"""ROM mode of the Pokemon plugin (Generation III): the text codec and the GBA helpers, and the real ROM when present.

The real-ROM tests read the FireRed (USA, rev 0) image from ``PICORIPI_FIRERED_ROM`` or the owner's workspace and skip
when it is not there. Nothing from the image is copied into the repository.
"""
import os
import random
from pathlib import Path

import pytest

from plugins.common import gba_rom
from plugins.pokemon_fr import rom_project, rom_text
from plugins.pokemon_fr.rom_text import Charmap, CodecError

DEFAULT_ROM = Path("E:/Emulators/RomHacking/Pokemon/FireRed and LeafGreen/ISO/"
                   "Pokemon - FireRed Version (USA, Europe).gba")


def _rom_path():
    path = Path(os.environ.get("PICORIPI_FIRERED_ROM", DEFAULT_ROM))
    return path if path.is_file() else None


@pytest.fixture(scope="module")
def charmap():
    return Charmap.load()


def test_named_and_control_codes_round_trip(charmap):
    raw = bytes([0xFD, 0x01, 0xE2, 0xFC, 0x01, 0x08, 0xFE, 0xFF])   # {PLAYER} n {COLOR BLUE} newline
    text = charmap.decode(raw)
    assert text == "{PLAYER}n{COLOR BLUE}\\n"
    assert charmap.encode(text) == raw


def test_sound_ids_are_not_text_codes(charmap):
    # D4 00 is the letter Z and a space; the sound table must not turn it into a sound code in running text.
    assert charmap.decode(bytes([0xD4, 0x00, 0xFF])) == "Z "


def test_every_single_byte_round_trips(charmap):
    for code in range(0xFF):          # 0xFF is the terminator: a message ends there
        raw = bytes([code, 0xFF])
        assert charmap.encode(charmap.decode(raw)) == raw, hex(code)


def test_random_messages_round_trip(charmap):
    rng = random.Random(7)
    for _ in range(3000):
        body = bytes(rng.randrange(0xFF) for _ in range(rng.randrange(1, 12)))   # no terminator inside a message
        raw = body + b"\xff"
        assert charmap.encode(charmap.decode(raw)) == raw, raw.hex()


def test_unknown_cell_is_an_error(charmap):
    with pytest.raises(CodecError):
        charmap.encode("\u4e00")


def test_header_complement_matches_the_bios_rule():
    rom = bytearray(0x200)
    rom[0xA0:0xBD] = bytes(range(0x1D))
    gba_rom.fix_header(rom)
    assert rom[0xBD] == (-(sum(range(0x1D)) + 0x19)) & 0xFF
    before = bytes(rom)
    gba_rom.fix_header(rom)
    assert bytes(rom) == before


def test_pointer_index_finds_unaligned_pointers():
    rom = bytearray(64)
    rom[3:7] = (gba_rom.ROM_BASE + 0x20).to_bytes(4, "little")     # odd offset, as bytecode has
    assert gba_rom.pointer_index(bytes(rom)) == {gba_rom.ROM_BASE + 0x20: [3]}


def test_relocation_rewrites_pointers_and_frees_the_old_block():
    rom = bytearray(b"\xff" * 0x100)
    rom[0x10:0x14] = b"ABCD"
    rom[0x40:0x44] = (gba_rom.ROM_BASE + 0x10).to_bytes(4, "little")
    index = gba_rom.pointer_index(bytes(rom))
    relocator = gba_rom.Relocator(rom, index, floor=0x80)
    new = relocator.move(0x10, 4, b"LONGER TEXT")
    assert rom[0x40:0x44] == (gba_rom.ROM_BASE + new).to_bytes(4, "little")
    assert rom[new:new + 11] == b"LONGER TEXT"
    assert rom[0x10:0x14] == b"\xff" * 4


def test_real_rom_unedited_round_trip_is_byte_exact(charmap):
    path = _rom_path()
    if path is None:
        pytest.skip("FireRed ROM not on disk")
    rom = path.read_bytes()
    units, floor, _header = rom_text.load_units(rom_text.FACTS_DIR / "firered_usa_rev0.json")
    texts = rom_text.read_all(rom, units, charmap)
    assert rom_text.write_all(rom, units, charmap, floor, texts) == rom


