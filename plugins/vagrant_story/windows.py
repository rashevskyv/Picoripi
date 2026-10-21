"""Message windows of Vagrant Story: the geometry the game draws them with, and a text split into pages and lines.

Sources (rood-reverse decompilation; structure only, no decompiled code is copied):
- dialogue balloon, BATTLE/BATTLE.PRG/5BF94.c, the text box drawing: width = chars_per_line * 12 + 10,
  height = lines * 13 + 4, text at +5 / +3, line step 13; the balloon's text is italic (font table 1).
- information box, 5BF94.c vs_battle_initTextBox case 4 (vs_battle_initInformationTextBox): 24 characters
  per line, text at +16, lines as the caller gives (default 4).
- menu item row, 5BF94.c vs_battle_setMenuItem / vs_battle_renderMenuItem: one line, text from x + 6
  (x + 22 with an icon), regular font; the code does not wrap it.
Byte rules as in codec.py: 0xE5 new page, 0xE8 new line, 0xE6 keeps the text in the same box,
FA nn moves the pen, FB 04 centres the lines that follow, FB 05 / 06 italic / regular.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from . import codec

CELL = 12
BALLOON_PAD_W, BALLOON_PAD_H = 10, 4
BALLOON_STEP = 13
BALLOON_TEXT = (5, 3)
INFO_CHARS, INFO_TEXT_X, INFO_LINES = 24, 16, 4
ROW_TEXT_X, ROW_ICON_X = 6, 22
ITALIC_OFFSET = 0xBD           # the italic widths follow the 189 regular ones
NEW_PAGE = 0xE5
ITALIC_TOGGLE, REGULAR_TOGGLE, CENTRE_TOGGLE = 5, 6, 4


@dataclass
class Line:
    """One line of a page: its byte tokens and whether it is centred."""

    tokens: List[Tuple[int, Optional[int]]] = field(default_factory=list)
    centre: bool = False


def balloon(chars_per_line: int, lines: int) -> dict:
    """A dialogue balloon as the game draws it: its frame and its text place (pixels)."""
    return {"kind": "balloon", "italic": True, "framed": True, "lines": lines,
            "width": chars_per_line * CELL + BALLOON_PAD_W, "height": lines * BALLOON_STEP + BALLOON_PAD_H,
            "text_x": BALLOON_TEXT[0], "text_y": BALLOON_TEXT[1], "step": BALLOON_STEP,
            "text_width": chars_per_line * CELL}


def info_box(lines: int = INFO_LINES) -> dict:
    """The information box (24 characters a line)."""
    return {"kind": "info", "italic": True, "framed": True, "lines": lines,
            "width": INFO_CHARS * CELL + BALLOON_PAD_W, "height": lines * BALLOON_STEP + BALLOON_PAD_H,
            "text_x": INFO_TEXT_X, "text_y": BALLOON_TEXT[1], "step": BALLOON_STEP,
            "text_width": INFO_CHARS * CELL}


def menu_row(icon: bool = False) -> dict:
    """A menu item row: one line of regular text, no frame; its width is the row's own."""
    return {"kind": "row", "italic": False, "framed": False, "lines": 1, "width": None, "height": 16,
            "text_x": ROW_ICON_X if icon else ROW_TEXT_X, "text_y": 0, "step": 16, "text_width": None}


def plain(italic: bool = False) -> dict:
    """Text the game draws without a window of its own (help pages, room names): no limit of lines."""
    return {"kind": "plain", "italic": italic, "framed": False, "lines": None, "width": None, "height": None,
            "text_x": 0, "text_y": 0, "step": 13, "text_width": None}


def split_pages(raw: bytes, italic: bool) -> List[List[Line]]:
    """The pages of one string (end byte excluded): each a list of lines. ``italic`` is the font the text starts in."""
    pages: List[List[Line]] = [[Line()]]
    centre = False
    for code, param in codec.tokens(raw):
        line = pages[-1][-1]
        if param is None and code == codec.NEWLINE:
            pages[-1].append(Line(centre=centre))
        elif param is None and code == NEW_PAGE:
            pages.append([Line(centre=centre)])
        elif code == 0xFB and param == CENTRE_TOGGLE:
            centre = not centre
            line.centre = centre
        else:
            line.tokens.append((code, param))
    return pages


def _advance(code: int, italic: bool, widths: Sequence[int]) -> int:
    index = code + (ITALIC_OFFSET if italic else 0)
    return widths[index] if index < len(widths) else 6


def place(line: Line, italic: bool, widths: Sequence[int], text_x: int = 0,
          centre_width: Optional[int] = None) -> Tuple[List[Tuple[int, bool, int]], int]:
    """``([(glyph code, italic, x)], width)`` of one line. A centred line starts at the middle of ``centre_width``."""
    runs: List[Tuple[int, bool, int]] = []
    pen, state = 0, italic
    for code, param in line.tokens:
        if param is None:
            if code < NEW_PAGE:
                runs.append((code, state, pen))
                pen += _advance(code, state, widths)
            continue
        if code == 0xFA:
            pen += param - 256 if param >= 240 else param
        elif code == 0xFB and param == ITALIC_TOGGLE:
            state = True
        elif code == 0xFB and param == REGULAR_TOGGLE:
            state = False
    width = max(pen, 0)
    start = text_x
    if line.centre and centre_width:
        start = text_x + (centre_width - width) // 2
    return [(c, s, x + start) for c, s, x in runs], width
