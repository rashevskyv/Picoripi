"""The cutscene dialogue window of Symphony of the Night, drawn with the game's layout (headless, PIL only).

Layout, from the USA decomp (``src/st/cutscene_script_box.h``, ``src/st/cutscene_script_text.h``, ``src/st/cen/cutscene.c``):
the window's place is set by the script's ``POS x y`` command (``startX``, ``startY``); the text of a line
starts at x = startX + 4 and y = startY + 20 for the first line, then one line every 12 px. A cell is 8 px
wide in the 8x8 font (two halfwords of 4bpp VRAM), so the strip of 192 px holds 24 cells. The screen is
320 x 240 (the PS1 NTSC frame). Glyph cells come from the 8x8 font sheet on the disc.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from PIL import Image

CANVAS = (320, 240)
CELL = 8                  # cell width and height of the 8x8 font, in pixels
PITCH = 12                # one text line every 12 px (CutsceneUnk3 / rect.y = nextCharY * 12)
TEXT_WIDTH = 192          # the text strip: u1 = 192 (cutscene_script_box.h), 24 cells
TEXT_DX = 4               # prim x0 = startX + 4
TEXT_DY = 20              # first line: nextLineY = startY + 20 (cutscene_script_text.h)
LINES = 4                 # lines a page shows (config.json lines_per_page)
DEFAULT_PLACE = (0, 0)    # used when a line has no POS before it in its script


@dataclass(frozen=True)
class Place:
    """Where the window's text starts: ``startX`` and ``startY`` of the script's POS command."""

    x: int
    y: int

    def line_origin(self, row: int) -> Tuple[int, int]:
        return self.x + TEXT_DX, self.y + TEXT_DY + row * PITCH


def cell_sheet_crop(sheet: Image.Image, code: int, columns: int = 16) -> Image.Image:
    """The 8x8 cell ``code`` of a grid sheet (row-major, ``columns`` cells a row)."""
    col, row = code % columns, code // columns
    return sheet.crop((col * CELL, row * CELL, col * CELL + CELL, row * CELL + CELL))


def render_page(lines: Sequence[Sequence[int]], sheet: Image.Image, place: Place,
                background: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
    """One page of text drawn into the 320 x 240 frame, cell by cell.

    ``lines`` are cell codes, one list per line (at most ``LINES``). Pixels with alpha 0 in a cell are
    not drawn, so the frame behind the window shows through. ``background`` (RGBA) fills the frame first.
    """
    frame = Image.new("RGBA", CANVAS, background or (0, 0, 0, 0))
    for row, codes in enumerate(lines[:LINES]):
        x, y = place.line_origin(row)
        for index, code in enumerate(codes):
            if (index + 1) * CELL > TEXT_WIDTH:
                break                       # the strip ends: the rest of the line is not drawn
            px = x + index * CELL
            if px >= 0 and y >= 0 and px + CELL <= CANVAS[0] and y + CELL <= CANVAS[1]:
                frame.alpha_composite(cell_sheet_crop(sheet, code), (px, y))
    return frame


def scale_nearest(image: Image.Image, factor: int) -> Image.Image:
    """Whole-number, nearest-neighbour zoom of the frame (pixel-crisp)."""
    return image.resize((image.width * factor, image.height * factor), Image.NEAREST)
