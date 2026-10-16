"""The message window of a Pokémon generation IV game, as the game draws it: the text box of Platinum, from facts.

Facts (pret decomp pokeplatinum, used for numbers only; no code or text is copied):
  - FONT_MESSAGE is the font ``font_message.NFGR``, the second file of ``graphic/pl_font.narc`` (res/fonts/pl_font.order)
    and is a Gen 4 font bin (``core.font_formats.gen4_glyphs``): 16 x 16 glyphs, advance widths in its WID table.
  - The field message window is MESSAGE_WINDOW_TILE_W x MESSAGE_WINDOW_TILE_H = 27 x 4 tiles = 216 x 32 px
    (include/render_window.h); a line is 16 px high and there is no line spacing (src/font.c), so a box shows 2 lines.
  - The text code of a character is its glyph index + 1; ``\\n`` (E000) breaks a line, ``\\r`` (25BC) ends a page.
  - The renderer does not wrap lines (src/render_text.c): a line wider than the box runs past its edge. The preview
    marks such a line instead of wrapping it.

Only Platinum has these facts; other Gen 4 games get the BFN preview.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from core.containers.narc_members import narc_members
from core.font_formats import gen4_glyphs
from core.i18n import tr
from plugins.common import gen4msg

WINDOW_TILES = (27, 4)
TILE_PX = 8
LINE_PX = 16
LINES_PER_PAGE = WINDOW_TILES[1] * TILE_PX // LINE_PX
BOX_PX = WINDOW_TILES[0] * TILE_PX
FACTS = {
    # game code (ROM header) -> (font NARC path in the unpacked source, member index of the message font)
    "CPUE": ("graphic/pl_font.narc", 1),
}
SCALE = 2
_TAG = re.compile(r"\{[^{}]*\}")
_PLAYER = "PLAYER"


def facts_for(game_code: str) -> Optional[Tuple[str, int]]:
    return FACTS.get(game_code)


def page_lines(text: str, lines_per_page: int = LINES_PER_PAGE) -> Tuple[List[List[str]], bool]:
    """The first page of ``text`` as lines of glyph characters, and whether more text follows.

    Tags are shown as their placeholder (a player name) or not at all; they take no width.
    """
    raw = text.replace("\\r", "\r").replace("\\n", "\n")
    raw = _TAG.sub(lambda m: _PLAYER if m.group(0).upper().startswith("{STRVAR") else "", raw)
    pages = raw.split("\r")
    first = pages[0]
    lines = first.split("\n")
    shown = [list(line) for line in lines[:lines_per_page]]
    more = len(lines) > lines_per_page or any(p.strip() for p in pages[1:])
    return shown, more


def line_width(chars: List[str], width_of) -> int:
    total = 0
    for ch in chars:
        advance = width_of(ch)
        total += advance or 0
    return total


class MessageWindowPreview(QWidget):
    """The Platinum message box with the game's font, drawn from the unpacked font bin.

    It keeps the last text it was given. ``refresh`` draws it again; ``update_preview_text`` takes new text.
    """

    def __init__(self, font_bin: bytes, codec: gen4msg.Codec):
        super().__init__()
        self._font = font_bin
        self._codec = codec
        self._widths = gen4_glyphs.glyph_widths(font_bin)
        self._glyphs: Dict[int, List[List[int]]] = {}
        self._text = ""
        self._image = QImage(BOX_PX * SCALE, LINES_PER_PAGE * LINE_PX * SCALE, QImage.Format.Format_ARGB32)
        self._overflow = False
        self._more = False
        self.setMinimumSize(BOX_PX * SCALE + 20, LINES_PER_PAGE * LINE_PX * SCALE + 46)
        self._render()

    # -- font ----------------------------------------------------------------------------------------------------

    def _width_of(self, ch: str) -> Optional[int]:
        code = self._codec.char_codes.get(ch)
        if code is None:
            return None
        index = code - 1
        return self._widths[index] if 0 <= index < len(self._widths) else None

    def _glyph(self, ch: str) -> Optional[List[List[int]]]:
        code = self._codec.char_codes.get(ch)
        if code is None or not 0 <= code - 1 < len(self._widths):
            return None
        if code - 1 not in self._glyphs:
            self._glyphs[code - 1] = gen4_glyphs.glyph_levels(self._font, code - 1)
        return self._glyphs[code - 1]

    # -- drawing -------------------------------------------------------------------------------------------------

    def _render(self) -> None:
        image = QImage(BOX_PX * SCALE, LINES_PER_PAGE * LINE_PX * SCALE, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        lines, more = page_lines(self._text)
        self._more = more
        self._overflow = False
        ink = {3: QColor(0, 0, 0), 2: QColor(90, 90, 90), 1: QColor(170, 170, 170)}
        for row, chars in enumerate(lines):
            x = 0
            if line_width([c for c in chars if c], self._width_of) > BOX_PX:
                self._overflow = True
            for ch in chars:
                glyph = self._glyph(ch) if ch else None
                advance = self._width_of(ch) if ch else None
                if glyph is None:
                    if advance:
                        x += advance
                    continue
                for gy, levels in enumerate(glyph):
                    for gx, level in enumerate(levels):
                        if not level:
                            continue
                        colour = ink[level]
                        px, py = (x + gx) * SCALE, (row * LINE_PX + gy) * SCALE
                        for dy in range(SCALE):
                            for dx in range(SCALE):
                                if 0 <= px + dx < image.width() and 0 <= py + dy < image.height():
                                    image.setPixelColor(px + dx, py + dy, colour)
                x += advance or 0
        self._image = image
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 46))
        left, top = 10, 10
        box = QRect(left - 4, top - 4, BOX_PX * SCALE + 8, LINES_PER_PAGE * LINE_PX * SCALE + 8)
        painter.fillRect(box, QColor(246, 246, 242))
        painter.setPen(QPen(QColor(20, 20, 20), 2))
        painter.drawRect(box)
        painter.drawImage(left, top, self._image)
        painter.setPen(QColor(230, 230, 230))
        note = []
        if self._overflow:
            note.append(tr("A line is wider than the box (216 px)."))
        if self._more:
            note.append(tr("More text follows on the next page or line."))
        painter.setFont(QFont(painter.font().family(), 9))
        y = top + LINES_PER_PAGE * LINE_PX * SCALE + 18
        for text in note:
            painter.drawText(left, y, text)
            y += 16
        painter.end()

    # -- host interface ------------------------------------------------------------------------------------------

    def refresh(self) -> None:
        self._render()

    def update_preview_text(self, text: object = None, original: object = None) -> None:
        self._text = text if isinstance(text, str) else ""
        self._render()

    def shutdown(self) -> None:
        self._glyphs.clear()


def load_font(source_dir: str, narc_path: str, member: int) -> Optional[bytes]:
    """The font bin of ``member`` in the unpacked NARC, or None when the workspace has none."""
    path = Path(source_dir) / narc_path.replace("/", os.sep)
    if not path.is_file():
        return None
    members = narc_members(path.read_bytes())
    if member >= len(members) or not gen4_glyphs.is_font_bin(members[member]):
        return None
    return members[member]


def game_code(source_dir: str) -> Optional[str]:
    """The game code of the clean image the unpack kept (``rom/base.nds``), or None."""
    path = Path(source_dir) / "rom" / "base.nds"
    if not path.is_file():
        return None
    with open(path, "rb") as stream:
        code = stream.read(0x10)[0x0C:0x10]
    return code.decode("ascii", "replace")


__all__ = ["MessageWindowPreview", "facts_for", "game_code", "load_font", "page_lines", "BOX_PX", "LINE_PX",
           "LINES_PER_PAGE"]
