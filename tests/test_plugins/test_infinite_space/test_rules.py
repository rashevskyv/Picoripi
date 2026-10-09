"""Infinite Space plugin: the scx script, the OBD dialogue font, .tex textures and .bgd sheets; real data."""
import json
import struct
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.font_formats import char_map
from plugins.infinite_space import scx
from plugins.infinite_space.textures import describe
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "infinite_space"
PLUGIN_DIR = Path(__file__).parents[3] / "plugins" / "infinite_space"
WS = Path(r"E:\Emulators\RomHacking\Infinite Space")
SOURCE = WS / "source"
needs_data = pytest.mark.skipif(not (SOURCE / "data" / "Event" / "SpaceShip.scx").is_file(),
                                reason="Infinite Space workspace not on disk")


def _letters(text: str) -> bytes:
    return b"".join(bytes((0x80, 2 * scx.CHARACTERS.index(c) + 1)) for c in text)


def _script(*lines: bytes) -> bytes:
    """An scx with one empty slot, the lines, and a 4-byte table after them."""
    slots = [0] + [1] * len(lines)
    head_size = scx.SLOTS_AT + 4 * len(slots)
    head = bytearray(b"scx\0" + bytes(4) + struct.pack("<I", len(slots)) + bytes(scx.SLOTS_AT - 12) + bytes(4 * len(slots)))
    at, body = head_size, bytearray()
    for n, line in enumerate(lines):
        struct.pack_into("<I", head, scx.SLOTS_AT + 4 * (n + 1), at + len(body))
        body += line + b"\0"
    end = head_size + len(body)
    for k in range(scx.TABLES):
        struct.pack_into("<I", head, scx.TABLES_AT + 4 * k, end)
    return bytes(head) + bytes(body) + b"TABL"


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, "First line\nSecond line\n\nA line of the next block")


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_letters_and_commands_become_editor_text_and_back():
    raw = b"[\\c,1,12]" + _letters("Yuri, hi!") + b"[\\n]" + _letters("I’m") + b"[\\r]"
    text = scx.to_editor(raw)
    assert text == "[\\c,1,12]Yuri, hi!\nI’m[\\r]"
    assert scx.from_editor(text) == raw
    assert scx.from_editor("I'm") == _letters("I’m")


def test_a_letter_the_font_lacks_is_refused():
    with pytest.raises(scx.FormatError):
        scx.from_editor("Привіт")


def test_a_longer_line_moves_the_tables():
    data = _script(b"[\\w,1,=,2]", _letters("Hello"))
    script = scx.parse(data)
    assert script.build(script.strings) == data
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks == [["Hello"]]                         # the bare command line is not listed
    blocks[0][0] = "UA TEST: a much longer hello"
    again = scx.parse(rules.save_data_to_json_obj(blocks, names))
    assert scx.to_editor(again.strings[1]) == "UA TEST: a much longer hello"
    assert again.strings[0] == b"[\\w,1,=,2]" and again.raw.endswith(b"TABL")
    assert struct.unpack_from("<I", again.raw, scx.TABLES_AT)[0] == len(again.raw) - 4


def _obd(glyphs: int) -> bytes:
    tiles = bytes(range(256)) * (glyphs * 64 // 256 + 1)
    tiles = tiles[:glyphs * 64]
    head = bytearray(b"OBD\0" + struct.pack("<HHHHHHH", 0, 32, len(tiles) // 1024, len(tiles), 0, 1, 32))
    head += bytes(0x18 - len(head))
    offsets = [0x2C, 0x2C + len(tiles)] + [0x2C + len(tiles) + 32] * 3
    head += struct.pack("<5I", *offsets)
    return bytes(head) + tiles + bytes(32)


def test_the_obd_font_packs_back_and_takes_an_edit():
    data = _obd(4)
    params = {"first": 0, "count": 4, "chars": "ABCD"}
    metadata, sheets = font_formats.extract("is_obd", data, params)
    assert font_formats.pack("is_obd", metadata, sheets, data, params) == data
    assert char_map(metadata)["C"] == 2
    ImageDraw.Draw(sheets[0]).rectangle((8, 0, 15, 15), fill=(255, 255, 255, 255))
    packed = font_formats.pack("is_obd", metadata, sheets, data, params)
    assert packed[0x2C + 64:0x2C + 128] == bytes([0x11]) * 64 and packed[0x2C:0x2C + 64] == data[0x2C:0x2C + 64]


def test_a_tex_texture_writes_back():
    pixels = bytes([0b11100100]) * 8                        # 2-bit pixels 0,1,2,3
    palette = struct.pack("<4H", 0, 0x7FFF, 0x001F, 0x03E0)
    data = struct.pack("<IHHII", 0, 8, 4, 0x2C, len(pixels)) + bytes(12) + struct.pack("<III", 0, 0x2C + 8, 8) + bytes(4)
    data += pixels + palette
    texture = texture_formats.read("is_tex", data)[0]
    assert texture.image.size == (8, 4)
    assert texture_formats.write("is_tex", data, {0: texture.image}) == data
    image = texture.image.copy()
    image.putpixel((0, 0), (255, 0, 0, 255))
    assert texture_formats.write("is_tex", data, {0: image})[0x2C] & 3 == 2


# -- real data -------------------------------------------------------------------------------------------------


@needs_data
def test_the_script_saves_back_byte_for_byte_and_every_line_reencodes():
    data = (SOURCE / "data" / "Event" / "SpaceShip.scx").read_bytes()
    script = scx.parse(data)
    assert len(script.strings) == 9349 and script.build(list(script.strings)) == data
    assert all(scx.from_editor(scx.to_editor(line)) == line for line in script.strings)
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(data)
    assert sum(len(block) for block in blocks) > 5000
    assert rules.save_data_to_json_obj(blocks, names) == data


@needs_data
def test_the_dialogue_font_packs_back_unchanged():
    entry = json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8"))[0]
    data = (SOURCE / entry["path"][0]).read_bytes()
    metadata, sheets = font_formats.extract("is_obd", data, entry["params"])
    assert font_formats.pack("is_obd", metadata, sheets, data, entry["params"]) == data
    assert len(char_map(metadata)) == 78


@needs_data
def test_every_picture_reads_and_writes_back():
    entries = describe(SOURCE)
    assert entries == json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    for entry in entries[::25]:
        data = (SOURCE / entry["path"]).read_bytes()
        images = {i: t.image for i, t in enumerate(texture_formats.read(entry["format"], data, entry.get("params", {})))}
        assert texture_formats.write(entry["format"], data, images, entry.get("params", {})) == data, entry["label"]
