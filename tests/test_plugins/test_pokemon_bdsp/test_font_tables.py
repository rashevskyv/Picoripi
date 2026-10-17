"""The BDSP font build writes an edited glyph table back and writes nothing for an unchanged one (real data: the owner's
romfs and the workspace font JSON; skipped without them)."""
import json

import pytest
import romhacking_root

from plugins.pokemon_bdsp import assets, build

WS = romhacking_root.under("Pokemon\\Brilliant Diamond and Shining Pearl")
ROMFS = WS / "romfs"
FONT = ROMFS / assets.ASSETS[1:] / assets.FONT_FOLDER / "efigs_font"
TABLE = WS / "source" / "font" / "efigs_font" / "efigs_font.json"


def _need():
    if not FONT.is_file() or not TABLE.is_file():
        pytest.skip("the owner's Brilliant Diamond romfs font bundle and workspace font JSON are not on disk")


def test_an_unchanged_glyph_table_writes_no_bundle(tmp_path):
    _need()
    same = {"font/efigs_font": {"font/efigs_font/efigs_font.json": TABLE.read_bytes()}}
    build.build_fonts(ROMFS, same, tmp_path, lambda: False)
    assert not list(tmp_path.rglob("efigs_font"))


def test_an_edited_glyph_advance_is_written_back(tmp_path):
    _need()
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    glyph = table["m_GlyphTable"][0]["m_Metrics"]
    glyph["m_HorizontalAdvance"] = glyph["m_HorizontalAdvance"] + 1.0
    edited = {"font/efigs_font": {"font/efigs_font/efigs_font.json": json.dumps(table).encode("utf-8")}}
    build.build_fonts(ROMFS, edited, tmp_path, lambda: False)
    target = (tmp_path / build.MOD_DIR / "contents" / build.TITLE_IDS[0] / "romfs"
              / assets.ASSETS[1:] / assets.FONT_FOLDER / "efigs_font")
    _bundle, serialized = assets.open_serialized(target.read_bytes())
    fonts = [serialized.read(obj.path_id) for obj in serialized.objects if obj.class_id == assets.MONOBEHAVIOUR]
    font = next(value for value in fonts if value.get("m_GlyphTable"))
    assert font["m_GlyphTable"][0]["m_Metrics"]["m_HorizontalAdvance"] == glyph["m_HorizontalAdvance"]
    assert len(font["m_GlyphTable"]) == len(table["m_GlyphTable"])
