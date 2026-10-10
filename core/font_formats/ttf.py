"""Plain TrueType / OpenType font files (a Unity Font's data, a PC game's .ttf or .otf): the glyph model of ``bfotf``.

The file is read as it is (no scrambling). Extract and pack are ``bfotf``'s: every mapped character is drawn into a
sheet, widths and redrawn glyphs are written back, and a character map change is written into the font's cmap.
Characters the font does not have are added with ``alias``: the new code point points at a glyph the font already
has (a look-alike shape that is copied, not drawn). A translator can then type those letters; the glyph looks like
its source until a real shape is drawn.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from core.font_formats import Metadata, Sheets, char_code, char_map, map_entries
from core.font_formats import bfotf


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    metadata, sheets = bfotf.extract(bytes(data), dict(params or {}))
    metadata["header"]["format"] = "ttf"
    return metadata, sheets


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    return bfotf.pack(metadata, sheets, bytes(original), dict(params or {}))


def missing(metadata: Metadata, chars: str) -> str:
    """The characters of ``chars`` the font does not map."""
    have = char_map(metadata)
    return "".join(char for char in chars if char not in have)


def alias(metadata: Metadata, pairs: Dict[str, str]) -> Metadata:
    """A copy of ``metadata`` where each character of ``pairs`` (key) is mapped to the glyph of another character
    the font has (value). Raises ValueError when the value is not mapped either."""
    have = char_map(metadata)
    entries = {char_code(char): cell for char, cell in have.items()}
    for char, like in pairs.items():
        if like not in have:
            raise ValueError(f"the font has no glyph for {like!r}; cannot copy its shape to {char!r}")
        entries[char_code(char)] = have[like]
    out = dict(metadata)
    out["MAP1"] = [map_entries(sorted(entries.items()))]
    out["header"] = dict(metadata["header"])
    return out