def test_real_rom_unpack_and_build_match_the_image(tmp_path):
    path = _rom_path()
    if path is None:
        pytest.skip("FireRed ROM not on disk")
    unpacked = rom_project.unpack(str(path), str(tmp_path / "unpacked"), lambda p, t: None, lambda: False)
    source_root = Path(unpacked) / rom_project.SOURCE_DIR          # the host opens this folder as the project
    assert (source_root / rom_project.TEXT_FILE).is_file()
    built = rom_project.build(str(source_root), str(tmp_path / "translation"), str(tmp_path / "build"),
                              lambda p, t: None, lambda: False)
    assert Path(built).read_bytes() == path.read_bytes()


def test_real_rom_project_loads_saves_and_builds_unchanged(tmp_path):
    """The Project Manager's path: unpack, the plugin loads and saves the text file, the build packs the ROM."""
    from core.project_library import build as project_build
    from plugins.pokemon_fr.rules import GameRules

    path = _rom_path()
    if path is None:
        pytest.skip("FireRed ROM not on disk")
    rules = GameRules(None)
    never = lambda: False  # noqa: E731
    source = project_build.run_unpack(rules, {rom_project.ROM_ROLE: str(path)}, str(tmp_path / "project"),
                                      lambda p, t: None, never)
    text_file = Path(source) / rom_project.TEXT_FILE
    original = text_file.read_text(encoding="utf-8")
    data, block_names = rules.load_data_from_json_obj(original)
    assert len(data[0]) == len(rom_text.load_units(rom_text.FACTS_DIR / "firered_usa_rev0.json")[0])
    assert rules.save_data_to_json_obj(data, block_names) == original
    built = project_build.run_build(rules, "rom", str(tmp_path / "project"), source,
                                    str(tmp_path / "translation"), lambda p, t: None, never)
    assert Path(built).read_bytes() == path.read_bytes()


def test_a_message_without_a_pointer_refuses_to_move():
    rom = bytearray(b"\xff" * 0x100)
    rom[0x10:0x14] = b"ABCD"
    relocator = gba_rom.Relocator(rom, {}, floor=0x80)
    with pytest.raises(gba_rom.RomError):
        relocator.move(0x10, 4, b"LONGER THAN FOUR")
    assert rom[0x10:0x14] == b"ABCD"


def test_real_rom_longer_message_moves_and_reads_back(tmp_path, charmap):
    path = _rom_path()
    if path is None:
        pytest.skip("FireRed ROM not on disk")
    rom = path.read_bytes()
    units, floor, _header = rom_text.load_units(rom_text.FACTS_DIR / "firered_usa_rev0.json")
    unit = next(u for u in units if u.label == "ViridianForest_Text_RickDefeat")
    new_text = "No! Test text that is clearly longer than the original line"
    patched = rom_text.write_all(rom, units, charmap, floor, {unit.label: new_text})
    pointers = gba_rom.pointer_index(rom).get(gba_rom.ROM_BASE + unit.offset, [])
    assert pointers, "the message has no pointer in the image"
    target = int.from_bytes(patched[pointers[0]:pointers[0] + 4], "little") - gba_rom.ROM_BASE
    size = len(charmap.encode(new_text))
    assert charmap.decode(patched[target:target + size]) == new_text
    assert patched[unit.offset:unit.offset + unit.size] == b"\xff" * unit.size


