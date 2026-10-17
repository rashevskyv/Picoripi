"""Draw a message box with a game's own font: the lines, the pages and the overflow warnings.

One renderer for every ROM font. It takes the decoded glyphs (plugins/common/gba_text_font.py or a later decoder),
a window description and the text in data form. ``\\n`` and ``\\l`` start a new line, ``\\p`` starts a new page
and ``{TAG}`` is a placeholder of the tag's name. Pure except for the QImage it returns.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from PyQt6.QtGui import QColor, QImage

from plugins.common.gba_text_font import INK, SHADOW, GlyphSet

PAPER_RGB = (255, 255, 255)
INK_RGB = (99, 99, 99)
SHADOW_RGB = (165, 214, 231)
FRAME_RGB = (74, 115, 165)
CELL = 8                                    # one tile of the game's text box, in pixels
TOKEN = re.compile(r"(\\[nlp]|\n|\{[^{}]*\})")


@dataclass(frozen=True)
class Window:
    """The message box in its own pixels: where the text starts, how wide and how many lines it shows."""

    text_x: int
    text_width: int
    lines: int
    line_height: int
    box_width: int
    box_height: int
    text_top: int = 12
    frame: Optional[Dict[str, int]] = None      # tile codes of the box frame (tl, h, tr, v, bl, br), if the game has one

    @classmethod
    def from_facts(cls, facts: Dict[str, object]) -> "Window":
        frame = facts.get("frame")
        return cls(int(facts["text_x"]), int(facts["text_width"]), int(facts["lines"]), int(facts["line_height"]),
                   int(facts["box_width"]), int(facts["box_height"]), int(facts.get("text_top", 12)),
                   {str(k): int(v) for k, v in frame.items()} if isinstance(frame, dict) else None)


@dataclass
class Line:
    """One line of a page: the glyph codes it draws, and how it begins (``n`` new line, ``l`` scroll)."""

    codes: List[int]
    start: str
    text: str


@dataclass
class Overflow:
    """An overflow the editor should show: which page and line, and what is wrong."""

    page: int
    line: int
    kind: str       # "wide" (too many pixels) or "lines" (more lines than the box shows without a scroll)
    detail: int     # pixel width of the line, or the line count


def parse_pages(text: str, code_of: Callable[[str], Optional[int]], missing: int) -> List[List[Line]]:
    """Split the data text into pages of lines. A character without a code draws ``missing`` (a question mark)."""
    pages: List[List[Line]] = [[]]
    current = Line([], "n", "")
    for token in (part for part in TOKEN.split(str(text)) if part != ""):
        if token in ("\\n", "\n", "\\l"):
            pages[-1].append(current)
            current = Line([], "l" if token == "\\l" else "n", "")
        elif token == "\\p":
            pages[-1].append(current)
            pages.append([])
            current = Line([], "n", "")
        elif token.startswith("{") and token.endswith("}"):
            name = token[1:-1].split(" ")[0].upper()
            current.text += token
            current.codes.extend(_code(code_of, ch, missing) for ch in name)
        else:
            for ch in token:
                current.text += ch
                current.codes.append(_code(code_of, ch, missing))
    pages[-1].append(current)
    return [page for page in pages if any(line.codes or line.text for line in page)] or [[Line([], "n", "")]]


def _code(code_of: Callable[[str], Optional[int]], ch: str, missing: int) -> int:
    code = code_of(ch)
    return missing if code is None else code


class CodeTable:
    """Text character to byte code: ``byte_of`` is the lookup the parsers call."""

    def __init__(self, byte_of: Dict[str, int]) -> None:
        self.byte_of = byte_of


class FontContext:
    """What a message box preview needs from a project: the glyphs, the codes and the window."""

    def __init__(self, glyphs: Any, charmap: Any, window: Window) -> None:
        self.glyphs = glyphs
        self.charmap = charmap
        self.window = window


GB_BREAKS = ("line", "next", "cont", "para", "page")
_GB_TOKEN = re.compile(r"(\{[^{}]*\}|<[^<>]+>|#|@|\n)")


class _GbBox:
    """The two-row Game Boy box while the text runs through it (see ``parse_gb_pages``)."""

    def __init__(self, code_of: Callable[[str], Optional[int]], missing: int, placeholders: Dict[str, str]) -> None:
        self.code_of, self.missing, self.placeholders = code_of, missing, placeholders
        self.pages: List[List[Line]] = [[]]
        self.line = Line([], "n", "")
        self.pending = 0            # newlines not turned into a break yet
        self.forced = ""            # the {word} written right after the newlines
        self.previous = ""          # the last break word

    def newline(self) -> None:
        self.pending += 1

    def force(self, word: str) -> None:
        if self.pending:
            self.forced = word

    def _break(self) -> None:
        if not self.pending:
            return
        if self.pending >= 2:
            word = "para"
        elif self.forced:
            word = self.forced
        else:
            word = "cont" if self.previous in ("line", "cont") else "line"
        self.pending, self.forced, self.previous = 0, "", word
        closed = self.line
        self.pages[-1].append(closed)
        self.line = Line([], "n", "")
        if word in ("para", "page"):
            self.pages.append([])
        elif word == "cont":
            # The box scrolls up one row: the bottom row moves to the top, and the bottom row is empty when the
            # line just closed was the top one.
            if len(self.pages[-1]) >= 2:
                self.pages.append([Line(list(closed.codes), "n", closed.text)])
            else:
                self.pages.append([Line([], "n", "")])

    def draw(self, chars: str) -> None:
        self._break()
        for ch in chars:
            self.line.text += ch
            self.line.codes.append(_code(self.code_of, ch, self.missing))

    def code(self, token: str) -> None:
        self._break()
        self.line.text += token
        self.line.codes.append(_code(self.code_of, token, self.missing))

    def finish(self) -> List[List[Line]]:
        self.pages[-1].append(self.line)
        return [page for page in self.pages if any(line.codes or line.text for line in page)] or [[Line([], "n", "")]]


def parse_gb_pages(text: str, code_of: Callable[[str], Optional[int]], missing: int,
                   placeholders: Optional[Dict[str, str]] = None) -> List[List[Line]]:
    """Screens of a Game Boy text box: two rows, a new screen after a scroll (``{cont}``) or a clear (``{para}``).

    A newline is a new row (``line`` or ``next``). Without a tag the game's default applies: ``line`` after text
    and ``cont`` after a row break that followed ``line`` or ``cont``. Two newlines clear the box. A flow tag
    right after the newlines names the break. A line that carries a placeholder (``{Player}``, ``<PLAYER>``...)
    draws the text in ``placeholders``; any other tag draws ``missing`` once. A third row on one screen is shown
    in ``check_pages`` as an overflow.
    """
    box = _GbBox(code_of, missing, placeholders or {})
    for token in (part for part in _GB_TOKEN.split(str(text)) if part != ""):
        if token == "\n":
            box.newline()
        elif token == "@":
            continue
        elif token in box.placeholders:
            box.draw(box.placeholders[token])
        elif token.startswith("{") and token.endswith("}"):
            name = token[1:-1].split(" ")[0]
            if name in GB_BREAKS:
                box.force(name)
            else:
                box.draw("?")
        elif token.startswith("<") and token.endswith(">"):
            box.code(token)
        else:
            box.draw(token)
    return box.finish()


def check_pages(pages: Sequence[Sequence[Line]], glyphs: GlyphSet, window: Window) -> List[Overflow]:
    """Overflows: a line wider than the text width, and a plain new line beyond the box's line count."""
    found: List[Overflow] = []
    for p, page in enumerate(pages):
        screen = 0                      # lines since the last scroll or page break
        for l, line in enumerate(page):
            width = sum(glyphs.width(code) for code in line.codes)
            if width > window.text_width:
                found.append(Overflow(p, l, "wide", width))
            if line.start == "l":
                screen = 0
            elif l > 0:
                screen += 1
            if screen >= window.lines:
                found.append(Overflow(p, l, "lines", screen + 1))
                screen = 0
    return found


