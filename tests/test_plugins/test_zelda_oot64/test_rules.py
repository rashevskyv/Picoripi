"""Ocarina of Time (N64): codec, load and save of a ROM-shaped image (the ROM machinery is tested with MM)."""
import struct

import pytest

from core.containers import yaz0
from plugins.common.n64_rom import N64Rom, compute_crc
from plugins.testing import check_loads, check_validator
from plugins.zelda_oot64.msg_codec import FORMAT
from plugins.zelda_oot64.rules import FONT_WIDTHS, MAX_LINE_WIDTH, GameRules

PLUGIN = "zelda_oot64"
TABLE = 0xFD9EC
MESSAGES = [
    (0x0001, 0x23, b"\x1a\x13\x2d\x08You borrowed a \x05\x41Pocket Egg\x05\x40!\x09\x01Nice."),
    (0x0002, 0x03, b"\x86l\xe8ve \x9f to talk.\x04Next box\x12\x28\x50"),
    (0xFFFD, 0x00, b""),
]


def _rom():
    """A 2 MB image shaped like the US 1.0 ROM: file 22 = English text, file 27 = Yaz0 code."""
    rom = bytearray(0x200000)
    rom[0:4] = b"\x80\x37\x12\x40"
    rom[0x3B:0x3F] = b"CZLE"
    text = bytearray()
    code = bytearray(TABLE + 8 * (len(MESSAGES) + 1) + 0x20)
    for n, (message_id, info, body) in enumerate(MESSAGES):
        struct.pack_into(">HBBI", code, TABLE + 8 * n, message_id, info, 0, 0x07000000 | len(text))
        text += body + b"\x02"
        text += b"\0" * (-len(text) % 4)
    struct.pack_into(">HBBI", code, TABLE + 8 * len(MESSAGES), 0xFFFF, 0, 0, 0)
    text += b"\0" * (-len(text) % 16)
    stored = yaz0.compress(bytes(code))
    after = 0x100000 + len(text) + 0x40
    files = [(0, 0x1060, 0, 0)] + [(0x2000 + i * 0x10,) * 3 + (0,) for i in range(1, 22)]
    files += [(0x100000, 0x100000 + len(text), 0x100000, 0)]
    files += [(after + i * 0x10,) * 2 + (0x180000, 0) for i in range(4)]
    files += [(0x200000, 0x200000 + len(code), 0x110000, 0x110000 + len(stored))]
    for n, entry in enumerate(files):
        struct.pack_into(">IIII", rom, 0x7430 + 16 * n, *entry)
    rom[0x100000:0x100000 + len(text)] = text
    rom[0x110000:0x110000 + len(stored)] = stored
    struct.pack_into(">II", rom, 0x10, *compute_crc(bytes(rom)))
    return bytes(rom)


@pytest.fixture(scope="module")
def raw_rom():
    return _rom()


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_codes_colors_buttons_and_accents_read_as_tags_and_encode_back():
    text = FORMAT.decode(MESSAGES[0][2]) + "|" + FORMAT.decode(MESSAGES[1][2])
    assert text == ("{unskippable}{item-icon:45}{quicktext-on}You borrowed a {color:red}Pocket Egg"
                    "{color:default}!{quicktext-off}\nNice.|Él{x:E8}ve {btn:A} to talk.{box-break}\nNext box{sfx:10320}")
    assert FORMAT.encode("{color:light-blue}é{color:68}") == b"\x05\x44\x96\x05\x44"


def test_the_rom_opens_and_an_unchanged_project_saves_it_identically(raw_rom):
    rules = GameRules()
    blocks, _ = rules.load_data_from_json_obj(raw_rom)
    assert blocks[0][0].startswith("{unskippable}") and len(blocks[0]) == 3
    assert rules.get_message_attributes(0, 0) == {"message_id": 1, "textbox_type": 2, "textbox_position": 3}
    assert rules.save_data_to_json_obj(blocks, {}) == raw_rom


def test_longer_text_moves_and_the_one_reference_is_retargeted(raw_rom, monkeypatch):
    import plugins.common.z64_rules as z64_rules
    calls = []
    monkeypatch.setattr(z64_rules, "retarget_constant",
                        lambda code, old, new, expected: calls.append((old, new, expected)) or code)
    rules = GameRules()
    blocks, _ = rules.load_data_from_json_obj(raw_rom)
    blocks[0][1] += " and more" * 20
    out = N64Rom(rules.save_data_to_json_obj(blocks, {}))
    assert calls == [(0x100000, N64Rom(raw_rom).free_vrom(), 1)]
    again, _ = GameRules().load_data_from_json_obj(bytes(out.data))
    assert again == blocks


def test_line_width_uses_the_game_table(raw_rom):
    rules = GameRules()
    rules.load_data_from_json_obj(raw_rom)
    # É and é are font slots 0x86 and 0x96, the A button 0x9F
    expected = FONT_WIDTHS[0x86 - 0x20] + FONT_WIDTHS[0x96 - 0x20] + FONT_WIDTHS[0x9F - 0x20]
    assert rules.calculate_string_width_override("Éé{btn:A}", {}) == expected
    assert rules.get_string_layout(0, 0)["max_width"] == MAX_LINE_WIDTH


def test_line_width_prefers_the_font_editors_map():
    class Window:
        all_font_maps = {"oot_font.json": {"É": {"width": 3}, "Ж": {"width": 11}}}

    rules = GameRules(Window())
    # É from the editor's map, é and the A button from the table, Ж (only in the map) from the map
    expected = 3 + FONT_WIDTHS[0x96 - 0x20] + FONT_WIDTHS[0x9F - 0x20] + 11
    assert rules.calculate_string_width_override("Éé{btn:A}Ж", {}) == expected
    assert GameRules().calculate_string_width_override("É", {}) == FONT_WIDTHS[0x86 - 0x20]


def test_the_majoras_mask_rom_is_refused(raw_rom):
    raw = bytearray(raw_rom)
    raw[0x3B:0x3F] = b"NZSE"
    with pytest.raises(ValueError, match="supports CZLE v0"):
        GameRules().load_data_from_json_obj(bytes(raw))


def test_the_shipped_context_belongs_to_this_rom():
    import json
    from pathlib import Path
    data = json.loads((Path("plugins") / "zelda_oot64" / "context.json").read_text(encoding="utf-8"))
    assert data["source"]["rom_sha1"] == "ad69c91157f6705e8ab06c79fe08aad47bb57ba7"
    assert len(data["messages"]) > 1000 and len(data["glossary"]) > 100
