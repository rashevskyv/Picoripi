"""ROM mode of the Pokemon Gen 1 plugin: the text codec, the GB helpers, and the real Red, Blue and Yellow ROMs.

The real-ROM tests read the images from ``PICORIPI_RED_ROM`` / ``PICORIPI_BLUE_ROM`` / ``PICORIPI_YELLOW_ROM`` or the
owner's workspace and skip when they are not there. Nothing from an image is copied into the repository.
"""
import hashlib
import json
import os
from pathlib import Path

import pytest

import romhacking_root
from plugins.common import gb_rom
from plugins.pokemon_gen1 import rom_project, rom_text

WORKSPACE = romhacking_root.under("Pokemon")
ROMS = {
    "red": Path(os.environ.get("PICORIPI_RED_ROM", WORKSPACE / "Red and Blue/ISO/Pokemon Red Version (UE) [S][!].gb")),
    "blue": Path(os.environ.get("PICORIPI_BLUE_ROM", WORKSPACE / "Red and Blue/ISO/Pokemon Blue Version (UE) [S][!].gb")),
    "yellow": Path(os.environ.get("PICORIPI_YELLOW_ROM",
                                  WORKSPACE / "Yellow/ISO/Pokemon Yellow Version - Special Pikachu Edition (UE) [!].gb")),
}
LONG_TEXT = [("text", '"Picoripi moves this body into free space because the new text is much longer than the old."'),
             ("line", '"It must still be reached through every text far operand."'),
             ("done", "")]


def _rom(name):
    path = ROMS[name]
    if not path.is_file():
        pytest.skip(f"{name} ROM is not on this machine")
    return path


def _names():
    charmap = [["<PLAYER>", 0x52], ["@", 0x50], ["!", 0xE7], [" ", 0x7F], ["n", 0xAD], ["A", 0x80],
               ["a", 0xA0], ["b", 0xA1], ["c", 0xA2], ["d", 0xA3], ["e", 0xA4], ["g", 0xA6], ["h", 0xA7],
               ["i", 0xA8], ["l", 0xAB], ["m", 0xAC], ["o", 0xAE], ["p", 0xAF], ["r", 0xB1], ["s", 0xB2],
               ["t", 0xB3], ["u", 0xB4], ["w", 0xB6], [".", 0xE8], ["y", 0xB8]]
    return rom_text.Names(charmap, {"wStringBuffer": 0xCF4B}, {"_Target": (3, 0x4567)})


def test_codec_round_trip_and_lines():
    names = _names()
    raw = bytes([0x00, 0x52, 0x7F, 0x4F, 0xA0, 0xAD, 0x7F, 0x50, 0x01, 0x4B, 0xCF, 0x00, 0xE7, 0x50, 0x50])
    lines = rom_text.decode(raw, names)
    assert lines == [("text", '"<PLAYER> "'), ("line", '"an @"'), ("text_ram", "wStringBuffer"),
                     ("text", '"!@"'), ("text_end", "")]
    assert rom_text.encode(lines, names) == raw


def test_codec_terminators_far_reference_and_text_start():
    names = _names()
    raw = bytes([0x00, 0xA0, 0x57, 0x17, 0x67, 0x45, 0x03, 0x00, 0x58])
    lines = rom_text.decode(raw, names)
    assert lines == [("text", '"a"'), ("done", ""), ("text_far", "_Target"), ("text_start", ""), ("prompt", "")]
    assert rom_text.encode(lines, names) == raw


def test_codec_stops_at_text_asm():
    names = _names()
    raw = bytes([0x00, 0xA0, 0x08, 0xC9, 0xC9])        # the code after text_asm is not text
    lines = rom_text.decode(raw, names)
    assert lines == [("text", '"a"'), ("text_asm", "")]
    assert rom_text.encode(lines, names) == raw[:3]


def test_at_sign_inside_text_is_a_character_before_the_end():
    names = _names()
    raw = bytes([0x00, 0xA0, 0xE7, 0x50, 0x50])        # "a!" then "@" as a character, then text_end
    lines = rom_text.decode(raw, names)
    assert lines == [("text", '"a!@"'), ("text_end", "")]
    assert rom_text.encode(lines, names) == raw


def test_header_checksums_are_consistent():
    rom = bytearray(0x8000)
    for index in range(0x134, 0x14D):
        rom[index] = index & 0xFF
    gb_rom.fix_checksums(rom)
    total = 0
    for byte in rom[0x134:0x14D]:
        total = (total - byte - 1) & 0xFF
    assert rom[0x14D] == total
    assert (rom[0x14E] << 8 | rom[0x14F]) == (sum(rom) - rom[0x14E] - rom[0x14F]) & 0xFFFF


