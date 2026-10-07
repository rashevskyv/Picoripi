"""Majora's Mask on the US ROM itself (skipped where the workspace is not on this machine): every text block,
the font and one texture of each pixel format survive an unchanged save byte for byte, and edits land where
the game reads them; a text save keeps the texture, glyph and width edits of the translated ROM."""
import glob
import json
import struct
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.texture_formats import sources
from plugins.common.n64_rom import N64Rom
from plugins.zelda_mm64.rules import CODE_FILE, TITLE_FILE, TITLE_OFFSET, GameRules

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = Path(r"E:\Emulators\RomHacking\Zelda\Majoras Mask\N64")
FONT = json.loads((ROOT / "plugins" / "zelda_mm64" / "font_sources.json").read_text(encoding="utf-8"))[0]
TEXTURE_SOURCES = json.loads((ROOT / "plugins" / "zelda_mm64" / "texture_sources.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw():
    found = sorted(glob.glob(str(WORKSPACE / "source" / "*.z64")))
    if not found:
        pytest.skip("the Majora's Mask workspace is not on this machine")
    return Path(found[0]).read_bytes()


class _Versions:
    def __init__(self, *versions):
        self.versions = versions

    def existing_versions(self):
        return iter(self.versions)


def test_every_text_block_opens_and_saves_unchanged(raw):
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert [len(block) for block in blocks] == [4589, 45, 19, 1]
    assert list(names.values())[1:] == ["Credits", "Interface strings", "Title screen"]
    assert "SHIGERU MIYAMOTO" in blocks[1][0]
    assert blocks[2][:2] == ["Great Bay Coast", "Zora Cape"] and blocks[2][11:] == [
        "Rupee(s)", "Fast", "----", "Slow", "RED", "BLUE", "YELLOW", "GREEN"]
    assert blocks[3] == ["PRESS START"]
    assert rules.save_data_to_json_obj(blocks, names) == raw


def test_credits_interface_and_title_edits_land_in_the_rom(raw):
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    blocks[1][0] = blocks[1][0].replace("SHIGERU MIYAMOTO", "UA TEST")
    blocks[2][0] = "UA TEST"
    blocks[2][11] = "Rupees!"
    blocks[3][0] = "UA TEST"
    saved = N64Rom(rules.save_data_to_json_obj(blocks, names))
    again, _ = GameRules().load_data_from_json_obj(bytes(saved.data))
    assert again[1:] == blocks[1:] and again[0] == blocks[0]
    code = saved.read_file(CODE_FILE)
    assert code[0x12AC54:0x12AC64] == b"UA TEST" + bytes(9) and struct.unpack_from(">h", code, 0x12AD04)[0] == 7
    # U A blank blank blank | T E S T blank: cells of the ordered font (A = 10, blank = 62)
    assert saved.read_file(TITLE_FILE)[TITLE_OFFSET:TITLE_OFFSET + 10] == bytes([30, 10, 62, 62, 62, 29, 14, 28, 29, 62])
    blocks[3][0] = "PRESSES START"
    with pytest.raises(ValueError, match="room for 5"):
        rules.save_data_to_json_obj(blocks, names)
    blocks[3][0] = "ПУСК"
    with pytest.raises(ValueError, match="the title font has no"):
        rules.save_data_to_json_obj(blocks, names)
    blocks[3][0] = "UA"
    blocks[2][12] = "Faster"
    with pytest.raises(ValueError, match="room for 4"):
        rules.save_data_to_json_obj(blocks, names)


def test_the_font_opens_and_packs_back_unchanged(raw):
    metadata, sheets = font_formats.extract("n64", raw, FONT["params"])
    assert all(char in font_formats.char_map(metadata) for char in "0123456789ABCZabcz.-Àüª")
    assert font_formats.pack("n64", metadata, sheets, raw, FONT["params"]) == raw


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
    written = texture_formats.write("raw", data, {0: image}, params)
    again, _ = sources.unwrap(rewrap(written), descriptor["member"], params)
    assert texture_formats.read("raw", again, params)[0].image.tobytes() == \
        texture_formats.read("raw", written, params)[0].image.tobytes()


def test_every_listed_texture_resolves_once(raw):
    found = sources.resolve(TEXTURE_SOURCES, {"source_path": str(WORKSPACE / "source"), "translation_path": ""})
    names = [t["name"] for d in TEXTURE_SOURCES for t in d["params"]["textures"]]
    assert sorted(s.name for s in found) == sorted(names) and len(names) == 250


def test_a_text_save_keeps_the_texture_glyph_and_width_edits_of_the_translated_rom(raw):
    descriptor = next(d for d in TEXTURE_SOURCES if d["member"] == "#800" and d["params"]["width"] == 72)
    params = descriptor["params"]
    data, rewrap = sources.unwrap(raw, "#800", params)
    image = texture_formats.read("raw", data, params)[0].image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 30, 7), fill=(255, 255, 255, 255))
    translated = rewrap(texture_formats.write("raw", data, {0: image}, params))
    metadata, sheets = font_formats.extract("n64", translated, FONT["params"])
    glyph = font_formats.char_map(metadata)["S"]
    ImageDraw.Draw(sheets[0]).rectangle((glyph % 16 * 16 + 2, glyph // 16 * 16 + 2,
                                         glyph % 16 * 16 + 13, glyph // 16 * 16 + 13), fill=(255, 255, 255, 255))
    metadata["WID1"][0]["packets"][glyph]["width"] = 14
    translated = font_formats.pack("n64", metadata, sheets, translated, FONT["params"])

    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(translated)
    rules.prepare_save_context(_Versions(translated, raw))
    blocks[3][0] = "UA TEST"
    blocks[0][0] += " UA"
    saved = N64Rom(rules.save_data_to_json_obj(blocks, names))
    before = N64Rom(translated)
    assert saved.read_file(800) == before.read_file(800)
    assert saved.read_file(28) == before.read_file(28)
    widths = int(FONT["params"]["widths_offset"], 16)
    assert struct.unpack_from(">f", saved.read_file(CODE_FILE), widths + 4 * glyph)[0] == 14.0
    assert GameRules().load_data_from_json_obj(bytes(saved.data))[0][3] == ["UA TEST"]