def _draw_glyph(image: QImage, glyphs: GlyphSet, code: int, x: int, y: int, colours: Dict[int, QColor]) -> None:
    pixels = glyphs.pixels(code)
    for py in range(len(pixels)):
        for px in range(glyphs.drawn_width(code)):
            value = pixels[py][px]
            if value in colours and 0 <= x + px < image.width() and 0 <= y + py < image.height():
                image.setPixelColor(x + px, y + py, colours[value])


def _draw_tile_frame(image: QImage, glyphs: GlyphSet, window: Window, colours: Dict[int, QColor]) -> None:
    """The box frame as the game draws it: one font tile per cell along the edges (tl, h, tr, v, bl, br)."""
    frame = window.frame or {}
    columns, rows = window.box_width // CELL, window.box_height // CELL
    for cy in range(rows):
        for cx in range(columns):
            top, bottom, left, right = cy == 0, cy == rows - 1, cx == 0, cx == columns - 1
            if top:
                key = ("tl" if left else "tr" if right else "h")
            elif bottom:
                key = ("bl" if left else "br" if right else "h")
            elif left or right:
                key = "v"
            else:
                continue
            if key in frame:
                _draw_glyph(image, glyphs, frame[key], cx * CELL, cy * CELL, colours)


def render_page(lines: Sequence[Line], glyphs: GlyphSet, window: Window) -> QImage:
    """The box with one page's lines drawn in the game's font. Scale the image when you show it."""
    image = QImage(window.box_width, window.box_height, QImage.Format.Format_ARGB32)
    image.fill(QColor(*PAPER_RGB))
    colours = {INK: QColor(*INK_RGB), SHADOW: QColor(*SHADOW_RGB)}
    if window.frame:
        _draw_tile_frame(image, glyphs, window, colours)
    else:
        for y in range(window.box_height):
            for x in range(window.box_width):
                if x in (0, window.box_width - 1) or y in (0, window.box_height - 1):
                    image.setPixelColor(x, y, QColor(*FRAME_RGB))
    for row, line in enumerate(lines[:window.lines]):
        pen_x = window.text_x
        top = window.text_top + row * window.line_height
        for code in line.codes:
            _draw_glyph(image, glyphs, code, pen_x, top, colours)
            pen_x += glyphs.width(code)
    return image
