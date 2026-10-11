"""Paper Mario (N64) message font: the charset glyph sheet opens in the Font Editor's format and packs back to
the same bytes unedited; a changed glyph lands in its own cell (skipped where the workspace is not here)."""
import json
from pathlib import Path

import pytest

from core import font_formats

PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "paper_mario_64"
FONT_FILE = Path(r"E:\Emulators\RomHacking\Paper Mario\Paper Mario 64\N64-PC-port with ISO\source\font\charset_standard.bin")


def _descriptor():
    return json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))[0]


def test_font_descriptor_has_166_cells_and_16x16():
    entry = _descriptor()
    assert entry["format"] == "texture_grid"
    assert entry["params"]["cell"] == [16, 16]
    assert len(entry["params"]["chars"]) == 166


def test_unedited_font_packs_back_byte_exact():
    if not FONT_FILE.is_file():
        pytest.skip("the Paper Mario workspace is not on this machine")
    params = _descriptor()["params"]
    data = FONT_FILE.read_bytes()
    metadata, sheets = font_formats.extract("texture_grid", data, params)
    assert font_formats.pack("texture_grid", metadata, sheets, data, params) == data
