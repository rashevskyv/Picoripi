"""ROM mode of the Pokemon Gold, Silver and Crystal plugin: the Generation II codec and the real ROMs.

The real-ROM tests read the images from the RomHacking workspace (``PICORIPI_ROMHACKING``) and skip when they
are not there. Nothing from an image is copied into the repository.
"""
import hashlib
import json
from pathlib import Path

import pytest

import romhacking_root
from plugins.common import gb_rom
from plugins.pokemon_gen1 import rom_project, rom_text
from plugins.pokemon_gsc import rules as gsc_rules

WORKSPACE = romhacking_root.under("Pokemon")
ROMS = {
    "gold": WORKSPACE / "Gold and Silver/ISO/Pokemon - Gold Version (UE) [!].gbc",
    "silver": WORKSPACE / "Gold and Silver/ISO/Pokemon - Silver Version (UE) [!].gbc",
    "crystal": WORKSPACE / "Crystal/ISO/Pokemon - Crystal Version (UE) (V1.0) [!].gbc",
}
FACTS = gsc_rules.ROM_FACTS_DIR


def _rom(name):
    path = ROMS[name]
    if not path.is_file():
        pytest.skip(f"{name} ROM is not on this machine")
    return path


def _names():
    charmap = [["<PLAYER>", 0x52], ["@", 0x50], ["!", 0xE7], [" ", 0x7F], ["a", 0xA0], ["b", 0xA1], ["c", 0xA2],
               ["d", 0xA3], ["e", 0xA4]]
    return rom_text.Names(charmap, {"wStringBuffer": 0xCF4B}, {"_Target": (0x64, 0x4567)}, gen2=True)


def test_generation_two_far_reference_uses_opcode_0x16():
    names = _names()
    raw = bytes([0x00, 0xA0, 0x57, 0x16, 0x67, 0x45, 0x64, 0x00, 0x58])
    lines = rom_text.decode(raw, names)
    assert lines == [("text", '"a"'), ("done", ""), ("text_far", "_Target"), ("text_start", ""), ("prompt", "")]
    assert rom_text.encode(lines, names) == raw


def test_generation_two_sounds_and_buffer_codes_round_trip():
    names = _names()
    raw = bytes([0x00, 0xA0, 0x14, 0x01, 0x0F, 0x15, 0x12, 0x50])   # buffer 1, item sound, day, fanfare
    lines = rom_text.decode(raw, names)
    assert lines[1] == ("text_buffer", "1")
    assert rom_text.encode(lines, names) == raw


def test_generation_two_facts_are_present_for_every_image():
    for name in ("pokegold", "pokesilver", "pokecrystal", "pokecrystal11"):
        facts = FACTS / f"{name}.json"
        assert facts.is_file(), name


@pytest.mark.parametrize("name", ["gold", "silver", "crystal"])
def test_real_rom_unpacks_and_builds_back_to_the_same_bytes(name, tmp_path):
    rom_path = _rom(name)
    assert rom_project.identify(str(rom_path), FACTS) == {"role": "rom", "platform": "gb"}
    project = tmp_path / "project"
    rom_project.unpack(str(rom_path), str(project), lambda *_: None, lambda: False, FACTS)
    built = Path(rom_project.build(str(project / rom_project.SOURCE_DIR), str(tmp_path / "translation"),
                                   str(tmp_path / "out"), lambda *_: None, lambda: False, FACTS))
    assert hashlib.sha1(built.read_bytes()).hexdigest() == hashlib.sha1(rom_path.read_bytes()).hexdigest()


def test_pokedex_entry_keeps_its_height_weight_words_and_its_pages():
    names = _names()
    # name "ab@", height and weight (dw 204, 150), a first line, a page that starts with the "@" byte, and the end
    raw = bytes([0xA0, 0xA1, 0x50, 0xCC, 0x00, 0x96, 0x00, 0xA2, 0x4E, 0xA3, 0x50, 0xA4, 0x50])
    lines = rom_text.decode(raw, names, dex=True)
    assert lines == [("db", '"ab@"'), ("dw", "204, 150"), ("db", '"c"'), ("next", '"d"'), ("page", '"e"'),
                     ("text_end", "")]
    assert rom_text.encode(lines, names, 0, True) == raw