def test_free_space_takes_first_fit_in_allowed_banks():
    free = gb_rom.FreeSpace([[0, 0x100, 0x200], [2, 0x8000, 0x8010], [3, 0xC000, 0xC100]])
    assert free.take(0x10, banks=[2, 3]) == 0x8000      # bank 2 has exactly 0x10 bytes
    assert free.take(0x20, banks=[2]) is None           # bank 2 is used up
    assert free.take(0x20, banks=[3]) == 0xC000
    assert free.take(0x20) == 0x100                     # no filter: the first run, bank 0


def test_dname_fields_pad_with_at_sign_and_reject_overflow():
    names = _names()
    assert rom_text.encode([("dname", '"abc"')], names, 5) == bytes([0xA0, 0xA1, 0xA2, 0x50, 0x50])
    assert rom_text.encode([("dname", '"abcde"')], names, 5) == bytes([0xA0, 0xA1, 0xA2, 0xA3, 0xA4])
    with pytest.raises(rom_text.CodecError):
        rom_text.encode([("dname", '"abcdef"')], names, 5)
    raw = bytes([0xA0, 0xA1, 0x50, 0x50, 0x50, 0xA2, 0xA3, 0x50, 0x50, 0x50])
    lines = rom_text.decode_names(raw, names, "dname", 5)
    assert lines == [("dname", '"ab"'), ("dname", '"cd"')]
    assert rom_text.encode(lines, names, 5) == raw


def test_li_entries_end_at_at_sign_and_have_any_length():
    names = _names()
    raw = bytes([0xA0, 0x50, 0xA1, 0xA2, 0x50])
    lines = rom_text.decode_names(raw, names, "li")
    assert lines == [("li", '"a"'), ("li", '"bc"')]
    assert rom_text.encode(lines, names) == raw


def test_facts_files_are_consistent():
    for facts_path in sorted(rom_project.FACTS_DIR.glob("*.json")):
        facts = json.loads(facts_path.read_text(encoding="utf-8"))
        assert facts["files"], facts_path.name
        for item in facts["files"]:
            for body in item["labels"]:
                assert 0 < body["size"] and body["offset"] + body["size"] <= facts["rom_size"]


@pytest.mark.parametrize("name", ["red", "blue", "yellow"])
def test_real_rom_unpacks_and_builds_back_to_the_same_bytes(name, tmp_path):
    rom_path = _rom(name)
    assert rom_project.identify(str(rom_path)) == {"role": "rom", "platform": "gb"}
    project = tmp_path / "project"
    assert rom_project.unpack(str(rom_path), str(project), lambda *_: None, lambda: False) == str(project)
    built = Path(rom_project.build(str(project / rom_project.SOURCE_DIR), str(tmp_path / "translation"),
                                   str(tmp_path / "out"), lambda *_: None, lambda: False))
    assert hashlib.sha1(built.read_bytes()).hexdigest() == hashlib.sha1(rom_path.read_bytes()).hexdigest()


def test_real_rom_moved_body_is_reached_through_its_far_reference(tmp_path):
    rom_path = _rom("red")
    project = tmp_path / "project"
    rom_project.unpack(str(rom_path), str(project), lambda *_: None, lambda: False)
    facts = json.loads((rom_project.FACTS_DIR / "pokered.json").read_text(encoding="utf-8"))
    names = rom_project._names(facts)
    target = next(body for item in facts["files"] for body in item["labels"]
                  if body["far"] and not body["fixed"] and body["size"] < 60)
    file_name = next(rom_project.unit_name(item["file"]) for item in facts["files"] if target in item["labels"])
    source_file = project / rom_project.SOURCE_DIR / file_name
    groups = rom_text.read_labels(source_file.read_text(encoding="utf-8"))
    edited = "\n".join(rom_text.format_body(label, LONG_TEXT if label == target["label"] else lines)
                       for label, lines in groups if label)
    source_file.write_text(edited, encoding="utf-8")
    built = Path(rom_project.build(str(project / rom_project.SOURCE_DIR), str(tmp_path / "translation"),
                                   str(tmp_path / "out"), lambda *_: None, lambda: False))
    patched = built.read_bytes()
    size = len(rom_text.encode(LONG_TEXT, names))
    assert size > target["size"]
    for site in target["far"]:
        offset = gb_rom.offset_of(patched[site + 2], patched[site] | patched[site + 1] << 8)
        assert rom_text.decode(patched[offset:offset + size], names) == LONG_TEXT
