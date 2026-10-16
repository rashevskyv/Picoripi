"""The message box of a Pokémon game drawn with the game's own bitmap font (FFNT or CFNT, read by ``core.font_formats``).

One renderer for every 3DS Pokémon plugin. The facts of each game (font member, text origin, line pitch, glyph scale,
box lines) live in that plugin's ``config.json`` under a named window, and are read with ``BoxFacts.load``.

Facts are measured on Azahar frames (see the ``measured_on`` note of each window). Glyph scale: the game draws a font
at ``scale_x`` / ``scale_y`` of its cell size; the advance of a glyph is its WID1 width times ``scale_x``.

``WindowResolver`` reads the font on a worker thread (AGENTS rule 5). The widget draws when the result arrives.
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
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QWidget

from core.bfn_core import char_to_glyph
from core.font_formats import bcfnt, pmd_font
from core.font_formats.sources import join_pair
from core.i18n import tr
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread

SCALE = 2                                  # on-screen zoom of the widget; the box itself is drawn at native size
_TAG = re.compile(r"\{([A-Z]+)([^{}]*)\}")
# The editor shows the game's apostrophe (font code 0x27) as a curly quote; the font has no glyph for the curly one.
_SAME_GLYPH = {"’": "'", "‘": "'"}
_WHITE = (240, 240, 240, 255)
_RED = (255, 70, 70, 255)
_BOX = (24, 26, 28, 235)
_EDGE = (200, 200, 200, 255)
_HEIGHT = 240                              # every 3DS screen is 240 px high


@dataclass(frozen=True)
class BoxFacts:
    """Where the text sits in the box, read from a plugin's ``config.json`` window."""
    font_member: str
    text_x: int
    first_line_top: int
    line_pitch: float
    text_width: int                 # 0: not measured, the width is not checked
    box_lines: int
    screen_width: int = 320         # 320: bottom screen; 400: top screen
    draw_box: bool = True           # the language screen has a box; the dialogue text sits on the scene
    scale_x: float = 1.0            # glyph scale of the game's text pane (1.0: the cell as stored)
    scale_y: float = 1.0
    ink: Tuple[int, int, int, int] = _WHITE     # text colour
    red: Tuple[int, int, int, int] = _RED       # the colour of {COLOR 0001}
    box: Tuple[int, int, int, int] = _BOX       # the box fill, drawn only when draw_box
    edge: Tuple[int, int, int, int] = _EDGE     # the box border
    box_rect: Optional[Tuple[int, int, int, int]] = None   # a box inside the screen (x0, y0, x1, y1, inclusive)
    font_companion: str = ""        # the atlas of a Spike Chunsoft font (font_member is then the .dic)

    @classmethod
    def load(cls, config: Path, window: str) -> "BoxFacts":
        raw = json.loads(Path(config).read_text(encoding="utf-8"))[window]
        return cls(raw["font_member"], int(raw["text_x"]), int(raw["first_line_top"]), float(raw["line_pitch"]),
                   int(raw["text_width"]), int(raw["box_lines"]), int(raw.get("screen_width", 320)),
                   bool(raw.get("draw_box", True)), float(raw.get("scale_x", 1.0)), float(raw.get("scale_y", 1.0)),
                   _colour(raw.get("ink_rgb"), _WHITE), _colour(raw.get("red_rgb"), _RED),
                   _colour(raw.get("box_rgba"), _BOX), _colour(raw.get("edge_rgb"), _EDGE),
                   _rect(raw.get("box_rect")), str(raw.get("font_companion", "")))


def _rect(value: Optional[List[int]]) -> Optional[Tuple[int, int, int, int]]:
    """A config rectangle ``[x0, y0, x1, y1]`` (inclusive corners); None: the box covers the whole screen."""
    if value is None:
        return None
    x0, y0, x1, y1 = (int(v) for v in value)
    return (x0, y0, x1, y1)