@pytest.mark.parametrize("name", ["gold"])
def test_real_rom_ukrainian_pokedex_entry_builds_and_reads_back_through_its_pointer(name, tmp_path):
    rom_path = _rom(name)
    project = tmp_path / "project"
    rom_project.unpack(str(rom_path), str(project), lambda *_: None, lambda: False, FACTS)
    facts = json.loads((FACTS / "pokegold.json").read_text(encoding="utf-8"))
    names = rom_project._names(facts)
    item = next(item for item in facts["files"] for body in item["labels"]
                if body["label"] == "BulbasaurPokedexEntry")
    body = next(b for b in item["labels"] if b["label"] == "BulbasaurPokedexEntry")
    assert body["movable"] and body["pointers"] and body["dex"]
    source_file = project / rom_project.SOURCE_DIR / rom_project.unit_name(item["file"])
    groups = rom_text.read_labels(source_file.read_text(encoding="utf-8"))
    # the name and the height and weight stay; the text is longer than the 106 bytes of the entry, and the last
    # string ends with "@" inside its literal (the entry's terminator, as in the decompilation)
    entry = [("db", '"SEED@"'), ("dw", "204, 150"),
             ("db", '"\u0420\u043e\u0441\u043b\u0456\u043d\u0430 \u0437 \u043d\u0430\u0441\u0456\u043d\u043d\u044f\u043c \u043d\u0430 \u0441\u043f\u0438\u043d\u0456 \u0456 \u0441\u0442\u0435\u0431\u043b\u043e\u043c, \u0449\u043e \u0440\u043e\u0441\u0442\u0435."'),
             ("next", '"\u0417\u0435\u043b\u0435\u043d\u0435 \u043b\u0438\u0441\u0442\u044f, \u0432\u0435\u043b\u0438\u043a\u0435 \u0442\u0456\u043b\u043e, \u044f\u0433\u043e\u0434\u0438."'),
             ("next", '"\u0412\u043e\u043d\u0430 \u0445\u043e\u0434\u0438\u0442\u044c \u0440\u0430\u0437\u043e\u043c \u0456\u0437 \u0434\u0440\u0443\u0437\u044f\u043c\u0438, \u0442\u043e\u043c\u0443 \u0457\u0457 \u043b\u044e\u0431\u0438\u0442\u044c \u043a\u043e\u0436\u0435\u043d \u0442\u0440\u0435\u043d\u0435\u0440."'),
             ("page", '"\u0429\u0435 \u043e\u0434\u0438\u043d \u0440\u044f\u0434\u043e\u043a \u0442\u0435\u043a\u0441\u0442\u0443 \u043d\u0430 \u0434\u0440\u0443\u0433\u0456\u0439 \u0441\u0442\u043e\u0440\u0456\u043d\u0446\u0456.@"')]
    edited = "\n".join(rom_text.format_body(label, entry if label == "BulbasaurPokedexEntry" else lines)
                       for label, lines in groups if label)
    source_file.write_text(edited, encoding="utf-8")
    built = Path(rom_project.build(str(project / rom_project.SOURCE_DIR), str(tmp_path / "translation"),
                                   str(tmp_path / "out"), lambda *_: None, lambda: False, FACTS))
    patched = built.read_bytes()
    size = len(rom_text.encode(entry, names, 0, True))
    assert size > body["size"]
    site = body["pointers"][0]
    offset = gb_rom.offset_of(gb_rom.bank_of(body["offset"]), patched[site] | patched[site + 1] << 8)
    assert gb_rom.bank_of(offset) == gb_rom.bank_of(body["offset"])
    # the bytes at the pointer are the entry, byte for byte (a decode would show katakana for the cells that the
    # Japanese tokens of the charmap share with some Ukrainian letters, so the check is on the bytes)
    assert patched[offset:offset + size] == rom_text.encode(entry, names, 0, True)
