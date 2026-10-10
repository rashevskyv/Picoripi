"""Plain TrueType fonts (core/font_formats/ttf.py) on a real Unity font exported from a game (skipped where the file is
not on this machine): unchanged packing gives the same bytes, a copied-shape alias is written into the cmap."""
from pathlib import Path

import pytest

from core.font_formats import bfotf, char_map, ttf  # noqa: F401

FONT = Path(r"E:\Emulators\RomHacking\Bravely\Default\PC\source\font\SE-MLSEU.ttf")
PARAMS = {"size": 24}


def _need(path: Path) -> Path:
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_unchanged_font_packs_back_to_the_same_bytes():
    data = _need(FONT).read_bytes()
    metadata, sheets = ttf.extract(data, PARAMS)
    assert ttf.pack(metadata, sheets, data, PARAMS) == data
    assert metadata["header"]["format"] == "ttf"


def test_missing_ukrainian_letters_are_copied_from_look_alikes():
    data = _need(FONT).read_bytes()
    metadata, sheets = ttf.extract(data, PARAMS)
    assert ttf.missing(metadata, "ІіЇї") == "ІіЇї"
    edited = ttf.alias(metadata, {"І": "I", "і": "i", "Ї": "I", "ї": "i"})
    packed = ttf.pack(edited, sheets, data, PARAMS)
    assert packed != data
    cmap = bfotf.OpenType(packed).cmap()
    glyph = {char: cmap[ord(char)] for char in "IiІіЇї"}
    assert glyph["І"] == glyph["I"] and glyph["і"] == glyph["i"]
    assert glyph["Ї"] == glyph["I"] and glyph["ї"] == glyph["i"]
    again, _ = ttf.extract(packed, PARAMS)
    assert ttf.missing(again, "Іі") == ""


def test_alias_refuses_a_letter_the_font_does_not_have():
    data = _need(FONT).read_bytes()
    metadata, _sheets = ttf.extract(data, PARAMS)
    assert "Ж" not in char_map(metadata)
    with pytest.raises(ValueError):
        ttf.alias(metadata, {"Ґ": "Ж"})
