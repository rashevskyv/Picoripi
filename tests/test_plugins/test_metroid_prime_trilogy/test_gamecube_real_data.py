"""Metroid Prime (GameCube, USA GM8E01) on the user's own unpacked disc (workspace ``Metroid\\Prime (GC + PC port)``,
skipped when it is not there): every string table and texture writes back unchanged and keeps an edit, and every
font packs back unchanged and keeps an edited glyph."""
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from plugins.metroid_prime_trilogy.rules import GameRules
from plugins.metroid_prime_trilogy.strg import Strg

SOURCE = Path(r"E:\Emulators\RomHacking\Metroid\Prime (GC + PC port)\source")


def _files(kind: str, pattern: str):
    return sorted((SOURCE / kind).rglob(pattern)) if SOURCE.exists() else []


@pytest.mark.parametrize("path", _files("text", "*.strg"), ids=lambda p: f"{p.parent.name}-{p.stem}")
def test_every_string_table_saves_back_byte_for_byte_and_keeps_an_edit(path):
    raw = path.read_bytes()
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert rules.save_data_to_json_obj(blocks, names) == raw
    if blocks[0]:
        blocks[0][0] = blocks[0][0] + " UA TEST"
        saved = rules.save_data_to_json_obj(blocks, names)
        assert Strg(saved).english[0].endswith(" UA TEST")
        assert Strg(saved).count == Strg(raw).count


@pytest.mark.parametrize("path", _files("font", "*.font"), ids=lambda p: p.stem)
def test_every_font_packs_back_and_keeps_an_edit(path):
    data = path.read_bytes()
    metadata, sheets = font_formats.extract("retro_font_gc", data)
    assert font_formats.pack("retro_font_gc", metadata, sheets, data) == data
    gly = metadata["GLY1"][0]
    chars = font_formats.char_map(metadata)
    glyph = chars["9"] if "9" in chars else next(iter(chars.values()))
    x = (glyph % gly["glyph_horizontal_count"]) * gly["cell_width"]
    y = (glyph // gly["glyph_horizontal_count"]) * gly["cell_height"]
    before = sheets[0].getpixel((x, y))
    ImageDraw.Draw(sheets[0]).rectangle((x, y, x + 2, y + 2), fill=(255, 255, 255, 255) if before[:3] != (255, 255, 255) else (0, 0, 0, 255))
    edited = font_formats.pack("retro_font_gc", metadata, sheets, data)
    assert edited != data and len(edited) == len(data)
    _meta, again = font_formats.extract("retro_font_gc", edited)
    assert again[0].getpixel((x, y)) != before


def test_the_default_fonts_are_the_gamecube_layout():
    versions = {int.from_bytes(p.read_bytes()[4:8], "big") for p in _files("font", "*.font")}
    if not versions:
        pytest.skip("the GameCube disc is not unpacked")
    assert versions <= {0, 1, 2}


@pytest.mark.parametrize("path", _files("texture", "*.txtr"), ids=lambda p: f"{p.parent.name}-{p.stem}")
def test_every_interface_texture_writes_back_unchanged_and_keeps_an_edit(path):
    data = path.read_bytes()
    texture = texture_formats.read("txtr_gx", data)[0]
    assert texture_formats.write("txtr_gx", data, {0: texture.image}) == data
    edited = texture.image.copy()
    ImageDraw.Draw(edited).rectangle((0, 0, 3, 3), fill=(255, 255, 255, 255))
    new = texture_formats.write("txtr_gx", data, {0: edited})
    assert len(new) == len(data)
