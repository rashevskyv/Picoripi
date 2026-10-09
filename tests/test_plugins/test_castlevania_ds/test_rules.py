"""Castlevania DS plugin (Dawn of Sorrow, Portrait of Ruin, Order of Ecclesia): codes, string bank, fonts, pictures;
real data from the workspaces when they are on disk."""
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.texture_formats import tiles
from plugins.castlevania_ds import codec
from plugins.castlevania_ds.rules import TEXT_FORMAT, font_descriptors
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "castlevania_ds"
PLUGIN_DIR = Path(__file__).parents[3] / "plugins" / PLUGIN
ROOT = Path(r"E:\Emulators\RomHacking\Castlevania")
WORKSPACES = {"dos": ROOT / "Dawn of Sorrow", "por": ROOT / "Portrait of Ruin", "ooe": ROOT / "Order of Ecclesia"}


def _bank(strings, regions=(("Names", 0, 2), ("Events", 3, 4))) -> dict:
    return {"format": TEXT_FORMAT, "game": "dos", "regions": [list(r) for r in regions],
            "strings": [s.hex() for s in strings]}


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, [["First line", "Second line"], ["A line of the next block"]])


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_codes_become_text_and_tags_and_back():
    data = (bytes([0xE7, 0x01, 0xE3, 0x08]) + bytes(c - 0x20 for c in b"Hi") + bytes([0xE6, 0x3B, 0xE5, 0xE4, 0xE2, 0x01,
                                                                                       0xED, 0xE1, 0x00, 0x05, 0xC5, 0xE9]))
    text = codec.decode(data)
    assert text == "[name:01][face:08]Hi\n［[wait][box]\n[next][A][endchoice:0005][xC5][same]\n"
    assert codec.encode(text) == data


def test_a_line_break_after_a_new_box_is_kept():
    data = bytes([0xE4, 0xE6, 0x21])
    assert codec.decode(data) == "[box]\n\nA"
    assert codec.encode(codec.decode(data)) == data


def test_ukrainian_letters_have_their_own_cells_and_signs_stay():
    assert len(codec.UA_SLOTS) == 66 and len(set(codec.UA_SLOTS.values())) == 66
    assert all(0x5F <= code <= 0xBE for code in codec.UA_SLOTS.values())
    assert not set(codec.UA_SLOTS.values()) & {codec.CODES[c] for c in "’“”…«»çñ"}
    assert codec.decode(codec.encode("Їжак ґанок")) == "Їжак ґанок"


def test_unknown_characters_are_reported_and_the_end_code_refused():
    assert codec.unknown_chars("Hi 🙂[wait]") == ["🙂"]
    with pytest.raises(codec.EncodeError):
        codec.encode("Ω")
    assert codec.encode("aΩ", strict=False) == bytes([0x41, 0x1F])
    with pytest.raises(codec.EncodeError):
        codec.encode("[xEA]")


def test_the_bank_loads_in_regions_and_saves_only_the_edited_string():
    strings = [bytes([0x21 + i]) for i in range(5)]
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(_bank(strings))
    assert blocks == [["A", "B", "C"], ["D", "E"]] and names["1"] == "Events (3-4)"
    assert rules.get_message_attributes(1, 1) == {"id": 4}
    blocks[1][1] = "Привіт"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved["strings"][4] == codec.encode("Привіт").hex()
    assert saved["strings"][:4] == [s.hex() for s in strings[:4]]
    assert rules.get_string_layout(0, 0)["font_file"] == "cvds_text.json"