RUBY_DIR = Path("E:/Emulators/RomHacking/Pokemon/Ruby and Sapphire/ISO")
EMERALD_ROM = Path("E:/Emulators/RomHacking/Pokemon/Emerald/ISO/Pokemon - Emerald Version (USA, Europe).gba")
IMAGES = {
    "firered_rev0": (DEFAULT_ROM, "FireRed (USA, rev 0)"),
    "firered_rev1": (DEFAULT_ROM.parent / "Pokemon - FireRed Version (USA, Europe) (Rev 1).gba", "FireRed (USA, rev 1)"),
    "leafgreen_rev0": (DEFAULT_ROM.parent / "Pokemon - LeafGreen Version (USA, Europe).gba", "LeafGreen (USA, rev 0)"),
    "leafgreen_rev1": (DEFAULT_ROM.parent / "Pokemon - LeafGreen Version (USA, Europe) (Rev 1).gba", "LeafGreen (USA, rev 1)"),
    "emerald": (EMERALD_ROM, "Emerald (USA, Europe)"),
    "ruby_rev0": (RUBY_DIR / "Pokemon - Ruby Version (USA, Europe).gba", "Ruby (USA, Europe)"),
    "ruby_rev1": (RUBY_DIR / "Pokemon - Ruby Version (USA, Europe) (Rev 1).gba", "Ruby (USA, Europe) (Rev 1)"),
    "ruby_rev2": (RUBY_DIR / "Pokemon - Ruby Version (USA, Europe) (Rev 2).gba", "Ruby (USA, Europe) (Rev 2)"),
    "sapphire_rev0": (RUBY_DIR / "Pokemon - Sapphire Version (USA, Europe).gba", "Sapphire (USA, Europe)"),
    "sapphire_rev1": (RUBY_DIR / "Pokemon - Sapphire Version (USA, Europe) (Rev 1).gba", "Sapphire (USA, Europe) (Rev 1)"),
    "sapphire_rev2": (RUBY_DIR / "Pokemon - Sapphire Version (USA, Europe) (Rev 2).gba", "Sapphire (USA, Europe) (Rev 2)"),
}


@pytest.mark.parametrize("key", sorted(IMAGES))
def test_real_images_are_identified_and_round_trip_unedited(tmp_path, key):
    path, label = IMAGES[key]
    if not path.is_file():
        pytest.skip(f"{label} not on disk")
    assert rom_project.identify(str(path)) == {"role": rom_project.ROM_ROLE, "platform": "gba"}
    unpacked = rom_project.unpack(str(path), str(tmp_path / "unpacked"), lambda p, t: None, lambda: False)
    built = rom_project.build(str(Path(unpacked) / rom_project.SOURCE_DIR), str(tmp_path / "translation"),
                              str(tmp_path / "build"), lambda p, t: None, lambda: False)
    assert Path(built).read_bytes() == path.read_bytes()


def test_real_rom_unpack_writes_the_name_tables_and_their_budgets(tmp_path):
    path = _rom_path()
    if path is None:
        pytest.skip("FireRed ROM not on disk")
    unpacked = rom_project.unpack(str(path), str(tmp_path / "unpacked"), lambda p, t: None, lambda: False)
    text_dir = Path(unpacked) / rom_project.SOURCE_DIR
    for name in ("move_names.inc", "item_names.inc", "trainer_names.inc", "berry_names.inc"):
        assert (text_dir / name).is_file(), name
    assert "gMoveName_0::" in (text_dir / "move_names.inc").read_text(encoding="utf-8")
    sizes, charmap = rom_project.field_budgets(str(text_dir))
    assert (sizes["gMoveName_1"], sizes["gItemName_1"], sizes["gTrainerName_25"]) == (13, 14, 12)
    assert "gMoveName_1" in sizes and "gMoveDescription_1" not in sizes
    assert len(charmap.encode("POUND")) == 6
    assert rom_project.field_budgets(str(tmp_path)) is None


def test_braille_texts_use_the_braille_codes():
    braille = rom_text.braille_charmap()
    assert braille is not None
    assert braille.decode(bytes([0x31, 0x17, 0xFF])) == "UP"
    assert braille.encode("UP") == bytes([0x31, 0x17, 0xFF])
    assert braille.decode(bytes([0x2C, 0xFF])) == "."


def test_real_rom_braille_and_decoration_fields_unpack(tmp_path):
    path = _rom_path()
    if path is None:
        pytest.skip("FireRed ROM not on disk")
    unpacked = rom_project.unpack(str(path), str(tmp_path / "unpacked"), lambda p, t: None, lambda: False)
    text_dir = Path(unpacked) / rom_project.SOURCE_DIR
    messages = (text_dir / rom_project.TEXT_FILE).read_text(encoding="utf-8")
    assert 'Braille_Text_Up::\n\t.string "UP$"' in messages
    sizes, _charmap = rom_project.field_budgets(str(text_dir))
    assert sizes["gDecorationName_0"] == 16
