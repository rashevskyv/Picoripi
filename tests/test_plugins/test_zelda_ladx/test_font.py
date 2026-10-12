"""The DX dialog font through the shared font backend (real ROM; skipped where the ROM is missing)."""
import json
from pathlib import Path

from core import font_formats

from .test_real_rom import _load

FONT_SOURCES = Path(__file__).resolve().parents[3] / "plugins" / "zelda_ladx" / "font_sources.json"
FONT_START = 0x3D000
FONT_END = FONT_START + 160 * 16


def _params():
    return json.loads(FONT_SOURCES.read_text(encoding="utf-8"))[0]["params"]


def test_unedited_font_packs_back_to_the_rom():
    raw = _load()
    metadata, sheets = font_formats.extract("texture_grid", raw, _params())
    assert bytes(font_formats.pack("texture_grid", metadata, sheets, raw, _params())) == raw


def test_edited_glyph_changes_only_the_font_block():
    raw = _load()
    metadata, sheets = font_formats.extract("texture_grid", raw, _params())
    sheet = sheets[0].copy()
    x, y = 8, 0  # top-left pixel of cell 1
    sheet.putpixel((x, y), (0, 0, 0, 255))
    out = bytes(font_formats.pack("texture_grid", metadata, [sheet], raw, _params()))
    changed = [i for i, (a, b) in enumerate(zip(raw, out)) if a != b]
    assert changed and all(FONT_START <= i < FONT_END for i in changed)