def _font(count=3, width=8, height=8, tail=b"\x00\x31"):
    data = bytearray()
    for glyph in range(count):
        data += glyph.to_bytes(2, "big") + bytes([(glyph * 37 + i) & 0xFF for i in range(width * height // 8)])
    return bytes(data + tail)


def test_font_records_unpack_and_pack_back_and_an_edit_lands_in_its_record():
    for cell in ([8, 8], [16, 12]):
        raw = _font(width=cell[0], height=cell[1])
        params = {"cell": cell, "chars": {"A": 1}}
        meta, sheets = font_formats.extract("cv_nds", raw, params)
        assert font_formats.pack("cv_nds", meta, sheets, raw, params) == raw
        assert font_formats.char_map(meta) == {"A": 1}
        sheet = sheets[0].copy()
        sheet.paste((255, 255, 255, 255), (cell[0], 0, 2 * cell[0], cell[1]))   # glyph 1: all ink
        packed = font_formats.pack("cv_nds", meta, [sheet], raw, params)
        record = 2 + cell[0] * cell[1] // 8
        assert packed[record + 2:2 * record] == b"\xff" * (record - 2) and packed[:record] == raw[:record]
        assert packed[-2:] == raw[-2:]


def test_linear_sprite_pictures_read_and_write_back():
    data = bytes(range(256)) * 4                                     # 4bpp, 16 x 128 pixels
    params = {"bpp": 4, "per_row": 2, "linear": True}
    image = tiles.read(data, params)[0].image
    assert image.size == (16, 128)
    assert image.getpixel((1, 0))[0] == tiles.read(data, params)[0].image.getpixel((1, 0))[0]
    assert tiles.write(data, {0: image}, params) == data
    pixel = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixel.alpha_composite(image)
    pixel.putpixel((0, 0), (255, 255, 255, 255))                     # grey level 15 = index 15
    assert tiles.write(data, {0: pixel}, params)[0] == 0x0F


# -- real data ------------------------------------------------------------------------------------------------

def _needs(key: str) -> Path:
    path = WORKSPACES[key] / "source" / key / "strings.cvdstext"
    if not path.is_file():
        pytest.skip(f"{key} workspace not on disk")
    return WORKSPACES[key] / "source"


@pytest.mark.parametrize("key", list(WORKSPACES))
def test_every_string_round_trips_and_every_font_and_picture_writes_back(key):
    source = _needs(key)
    bank = json.loads((source / key / "strings.cvdstext").read_text(encoding="utf-8"))
    for raw in bank["strings"]:
        assert codec.encode(codec.decode(bytes.fromhex(raw))).hex() == raw
    used = {b for raw in bank["strings"] for b in bytes.fromhex(raw)}
    assert not used & set(codec.UA_SLOTS.values()) - {0xE2, 0xE3, 0xE7, 0xE8}  # a slot is never an English letter
    for descriptor in font_descriptors():
        if descriptor["path"].startswith(key + "/"):
            raw = (source / descriptor["path"]).read_bytes()
            meta, sheets = font_formats.extract("cv_nds", raw, descriptor["params"])
            assert font_formats.pack("cv_nds", meta, sheets, raw, descriptor["params"]) == raw
    entries = [e for e in json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
               if e["path"].startswith(key + "/")]
    assert entries
    for entry in entries:
        raw = (source / entry["path"]).read_bytes()
        image = texture_formats.read(entry["format"], raw, entry["params"])[0].image
        assert texture_formats.write(entry["format"], raw, {0: image}, entry["params"]) == raw, entry["label"]


@pytest.mark.parametrize("key", list(WORKSPACES))
def test_the_rom_rebuilds_byte_exact_and_long_text_moves_to_the_new_overlay(key):
    source = _needs(key)
    scripts = ROOT.parent / "_shared" / "scripts"
    roms = list((WORKSPACES[key] / "ISO").glob("*.nds"))
    if not (scripts / "zt" / "cvds.py").is_file() or len(roms) != 1:
        pytest.skip("workspace scripts or the base ROM not on disk")
    sys.path.insert(0, str(scripts))
    try:
        from zt import cvds
    finally:
        sys.path.remove(str(scripts))
    game = next(g for g in cvds.GAMES.values() if g.key == key)
    base = roms[0].read_bytes()
    strings = [bytes.fromhex(s) for s in json.loads((source / key / "strings.cvdstext").read_text(encoding="utf-8"))["strings"]]
    rom = cvds.Rom(base)
    assert cvds.read_strings(rom, game) == strings
    assert cvds.write_strings(rom, game, strings) and bytes(rom) == base
    longer = [s + bytes([0x0B]) * 12 for s in strings]                # every string 12 letters longer
    rom = cvds.Rom(base)
    cvds.write_strings(rom, game, longer)
    built = cvds.Rom(bytes(rom))
    assert game.free.overlay in built.overlays()
    assert cvds.read_strings(built, game) == longer
