"""The message box of a Pokémon Sun / Moon (3DS, generation 7) game, drawn with the game's own font.

Facts (measured on an Azahar frame of the language screen; kept in ``config.json`` under ``message_window``):
  - The message font is ``romfs/a/0/2/5/000.bffnt`` (FFNT, 15 x 19 px cells, no spacing). A glyph advances by its
    WID1 width. Line 1 of the language screen is 255 px wide in the frame; the font gives 255 px.
  - The text starts at x 9 and the first line's cell top is at y 10. A line is 20 px high.
  - The editor text is drawn as the game draws it: a newline starts a line, ``{PAGE}`` ends a page,
    ``{COLOR 0001}`` is red and ``{COLOR 0000}`` is white again. The game breaks the lines itself.

``WindowResolver`` reads the font on a worker thread (AGENTS rule 5). The widget draws when the result arrives.
Only the language-screen box is measured so far; other windows need their own frame before their facts change.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtWidgets import QWidget

from core.bfn_core import char_to_glyph
from core.font_formats import bcfnt
from core.i18n import tr
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread

FONT_MEMBER = "romfs/a/0/2/5/000.bffnt"
SCALE = 2
_CONFIG = Path(__file__).resolve().parent / "config.json"
_TAG = re.compile(r"\{([A-Z]+)([^{}]*)\}")
# The editor shows the game's apostrophe (font code 0x27) as a curly quote; the font has no glyph for the curly one.
_SAME_GLYPH = {"’": "'", "‘": "'"}
_WHITE = (240, 240, 240, 255)
_RED = (255, 70, 70, 255)
_BOX = (24, 26, 28, 235)
_EDGE = (200, 200, 200, 255)


@dataclass(frozen=True)
class BoxFacts:
    """Where the text sits in the box, read from ``config.json`` (``message_window``)."""
    font_member: str
    text_x: int
    first_line_top: int
    line_pitch: int
    text_width: int
    box_lines: int

    @classmethod
    def load(cls, path: Path = _CONFIG) -> "BoxFacts":
        raw = json.loads(path.read_text(encoding="utf-8"))["message_window"]
        return cls(raw["font_member"], int(raw["text_x"]), int(raw["first_line_top"]), int(raw["line_pitch"]),
                   int(raw["text_width"]), int(raw["box_lines"]))


class BoxFont:
    """A FFNT font decoded for drawing: glyph cells, advances and the character map."""

    def __init__(self, sheets: List[Image.Image], cell: Tuple[int, int], grid: Tuple[int, int],
                 cmap: Dict[int, int], advances: List[int]):
        self.sheets = sheets
        self.cell_w, self.cell_h = cell
        self.columns, self.rows = grid
        self.cmap = cmap
        self.advances = advances

    @classmethod
    def from_bytes(cls, data: bytes) -> "BoxFont":
        metadata, sheets = bcfnt.extract(data, {})
        gly = metadata["GLY1"][0]
        packets = metadata["WID1"][0]["packets"]
        return cls(sheets, (gly["cell_width"], gly["cell_height"]),
                   (gly["glyph_horizontal_count"], gly["glyph_vertical_count"]),
                   char_to_glyph(metadata["MAP1"]), [int(p["width"]) for p in packets])

    def glyph_of(self, ch: str) -> Optional[int]:
        g = self.cmap.get(ord(_SAME_GLYPH.get(ch, ch)))
        return g if g is not None and g < len(self.advances) else None

    def cell(self, glyph: int) -> Image.Image:
        per = self.columns * self.rows
        sheet, k = divmod(glyph, per)
        x, y = (k % self.columns) * self.cell_w, (k // self.columns) * self.cell_h
        return self.sheets[sheet].crop((x, y, x + self.cell_w, y + self.cell_h)).getchannel("A")

    def width(self, text: str) -> int:
        """The pen advance of a line. Characters the font does not have count as 0 px."""
        return sum(self.advances[g] for g in (self.glyph_of(c) for c in text) if g is not None)


def _plain(segment: str, colour: str) -> Tuple[str, str, str]:
    """``(plain text, colour at the start, colour at the end)``; every tag is dropped, ``{COLOR}`` changes colour."""
    out, pos, start, text_seen = [], 0, colour, False
    for m in _TAG.finditer(segment):
        out.append(segment[pos:m.start()])
        text_seen = text_seen or bool(segment[pos:m.start()])
        if m.group(1) == "COLOR":
            colour = "red" if m.group(2).strip() == "0001" else "white"
            if not text_seen:                      # a colour tag before the first letter sets the line's colour
                start = colour
        pos = m.end()
    out.append(segment[pos:])
    return "".join(out), start, colour


def split_pages(text: str) -> List[List[Tuple[str, str]]]:
    """Pages of lines. Each line is ``(plain text, colour)`` with ``colour`` 'white' or 'red'. ``{PAGE}`` starts a
    new page; a line that only ends in ``{PAGE}`` adds no empty line to the next page."""
    pages: List[List[Tuple[str, str]]] = [[]]
    colour = "white"
    for raw in (text or "").split("\n"):
        segments = raw.split("{PAGE}")
        for index, segment in enumerate(segments):
            if index:
                pages.append([])
            plain, start, colour = _plain(segment, colour)
            if index == len(segments) - 1 and len(segments) > 1 and plain == "":
                continue
            pages[-1].append((plain, start))
    return pages


def overflow_lines(page: List[Tuple[str, str]], font: BoxFont, facts: BoxFacts) -> List[int]:
    """Indexes of the lines of a page that are wider than the text width or that the box cannot show."""
    bad = [i for i, (line, _c) in enumerate(page) if font.width(line) > facts.text_width]
    if len(page) > facts.box_lines:
        bad += list(range(facts.box_lines, len(page)))
    return bad


def render_page(page: List[Tuple[str, str]], font: BoxFont, facts: BoxFacts) -> Image.Image:
    """The box with one page of text, as RGBA at native size (320 x 240 bottom screen)."""
    height = max(240, facts.first_line_top + facts.box_lines * facts.line_pitch + 8)
    out = Image.new("RGBA", (320, height), _BOX)
    ImageDraw.Draw(out).rectangle((0, 0, 319, height - 1), outline=_EDGE, width=2)
    for index, (line, colour) in enumerate(page):
        top = facts.first_line_top + index * facts.line_pitch
        if top >= height:
            break
        pen = facts.text_x
        ink = _RED if colour == "red" else _WHITE
        for ch in line:
            g = font.glyph_of(ch)
            if g is None:
                continue
            cell = font.cell(g)
            glyph = Image.new("RGBA", cell.size, ink)
            glyph.putalpha(cell)
            out.alpha_composite(glyph, (pen, top))
            pen += font.advances[g]
    return out


class Resolved:
    """The font of one project, read on the worker."""

    def __init__(self, font: BoxFont):
        self.font = font


class WindowResolver(WorkerThread):
    """Reads the project's message font off the UI thread. ``resolved`` carries (folder, Resolved or None)."""

    resolved = pyqtSignal(object)

    def __init__(self, source_dir: str):
        super().__init__()
        self._source_dir = source_dir
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        result = None
        try:
            path = Path(self._source_dir) / Path(FONT_MEMBER)
            result = Resolved(BoxFont.from_bytes(path.read_bytes()))
        except (OSError, ValueError, KeyError, IndexError) as exc:
            log_debug(f"pokemon_gen7: no message font for {self._source_dir}: {exc}")
        if not self._stop.is_set():
            self.resolved.emit((self._source_dir, result))


