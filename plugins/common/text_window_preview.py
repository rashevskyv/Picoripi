"""Draw a message box with a game's own font: the lines, the pages and the overflow warnings.

One renderer for every ROM font. It takes the decoded glyphs (plugins/common/gba_text_font.py or a later decoder),
a window description and the text in data form. ``\\n`` and ``\\l`` start a new line, ``\\p`` starts a new page
and ``{TAG}`` is a placeholder of the tag's name. Pure except for the QImage it returns.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from PyQt6.QtGui import QColor, QImage

from plugins.common.gba_text_font import GLYPH_ROWS, INK, SHADOW, GlyphSet

PAPER_RGB = (255, 255, 255)
INK_RGB = (99, 99, 99)
SHADOW_RGB = (165, 214, 231)
FRAME_RGB = (74, 115, 165)
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

    @classmethod
    def from_facts(cls, facts: Dict[str, object]) -> "Window":
        return cls(int(facts["text_x"]), int(facts["text_width"]), int(facts["lines"]), int(facts["line_height"]),
                   int(facts["box_width"]), int(facts["box_height"]), int(facts.get("text_top", 12)))


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


def render_page(lines: Sequence[Line], glyphs: GlyphSet, window: Window) -> QImage:
    """The box with one page's lines drawn in the game's font. Scale the image when you show it."""
    image = QImage(window.box_width, window.box_height, QImage.Format.Format_ARGB32)
    image.fill(QColor(*PAPER_RGB))
    colours = {INK: QColor(*INK_RGB), SHADOW: QColor(*SHADOW_RGB)}
    for y in range(window.box_height):
        for x in range(window.box_width):
            if x in (0, window.box_width - 1) or y in (0, window.box_height - 1):
                image.setPixelColor(x, y, QColor(*FRAME_RGB))
    for row, line in enumerate(lines[:window.lines]):
        pen_x = window.text_x
        top = window.text_top + row * window.line_height
        for code in line.codes:
            pixels = glyphs.pixels(code)
            for py in range(GLYPH_ROWS):
                for px in range(glyphs.width(code)):
                    value = pixels[py][px]
                    if value in colours and pen_x + px < window.box_width and top + py < window.box_height:
                        image.setPixelColor(pen_x + px, top + py, colours[value])
            pen_x += glyphs.width(code)
    return image
