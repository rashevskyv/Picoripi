"""The message window of a Pokémon generation IV game, as the game draws it: the text box, from facts.

Facts (pret decomp, used for numbers only; no code or text is copied):
  - The message font is a Gen 4 font bin (``core.font_formats.gen4_glyphs``): 16 x 16 glyphs, advance widths in its
    WID table. ``WINDOWS`` gives its place per game code. Platinum's is pl_font.narc member 1 (the message font).
  - A message box is 4 tiles (32 px) high: a line is 16 px high and there is no line spacing, so a box shows 2 lines.
  - The text code of a character is its glyph index + 1; ``\\n`` (E000) breaks a line, ``\\r`` (25BC) ends a page.
  - The renderer does not wrap lines: a line wider than the box runs past its edge. The preview marks such a line.

``WindowResolver`` reads the game code and the font on a worker thread (AGENTS rule 5). The widget draws when the
result arrives.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QRect, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from core.containers.narc_members import narc_members
from core.font_formats import gen4_glyphs
from core.i18n import tr
from plugins.common import gen4msg
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread

LINE_PX = 16
# Palette of the message box, read from an emulator frame of the Diamond intro box (exact RGB): level 1 is the
# dark ink, level 2 the grey ink, level 3 the box colour.
BOX_RGB = (251, 251, 251)
INK = {1: QColor(81, 81, 89), 2: QColor(162, 162, 170), 3: QColor(*BOX_RGB)}
LINES_PER_PAGE = 2
SCALE = 2
WIDEST_BOX_PX = 216
_CHARMAPS = Path(__file__).resolve().parent / "charmaps"
_TAG = re.compile(r"\{[^{}]*\}")
_PLAYER = "PLAYER"


@dataclass(frozen=True)
class Window:
    """Where the message font is (a NARC path in the unpacked source and a member) and how wide the box is."""
    font_narc: str
    font_member: int
    box_px: int


# Game code (ROM header) -> window. Box widths: 27 x 4 tiles in all five games (pret pokediamond
# arm9/src/text_02054590.c, ctrl-cheeb-del pokeheartgold src/dialog_box.c); font member 1 is fontId 1.
WINDOWS: Dict[str, Window] = {
    "CPUE": Window("graphic/pl_font.narc", 1, 216),   # Platinum
    "ADAE": Window("graphic/font.narc", 1, 216),      # Diamond
    "APAE": Window("graphic/font.narc", 1, 216),      # Pearl
    "IPKE": Window("a/0/1/6", 1, 216),                # HeartGold
    "IPGE": Window("a/0/1/6", 1, 216),                # SoulSilver
}


@dataclass(frozen=True)
class Resolved:
    window: Window
    font: Optional[bytes]    # None: the font is not in the unpacked source
    charmap: str


def game_code(source_dir: str) -> Optional[str]:
    """The game code of the clean image the unpack kept (``rom/base.nds``), or None."""
    path = Path(source_dir) / "rom" / "base.nds"
    if not path.is_file():
        return None
    with open(path, "rb") as stream:
        code = stream.read(0x10)[0x0C:0x10]
    return code.decode("ascii", "replace")


def load_font(source_dir: str, narc_path: str, member: int) -> Optional[bytes]:
    """The font bin of ``member`` in the unpacked NARC, or None when the workspace has none."""
    path = Path(source_dir) / narc_path.replace("/", os.sep)
    if not path.is_file():
        return None
    members = narc_members(path.read_bytes())
    if member >= len(members) or not gen4_glyphs.is_font_bin(members[member]):
        return None
    return members[member]


def charmap_for(source_dir: str) -> str:
    """Platinum has pl_msg banks; the other Gen 4 games use the Diamond / Pearl / HeartGold table."""
    if source_dir and (Path(source_dir) / "text" / "msgdata+pl_msg.narc").is_dir():
        return str(_CHARMAPS / "charmap_platinum.txt")
    return str(_CHARMAPS / "charmap_dp_hgss.txt")


def resolve(source_dir: str) -> Optional[Resolved]:
    """The window facts and the font of a project folder; None for a game without facts."""
    code = game_code(source_dir)
    window = WINDOWS.get(code) if code else None
    if window is None:
        return None
    font = load_font(source_dir, window.font_narc, window.font_member)
    return Resolved(window, font, charmap_for(source_dir))


class WindowResolver(WorkerThread):
    """Reads a project's window facts and font off the UI thread. ``resolved`` carries (folder, Resolved or None)."""

    resolved = pyqtSignal(object)

    def __init__(self, source_dir: str):
        super().__init__()
        self._source_dir = source_dir
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            result = resolve(self._source_dir)
        except (OSError, ValueError) as exc:
            log_debug(f"pokemon_gen4: no window facts for {self._source_dir}: {exc}")
            result = None
        if not self._stop.is_set():
            self.resolved.emit((self._source_dir, result))


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
    """The message box of one project. It draws with the game's font once ``receive`` gets the resolved facts.

    Until then it shows only the empty box. ``refresh`` draws it again; ``update_preview_text`` takes new text.
    """

    def __init__(self, source_dir: str):
        super().__init__()
        self._root = source_dir
        self._box_px = WIDEST_BOX_PX
        self._codec: Optional[gen4msg.Codec] = None
        self._widths: List[int] = []
        self._font: Optional[bytes] = None
        self._glyphs: Dict[int, List[List[int]]] = {}
        self._text = ""
        self._note = tr("Reading the game font...")
        self._overflow = False
        self._more = False
        self._image = QImage(WIDEST_BOX_PX * SCALE, LINES_PER_PAGE * LINE_PX * SCALE, QImage.Format.Format_ARGB32)
        self.setMinimumSize(WIDEST_BOX_PX * SCALE + 20, LINES_PER_PAGE * LINE_PX * SCALE + 46)
        self._render()

    # -- font ----------------------------------------------------------------------------------------------------

    def receive(self, payload: object) -> None:
        """Takes the (folder, Resolved or None) of a ``WindowResolver``. Another folder's result is ignored."""
        source_dir, resolved = payload
        if source_dir != self._root:
            return
        self._glyphs.clear()
        if resolved is None:
            self._note = tr("This game has no message window facts.")
        elif resolved.font is None:
            self._note = tr("The game font is not in this project.")
        else:
            self._note = ""
            self._box_px = resolved.window.box_px
            self._font = resolved.font
            self._widths = gen4_glyphs.glyph_widths(resolved.font)
            self._codec = gen4msg.Codec(resolved.charmap)
        self._render()

    def _width_of(self, ch: str) -> Optional[int]:
        if self._codec is None:
            return None
        code = self._codec.char_codes.get(ch)
        if code is None:
            return None
        index = code - 1
        return self._widths[index] if 0 <= index < len(self._widths) else None

    def _glyph(self, ch: str) -> Optional[List[List[int]]]:
        if self._codec is None:
            return None
        code = self._codec.char_codes.get(ch)
        if code is None or not 0 <= code - 1 < len(self._widths):
            return None
        if code - 1 not in self._glyphs:
            self._glyphs[code - 1] = gen4_glyphs.glyph_levels(self._font, code - 1)
        return self._glyphs[code - 1]

    # -- drawing -------------------------------------------------------------------------------------------------

    def _render(self) -> None:
        image = QImage(self._box_px * SCALE, LINES_PER_PAGE * LINE_PX * SCALE, QImage.Format.Format_ARGB32)
        image.fill(QColor(0, 0, 0, 0))
        lines, more = page_lines(self._text)
        self._more = more
        self._overflow = False
        ink = INK
        for row, chars in enumerate(lines):
            x = 0
            if line_width([c for c in chars if c], self._width_of) > self._box_px:
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
        box = QRect(left - 4, top - 4, self._box_px * SCALE + 8, LINES_PER_PAGE * LINE_PX * SCALE + 8)
        painter.fillRect(box, QColor(*BOX_RGB))
        painter.setPen(QPen(QColor(20, 20, 20), 2))
        painter.drawRect(box)
        painter.drawImage(left, top, self._image)
        painter.setPen(QColor(230, 230, 230))
        notes = [self._note] if self._note else []
        if self._overflow:
            notes.append(tr("A line is wider than the box."))
        if self._more:
            notes.append(tr("More text follows on the next page or line."))
        painter.setFont(QFont(painter.font().family(), 9))
        y = top + LINES_PER_PAGE * LINE_PX * SCALE + 18
        for text in notes:
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


__all__ = ["MessageWindowPreview", "Resolved", "Window", "WindowResolver", "WINDOWS", "charmap_for", "game_code",
           "load_font", "page_lines", "resolve", "LINE_PX", "LINES_PER_PAGE", "WIDEST_BOX_PX"]
