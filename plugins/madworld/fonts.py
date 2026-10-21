"""The two message fonts (subtitles, headings) as glyph grids: harvested from the English atlases, drawn anew for the
Ukrainian letters, and read back from the translation's grid when a glyph was edited.

A grid cell is ``(w, h, alpha, intensity)``. The metrics of each character (ink width, height, advance and line
height as the game stored them) are kept so a glyph the game already had keeps its spacing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from . import gx, messages

UKR_LETTERS = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
COLUMNS = 16
STYLES = ("subtitle", "heading")


def harvest_fonts(units: List[Tuple[dict, dict]]) -> Dict[str, Dict[str, tuple]]:
    """``{style: {char: (w, h, alpha, intensity, advance, line height)}}`` from the first picture of each glyph."""
    fonts: Dict[str, Dict[str, tuple]] = {}
    for atlas, chars in units:
        for idx, (ch, style) in chars.items():
            g = atlas["glyphs"][idx]
            pal = atlas["pages"][g[5]][3]
            font = fonts.setdefault(style, {})
            if ch not in font and g[0] and g[1]:
                font[ch] = (g[0], g[1], messages.alpha_of(g, pal), messages.inten_of(g, pal), g[3], g[4])
    return fonts


def font_index(fonts: Dict[str, Dict[str, tuple]]) -> Dict[str, dict]:
    """``{style: {"cell", "columns", "chars", "metrics"}}``: the grid layout of each font."""
    index = {}
    for style, glyphs in sorted(fonts.items()):
        chars = "".join(sorted(glyphs)) + "".join(c for c in UKR_LETTERS if c not in glyphs)
        cw = max(g[0] for g in glyphs.values()) + 2
        ch = max(g[1] for g in glyphs.values())
        index[style] = {"cell": [cw, ch], "columns": COLUMNS, "chars": chars,
                        "metrics": {c: [g[0], g[1], g[4], g[5]] for c, g in glyphs.items()}}
    return index


def grid_bytes(fonts: Dict[str, Dict[str, tuple]], index: Dict[str, dict]) -> Dict[str, bytes]:
    """The TPL of each font's grid, ``{style: bytes}``."""
    out = {}
    for style, info in index.items():
        glyphs = fonts[style]
        cells = [glyphs[c][:4] if c in glyphs else None for c in info["chars"]]
        out[style] = gx.grid_write_ia(cells, tuple(info["cell"]), info["columns"])
    return out


class Grids:
    """The font grids of a translation: the translation's file where it has one, else the source's."""

    def __init__(self, index: Dict[str, dict], source: Path, translation: Optional[Path]) -> None:
        self.index = index
        self.source = source
        self.translation = translation
        self._cache: Dict[str, list] = {}

    def _path(self, style: str) -> Path:
        rel = Path("font") / f"font_{style}.tpl"
        if self.translation is not None and (self.translation / rel).is_file():
            return self.translation / rel
        return self.source / rel

    def cells(self, style: str) -> list:
        if style not in self._cache:
            info = self.index[style]
            self._cache[style] = gx.grid_read_ia(self._path(style).read_bytes(), tuple(info["cell"]),
                                                 info["columns"], len(info["chars"]))
        return self._cache[style]

    def glyph(self, style: str, ch: str) -> Optional[tuple]:
        """``(w, h, alpha, intensity, advance, line height)`` of ``ch`` in the grid, or None for an empty cell."""
        info = self.index.get(style)
        if not info or ch not in info["chars"]:
            return None
        cw, chh, alpha, inten = self.cells(style)[info["chars"].index(ch)]
        right, bottom = gx.ink_box(alpha, cw, chh)
        if not right:
            return None
        m = info["metrics"].get(ch)
        w = max(right, m[0]) if m else right
        h = m[1] if m else bottom

        def cut(b: bytes) -> bytes:
            return b"".join(b[r * cw:r * cw + w] for r in range(h))

        adv = m[2] if m and right <= m[0] else right + 2
        line = m[3] if m else max(v[3] for v in info["metrics"].values())
        return (w, h, cut(alpha), cut(inten), adv, line)

    def edited(self, style: str) -> Set[str]:
        """The characters whose cells the translation's grid changes against the source's grid."""
        if self.translation is None:
            return set()
        rel = Path("font") / f"font_{style}.tpl"
        new, old = self.translation / rel, self.source / rel
        if not new.is_file() or new.read_bytes() == old.read_bytes():
            return set()
        info = self.index[style]
        a = gx.grid_read_ia(new.read_bytes(), tuple(info["cell"]), info["columns"], len(info["chars"]))
        b = gx.grid_read_ia(old.read_bytes(), tuple(info["cell"]), info["columns"], len(info["chars"]))
        return {c for c, x, y in zip(info["chars"], a, b) if x[2:] != y[2:]}