def _colour(value: Optional[List[int]], default: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    """A config colour: ``[r, g, b]`` (opaque) or ``[r, g, b, a]``; None keeps the default."""
    if value is None:
        return default
    rgba = [int(v) for v in value]
    return (rgba[0], rgba[1], rgba[2], rgba[3] if len(rgba) > 3 else 255)


class BoxFont:
    """A bitmap font decoded for drawing: glyph cells, advances and the character map."""

    def __init__(self, sheets: List[Image.Image], cell: Tuple[int, int], grid: Tuple[int, int],
                 cmap: Dict[int, int], advances: List[int], kerning: Optional[List[int]] = None):
        self.sheets = sheets
        self.cell_w, self.cell_h = cell
        self.columns, self.rows = grid
        self.cmap = cmap
        self.advances = advances
        self.kerning = kerning or [0] * len(advances)   # the ink starts this many px left of the pen

    @classmethod
    def from_bytes(cls, data: bytes) -> "BoxFont":
        """A CTR font (CFNT or FFNT, read by ``core.font_formats.bcfnt``)."""
        return cls.from_metadata(*bcfnt.extract(data, {}))

    @classmethod
    def from_pair(cls, dic: bytes, img: bytes) -> "BoxFont":
        """A Spike Chunsoft font: the ``.dic`` entries and the ``.img`` atlas (``core.font_formats.pmd_font``)."""
        return cls.from_metadata(*pmd_font.extract(join_pair(dic, img), {}))

    @classmethod
    def from_metadata(cls, metadata, sheets) -> "BoxFont":
        gly = metadata["GLY1"][0]
        packets = metadata["WID1"][0]["packets"]
        return cls(sheets, (gly["cell_width"], gly["cell_height"]),
                   (gly["glyph_horizontal_count"], gly["glyph_vertical_count"]),
                   char_to_glyph(metadata["MAP1"]), [int(p["width"]) for p in packets],
                   [-int(p.get("kerning", 0)) for p in packets])

    def glyph_of(self, ch: str) -> Optional[int]:
        g = self.cmap.get(ord(_SAME_GLYPH.get(ch, ch)))
        return g if g is not None and g < len(self.advances) else None

    def cell(self, glyph: int, scale_x: float = 1.0, scale_y: float = 1.0) -> Image.Image:
        """The alpha mask of one glyph, scaled as the game draws it."""
        per = self.columns * self.rows
        sheet, k = divmod(glyph, per)
        x, y = (k % self.columns) * self.cell_w, (k // self.columns) * self.cell_h
        mask = self.sheets[sheet].crop((x, y, x + self.cell_w, y + self.cell_h)).getchannel("A")
        if scale_x == 1.0 and scale_y == 1.0:
            return mask
        return mask.resize((max(1, round(self.cell_w * scale_x)), max(1, round(self.cell_h * scale_y))), Image.BILINEAR)

    def width(self, text: str) -> int:
        """The pen advance of a line in font pixels. Characters the font does not have count as 0 px."""
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
    bad = [i for i, (line, _c) in enumerate(page)
           if facts.text_width > 0 and font.width(line) * facts.scale_x > facts.text_width]
    if len(page) > facts.box_lines:
        bad += list(range(facts.box_lines, len(page)))
    return bad


def render_page(page: List[Tuple[str, str]], font: BoxFont, facts: BoxFacts) -> Image.Image:
    """One page of text at native size on its screen (``facts.screen_width`` x 240), boxed when the window is a box."""
    width = facts.screen_width
    out = Image.new("RGBA", (width, _HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)
    if facts.box_rect is not None:
        draw.rectangle(facts.box_rect, fill=facts.box, outline=facts.edge, width=2)
    elif facts.draw_box:
        out.paste(facts.box, (0, 0, width, _HEIGHT))
        draw.rectangle((0, 0, width - 1, _HEIGHT - 1), outline=facts.edge, width=2)
    for index, (line, colour) in enumerate(page):
        top = round(facts.first_line_top + index * facts.line_pitch)
        if top >= _HEIGHT:
            break
        pen = float(facts.text_x)
        ink = facts.red if colour == "red" else facts.ink
        for ch in line:
            g = font.glyph_of(ch)
            if g is None:
                continue
            cell = font.cell(g, facts.scale_x, facts.scale_y)
            glyph = Image.new("RGBA", cell.size, ink)
            glyph.putalpha(cell)
            out.alpha_composite(glyph, (round(pen + font.kerning[g] * facts.scale_x), top))
            pen += font.advances[g] * facts.scale_x
    return out


class Resolved:
    """The font of one project, read on the worker."""

    def __init__(self, font: BoxFont):
        self.font = font


class WindowResolver(WorkerThread):
    """Reads a project's message font off the UI thread. ``resolved`` carries (folder, Resolved or None)."""

    resolved = pyqtSignal(object)

    def __init__(self, source_dir: str, font_member: str, font_companion: str = ""):
        super().__init__()
        self._source_dir = source_dir
        self._font_member = font_member
        self._font_companion = font_companion
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        result = None
        try:
            path = Path(self._source_dir) / Path(self._font_member)
            if self._font_companion:
                atlas = Path(self._source_dir) / Path(self._font_companion)
                result = Resolved(BoxFont.from_pair(path.read_bytes(), atlas.read_bytes()))
            else:
                result = Resolved(BoxFont.from_bytes(path.read_bytes()))
        except (OSError, ValueError, KeyError, IndexError) as exc:
            log_debug(f"message window: no message font for {self._source_dir}: {exc}")
        if not self._stop.is_set():
            self.resolved.emit((self._source_dir, result))


class MessageWindowPreview(QWidget):
    """The message box of one project. It draws with the game's font once ``receive`` gets the font."""

    def __init__(self, source_dir: str, facts: BoxFacts):
        super().__init__()
        self._root = source_dir
        self._facts = facts
        self._font: Optional[BoxFont] = None
        self._text = ""
        self._note = tr("Reading the game font...")
        self._image = QImage(self._facts.screen_width * SCALE, _HEIGHT * SCALE, QImage.Format.Format_ARGB32)
        self.setMinimumSize(self._facts.screen_width * SCALE + 20, _HEIGHT * SCALE + 46)
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


class WindowFonts:
    """The message font of a game plugin: one read per source folder, kept for the plugin's lifetime."""

    def __init__(self):
        self._fonts: Dict[str, Optional[Resolved]] = {}
        self._resolvers: Dict[str, WindowResolver] = {}

    def font_of(self, root: str, facts: BoxFacts) -> Optional[Resolved]:
        """The font of a source folder (one folder, one game). The first call starts the read on a worker; None until
        the read is done."""
        if root not in self._resolvers:
            worker = WindowResolver(root, facts.font_member, facts.font_companion)
            worker.resolved.connect(self._on_resolved)
            self._resolvers[root] = worker
            worker.start()
        return self._fonts.get(root)

    def _on_resolved(self, payload: object) -> None:
        root, resolved = payload
        self._fonts[root] = resolved

    def widget(self, root: str, facts: BoxFacts) -> MessageWindowPreview:
        """A preview widget for a folder. It fills in when the font arrives (now, or from the worker)."""
        self.font_of(root, facts)
        widget = MessageWindowPreview(root, facts)
        if root in self._fonts:
            widget.receive((root, self._fonts[root]))
        else:
            self._resolvers[root].resolved.connect(widget.receive)
        return widget


__all__ = ["BoxFacts", "BoxFont", "MessageWindowPreview", "Resolved", "WindowFonts", "WindowResolver",
           "overflow_lines", "render_page", "split_pages"]
