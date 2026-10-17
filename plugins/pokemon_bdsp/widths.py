"""Word widths of the Brilliant Diamond / Shining Pearl message labels: ``strWidth`` of each word of an edited label.

A word's width is the sum of the glyph advances of its characters at 32 pt, from the English TextMesh Pro fonts (their
glyph and character tables). A character the tables lack is measured with the fallback font file. ``<size=N%>`` scales
the words after it, as the game does. Words with a negative width (tags, waits) keep their value.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Callable, Dict, Optional

from PIL import ImageFont

WIDTH_FONTS = ("font/efigs_font/efigs_font.json", "font/efigs_font/or_font.json")
FALLBACK_FONT = "font/efigs_font/FOT-UDKakugoC80Pro-DB.otf"
SIZE = 32
_SCALE = re.compile(r"<size=(\d+(?:\.\d+)?)%>")


class Widths:
    """Measures words with the fonts ``pick(rel)`` returns (a path or None), translation first, then the source."""

    def __init__(self, pick: Callable[[str], Optional[Path]]):
        self.advance: Dict[str, float] = {}
        for rel in WIDTH_FONTS:
            path = pick(rel)
            if path is None:
                continue
            tree = json.loads(path.read_text(encoding="utf-8"))
            glyphs = {g["m_Index"]: g["m_Metrics"]["m_HorizontalAdvance"] for g in tree["m_GlyphTable"]}
            for char in tree["m_CharacterTable"]:
                self.advance.setdefault(chr(char["m_Unicode"]), glyphs.get(char["m_GlyphIndex"], 0.0))
        fallback = pick(FALLBACK_FONT)
        self.fallback = (ImageFont.truetype(io.BytesIO(fallback.read_bytes()), SIZE,
                                            layout_engine=ImageFont.Layout.BASIC) if fallback else None)

    def char(self, char: str) -> float:
        if char in self.advance:
            return self.advance[char]
        width = self.fallback.getlength(char) if self.fallback else 0.0
        self.advance[char] = width
        return width

    def label(self, label: dict) -> None:
        """Set ``strWidth`` of every measured word of ``label`` (in place)."""
        scale = 1.0
        for word in label["wordDataArray"]:
            if word["patternID"] == 3:
                size = _SCALE.match(word["str"])
                scale = float(size.group(1)) / 100 if size else 1.0
            if word["strWidth"] >= 0:
                word["strWidth"] = sum(self.char(c) for c in word["str"]) * scale


def edited_labels(value: dict, old: dict) -> list:
    """The labels of a table that differ from the same-named labels of the source table."""
    old_labels = {label["labelName"]: label for label in old.get("labelDataArray", [])}
    return [label for label in value.get("labelDataArray", []) if label != old_labels.get(label["labelName"])]
