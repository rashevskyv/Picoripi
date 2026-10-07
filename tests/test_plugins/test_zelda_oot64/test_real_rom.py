"""Ocarina of Time on the US 1.0 ROM itself (skipped where the workspace is not on this machine): every text
block, both fonts and one texture of each pixel format survive an unchanged save byte for byte, and edits land
where the game reads them."""
import glob
import json
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.texture_formats import sources
from plugins.common.n64_rom import N64Rom
from plugins.zelda_oot64.rules import TITLE_FILE, GameRules

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = Path(r"E:\Emulators\RomHacking\Zelda\Ocarina of Time\N64")
FONT_SOURCES = json.loads((ROOT / "plugins" / "zelda_oot64" / "font_sources.json").read_text(encoding="utf-8"))
TEXTURE_SOURCES = json.loads((ROOT / "plugins" / "zelda_oot64" / "texture_sources.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw():
    found = sorted(glob.glob(str(WORKSPACE / "source" / "*.z64")))
    if not found:
        pytest.skip("the Ocarina of Time workspace is not on this machine")
    return Path(found[0]).read_bytes()


class _Versions:
    def __init__(self, *versions):
        self.versions = versions

    def existing_versions(self):
        return iter(self.versions)


def test_every_text_block_opens_and_saves_unchanged(raw):
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert [len(block) for block in blocks] == [2115, 48, 2]
    assert list(names.values())[1:] == ["Credits", "Title screen"]
    assert blocks[2] == ["PRESS START", "NO CONTROLLER"]
    assert "SHIGERU MIYAMOTO" in blocks[1][0]
    assert rules.save_data_to_json_obj(blocks, names) == raw


def test_title_and_credits_edits_land_in_the_rom(raw):
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    blocks[1][0] = blocks[1][0].replace("SHIGERU MIYAMOTO", "UA TEST")
    blocks[2][0] = "UA TEST"
    saved = rules.save_data_to_json_obj(blocks, names)
    again, _ = GameRules().load_data_from_json_obj(saved)
    assert again[1][0] == blocks[1][0] and again[2] == ["UA TEST", "NO CONTROLLER"]
    overlay = N64Rom(saved).read_file(TITLE_FILE)
    assert overlay[0x2DA4:0x2DAE] == bytes([0xBF, 0xAB, 0xDF, 0xDF, 0xDF, 0xBE, 0xAF, 0xBD, 0xBE, 0xDF])
    blocks[2][0] = "PRESSES START"
    with pytest.raises(ValueError, match="room for 5 and 5"):
        rules.save_data_to_json_obj(blocks, names)
    blocks[2][0] = "ПУСК"
    with pytest.raises(ValueError, match="the title font has no"):
        rules.save_data_to_json_obj(blocks, names)


@pytest.mark.parametrize("index", range(len(FONT_SOURCES)))
def test_each_font_opens_and_packs_back_unchanged(raw, index):
    params = FONT_SOURCES[index]["params"]
    metadata, sheets = font_formats.extract("n64", raw, params)
    chars = font_formats.char_map(metadata)
    assert all(char in chars for char in "0123456789ABCZabcz.-")
    assert font_formats.pack("n64", metadata, sheets, raw, params) == raw


def test_a_title_font_glyph_edit_lands_in_the_kanji_file_only(raw):
    params = FONT_SOURCES[1]["params"]
    metadata, sheets = font_formats.extract("n64", raw, params)
    assert len(metadata["WID1"][0]["packets"]) == 236
    glyph = font_formats.char_map(metadata)["S"]
    ImageDraw.Draw(sheets[0]).rectangle((glyph % 16 * 16 + 2, glyph // 16 * 16 + 2,
                                         glyph % 16 * 16 + 13, glyph // 16 * 16 + 13), fill=(255, 255, 255, 255))
    edited = font_formats.pack("n64", metadata, sheets, raw, params)
    before, after = N64Rom(raw), N64Rom(edited)
    changed = [i for i in range(len(before.files)) if before.files[i] != after.files[i]
               or (i < 30 and before.read_file(i) != after.read_file(i))]
    assert changed == [6]
    again, sheets_again = font_formats.extract("n64", edited, params)
    assert sheets_again[0].tobytes() == sheets[0].tobytes()


@pytest.mark.parametrize("pixel_format", sorted({d["params"]["pixel_format"] for d in TEXTURE_SOURCES}))
def test_one_texture_of_each_pixel_format_round_trips_through_the_rom(raw, pixel_format):
    descriptor = next(d for d in TEXTURE_SOURCES if d["params"]["pixel_format"] == pixel_format)
    params = descriptor["params"]
    data, rewrap = sources.unwrap(raw, descriptor["member"], params)
    textures = texture_formats.read("raw", data, params)
    assert texture_formats.write("raw", data, {i: t.image for i, t in enumerate(textures)}, params) == data
    assert rewrap(data) == raw
    image = textures[0].image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 7, 3), fill=(255, 255, 255, 255))
    edited = rewrap(texture_formats.write("raw", data, {0: image}, params))
    again, _ = sources.unwrap(edited, descriptor["member"], params)
    assert texture_formats.read("raw", again, params)[0].image.tobytes() == \
        texture_formats.read("raw", texture_formats.write("raw", data, {0: image}, params), params)[0].image.tobytes()


# Formats the game uses only for pictures (no text texture has them): Volvagia's object, decomp object_fd.xml.
OTHER_FORMATS = [
    {"pixel_format": "n64:CI4", "width": 32, "height": 32, "offset": "0x458", "tlut_offset": "0x438"},
    {"pixel_format": "n64:CI4", "width": 32, "height": 32, "offset": "0xA78", "tlut_offset": "0xA58", "tlut_count": 12},
    {"pixel_format": "n64:CI8", "width": 32, "height": 32, "offset": "0x34A8", "tlut_offset": "0x32A8"},
    {"pixel_format": "n64:RGBA16", "width": 16, "height": 1, "offset": "0x438"},
]


@pytest.mark.parametrize("params", OTHER_FORMATS, ids=lambda p: f"{p['pixel_format']}@{p['offset']}")
def test_palette_and_rgba16_textures_round_trip(raw, params):
    data, rewrap = sources.unwrap(raw, "#637", params)
    image = texture_formats.read("raw", data, params)[0].image
    assert image.getbbox() is not None
    assert texture_formats.write("raw", data, {0: image}, params) == data
    if params["pixel_format"] == "n64:RGBA16":
        return
    edited = image.copy()
    ImageDraw.Draw(edited).rectangle((0, 0, 9, 9), fill=(255, 0, 255, 255))   # a colour the palette lacks
    new = texture_formats.write("raw", data, {0: edited}, params)
    tlut_end = int(params["tlut_offset"], 0) + 2 * params.get("tlut_count", 16 if "CI4" in params["pixel_format"] else 256)
    assert new[tlut_end:int(params["offset"], 0)] == data[tlut_end:int(params["offset"], 0)]
    assert texture_formats.read("raw", new, params)[0].image.getpixel((5, 5)) == (255, 0, 255, 255)
    assert len(rewrap(new)) == len(raw)


def test_a_text_save_keeps_the_texture_and_font_edits_of_the_translated_rom(raw):
    descriptor = next(d for d in TEXTURE_SOURCES if d["member"] == "#805" and d["params"]["width"] == 128)
    params = descriptor["params"]
    data, rewrap = sources.unwrap(raw, "#805", params)
    image = texture_formats.read("raw", data, params)[0].image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 40, 10), fill=(255, 255, 255, 255))
    translated = rewrap(texture_formats.write("raw", data, {0: image}, params))
    font_params = FONT_SOURCES[1]["params"]
    metadata, sheets = font_formats.extract("n64", translated, font_params)
    ImageDraw.Draw(sheets[0]).rectangle((0, 0, 15, 15), fill=(255, 255, 255, 255))
    translated = font_formats.pack("n64", metadata, sheets, translated, font_params)

    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(translated)
    rules.prepare_save_context(_Versions(translated, raw))
    blocks[2][0] = "UA TEST"
    saved = N64Rom(rules.save_data_to_json_obj(blocks, names))
    assert saved.read_file(805) == N64Rom(translated).read_file(805)
    assert saved.read_file(6) == N64Rom(translated).read_file(6)
    assert saved.read_file(TITLE_FILE) != N64Rom(raw).read_file(TITLE_FILE)