class MessageWindowPreview(QWidget):
    """The message box of one project. It draws with the game's font once ``receive`` gets the font."""

    def __init__(self, source_dir: str):
        super().__init__()
        self._root = source_dir
        self._facts = BoxFacts.load()
        self._font: Optional[BoxFont] = None
        self._text = ""
        self._note = tr("Reading the game font...")
        self._image = QImage(320 * SCALE, 240 * SCALE, QImage.Format.Format_ARGB32)
        self.setMinimumSize(320 * SCALE + 20, 240 * SCALE + 46)
        self._render()

    def receive(self, payload: object) -> None:
        """Takes the (folder, Resolved or None) of a ``WindowResolver``. Another folder's result is ignored."""
        source_dir, resolved = payload
        if source_dir != self._root:
            return
        if resolved is None:
            self._note = tr("The game font is not in this project.")
        else:
            self._font = resolved.font
            self._note = ""
        self._render()

    def _render(self) -> None:
        self._image.fill(QColor(0, 0, 0, 0))
        if self._font is None:
            self.update()
            return
        pages = split_pages(self._text)
        page = pages[0] if pages else []
        bad = overflow_lines(page, self._font, self._facts)
        img = render_page(page, self._font, self._facts).convert("RGBA")
        raw = img.tobytes("raw", "RGBA")
        frame = QImage(raw, img.width, img.height, img.width * 4, QImage.Format.Format_RGBA8888).copy()
        painter = QPainter(self._image)
        painter.scale(SCALE, SCALE)
        painter.drawImage(0, 0, frame)
        painter.end()
        self._note = tr("Line too wide for the box or too many lines: %1") % ", ".join(str(i + 1) for i in bad) \
            if bad else ""
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        painter.drawImage(10, 10, self._image)
        if self._note:
            painter.drawText(10, self.height() - 12, self._note)
        painter.end()

    def refresh(self) -> None:
        self._render()

    def update_preview_text(self, text: object = None, original: object = None) -> None:
        self._text = text if isinstance(text, str) else ""
        self._render()

    def shutdown(self) -> None:
        self._font = None


__all__ = ["BoxFacts", "BoxFont", "MessageWindowPreview", "Resolved", "WindowResolver", "overflow_lines",
           "render_page", "split_pages", "FONT_MEMBER"]
