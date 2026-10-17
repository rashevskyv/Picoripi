"""The text font of a Game Boy Pokemon game (Generation I and II), read from the ROM at the facts' addresses.

The main font is 1bpp: 8 bytes a tile, one bit a pixel (1 is ink), starting at the code ``code``. The extra font
(quotes, ellipsis, box frame) is 2bpp: 16 bytes a tile, the low plane then the high plane; shade 3 is ink and 0 is
paper. A glyph is one 8 x 8 cell, because the game's text has no proportional widths. A code outside both fonts
draws as a blank cell. The facts file holds ``font`` with ``tiles_1bpp`` and ``tiles_2bpp`` (``at``, ``count``,
``code``) and ``window``; tools/pokemon_gb_font_facts.py writes them.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core.i18n import tr
from plugins.common import text_window_preview as tw
from plugins.common.gba_text_font import INK, PAPER, SHADOW

CELL = 8
BYTES_1BPP = 8
BYTES_2BPP = 16
SHADE_CLASS = {0: PAPER, 1: SHADOW, 2: SHADOW, 3: INK}
# The box frame is drawn with these characters of the extra font (top-left, horizontal, top-right, vertical...).
FRAME_CHARS = {"tl": "┌", "h": "─", "tr": "┐", "v": "│", "bl": "└", "br": "┘"}


def decode_1bpp(tile: bytes) -> List[List[int]]:
    """The 8 x 8 pixel classes of a 1bpp tile: a set bit is ink, the leftmost pixel is the top bit."""
    return [[INK if (tile[y] >> (7 - x)) & 1 else PAPER for x in range(CELL)] for y in range(CELL)]


def decode_2bpp(tile: bytes) -> List[List[int]]:
    """The 8 x 8 pixel classes of a 2bpp tile: each row is a low byte and a high byte."""
    rows = []
    for y in range(CELL):
        low, high = tile[2 * y], tile[2 * y + 1]
        rows.append([SHADE_CLASS[(((high >> (7 - x)) & 1) << 1) | ((low >> (7 - x)) & 1)] for x in range(CELL)])
    return rows


class GbGlyphSet:
    """The glyphs of one Game Boy font. ``code`` is the text byte; every cell is 8 pixels wide."""

    def __init__(self, main_code: int, main: bytes, extra_code: int, extra: bytes) -> None:
        self._main_code, self._main = main_code, main
        self._extra_code, self._extra = extra_code, extra
        self._cache: Dict[int, List[List[int]]] = {}

    @property
    def count(self) -> int:
        return len(self._main) // BYTES_1BPP

    def width(self, code: int) -> int:
        return CELL

    def drawn_width(self, code: int) -> int:
        return CELL

    def pixels(self, code: int) -> List[List[int]]:
        if code not in self._cache:
            self._cache[code] = self._decode(code)
        return self._cache[code]

    def _decode(self, code: int) -> List[List[int]]:
        index = code - self._main_code
        if 0 <= index < self.count:
            return decode_1bpp(self._main[index * BYTES_1BPP:(index + 1) * BYTES_1BPP])
        index = code - self._extra_code
        if 0 <= index < len(self._extra) // BYTES_2BPP:
            return decode_2bpp(self._extra[index * BYTES_2BPP:(index + 1) * BYTES_2BPP])
        return [[PAPER] * CELL for _ in range(CELL)]


def read_gb_glyph_set(rom_path: Path, font: Dict[str, Any]) -> GbGlyphSet:
    """Read the two tile blocks from the ROM (a few kilobytes; call it from a worker thread)."""
    main, extra = font["tiles_1bpp"], font["tiles_2bpp"]
    with open(rom_path, "rb") as handle:
        handle.seek(int(main["at"]))
        one = handle.read(int(main["count"]) * BYTES_1BPP)
        handle.seek(int(extra["at"]))
        two = handle.read(int(extra["count"]) * BYTES_2BPP)
    if len(one) != int(main["count"]) * BYTES_1BPP or len(two) != int(extra["count"]) * BYTES_2BPP:
        raise ValueError("the ROM ends before the font tiles")
    return GbGlyphSet(int(main["code"]), one, int(extra["code"]), two)


def load_gb_context(rom_dir: Path, facts_dir: Path, base_rom: str, meta: str) -> tw.FontContext:
    """The preview context of an unpacked Game Boy project: its font, its charmap and its text box."""
    info = json.loads((rom_dir / meta).read_text(encoding="utf-8"))
    facts = json.loads((facts_dir / info["facts"]).read_text(encoding="utf-8"))
    font = facts.get("font")
    if not font:
        raise ValueError(tr("The font of this game is not in its facts yet."))
    byte_of: Dict[str, int] = {}
    for char, code in facts["charmap"]:
        byte_of.setdefault(str(char), int(code))
    window = dict(font["window"])
    window["frame"] = {key: byte_of[char] for key, char in FRAME_CHARS.items() if char in byte_of}
    glyphs = read_gb_glyph_set(rom_dir / base_rom, font)
    return tw.FontContext(glyphs, tw.CodeTable(byte_of), tw.Window.from_facts(window))
