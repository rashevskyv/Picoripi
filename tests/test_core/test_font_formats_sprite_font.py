"""MonoGame SpriteFont backend (core/font_formats/sprite_font.py): real fonts round trip, edits, add_character."""
import os
from pathlib import Path

import pytest

from core.font_formats import sprite_font


def _fonts_dir():
    root = os.environ.get("PICORIPI_ROMHACKING", "").strip()
    folder = Path(root) / "_new" / "Links Awakening DX HD" / "Content" / "Fonts" if root else None
    if folder is None or not folder.is_dir():
        pytest.skip("PICORIPI_ROMHACKING is not set or the Links Awakening DX HD fonts are missing")
    return folder


def test_slot_layout_wraps_rows_below_the_atlas():
    positions, height = sprite_font._slot_layout([(8, 8), (8, 8), (8, 8)], 16, 10)
    assert positions == [(0, 12), (8, 12), (0, 20)]
    assert height == 28


def test_slot_layout_refuses_a_glyph_wider_than_the_atlas():
    with pytest.raises(ValueError):
        sprite_font._slot_layout([(32, 8)], 16, 8)


def test_all_real_fonts_round_trip_byte_exact():
    folder = _fonts_dir()
    names = sorted(p.name for p in folder.glob("*.xnb"))
    assert len(names) == 8
    for name in names:
        data = (folder / name).read_bytes()
        metadata, sheets = sprite_font.extract(data, {})
        assert sprite_font.pack(metadata, sheets, data, {}) == data, name


def test_pixel_edit_reaches_the_glyph_and_nothing_else_changes():
    data = (_fonts_dir() / "smallFont.xnb").read_bytes()
    metadata, sheets = sprite_font.extract(data, {})
    grid = metadata["GLY1"][0]
    cell = sprite_font._cells(metadata)["A"]
    sheet = sheets[0].copy()
    x0 = (cell % grid["glyph_horizontal_count"]) * grid["cell_width"]
    y0 = (cell // grid["glyph_horizontal_count"]) * grid["cell_height"]
    sheet.paste((255, 0, 0, 255), (x0, y0, x0 + 2, y0 + 2))
    out = sprite_font.pack(metadata, [sheet], data, {})
    assert out != data and len(out) == len(data)
    again_meta, again_sheets = sprite_font.extract(out, {})
    assert again_sheets[0].getpixel((x0, y0)) == (255, 0, 0, 255)
    assert sprite_font._cells(again_meta) == sprite_font._cells(metadata)


def test_add_character_creates_a_glyph_and_keeps_the_map_sorted():
    data = (_fonts_dir() / "newHeaderFont.xnb").read_bytes()
    metadata, sheets = sprite_font.extract(data, {})
    sheets = list(sheets)
    assert "Ї" not in sprite_font._cells(metadata)
    cell = sprite_font.add_character(metadata, sheets, "Ї")
    grid = metadata["GLY1"][0]
    assert cell == 95  # 95 glyphs in 6 rows of 16: the one free cell
    cw, ch = grid["cell_width"], grid["cell_height"]
    columns = grid["glyph_horizontal_count"]
    x0, y0 = (cell % columns) * cw, (cell // columns) * ch
    sheets[0].paste((255, 255, 255, 255), (x0, y0, x0 + cw, y0 + ch))
    out = sprite_font.pack(metadata, sheets, data, {})
    again_meta, again_sheets = sprite_font.extract(out, {})
    cells = sprite_font._cells(again_meta)
    assert "Ї" in cells
    assert again_sheets[0].getpixel((x0 + cw // 2, y0 + ch // 2))[3] == 255
    chars = [chr(c) for c in sorted(ord(k) for k in cells)]
    assert chars == sorted(chars)
    assert sprite_font.is_sprite_font(out)


def test_free_cells_and_add_without_spare_grow_one_row():
    data = (_fonts_dir() / "smallFont.xnb").read_bytes()
    metadata, sheets = sprite_font.extract(data, {"spare": 0})
    assert sprite_font.free_cells(metadata) == []
    sheets = list(sheets)
    before = metadata["GLY1"][0]["glyph_vertical_count"]
    cell = sprite_font.add_character(metadata, sheets, "Ж")
    assert cell == 16 * before
    assert metadata["GLY1"][0]["glyph_vertical_count"] == before + 1
    assert sheets[0].height == (before + 1) * metadata["GLY1"][0]["cell_height"]
