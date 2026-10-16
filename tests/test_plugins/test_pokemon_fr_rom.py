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
    built = rom_project.build(unpacked, str(tmp_path / "translation"), str(tmp_path / "build"),
                              lambda p, t: None, lambda: False)
    assert Path(built).read_bytes() == path.read_bytes()


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
