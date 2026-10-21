"""The cutscene dialogue window of Symphony of the Night, drawn with the game's layout (headless, PIL only).

The window's place is set by the script's ``POS x y`` command (``startX``, ``startY``, ``src/st/cen/cutscene.c``).
A cell is 8 px wide in the 8x8 font (two halfwords of 4bpp VRAM), so the strip of 192 px holds 24 cells; one
line is 12 px high (``src/st/cutscene_script_box.h``). The text origin is fitted to a DuckStation frame, not
taken from the decomp's ``startX + 4`` and ``startY + 20`` rule: the owner's ``owner_02_dracula_dialog.png``
(ST0 line, POS 60, 36) puts the first body line at (72, 41). The screen is 256 x 240 in that frame; the
canvas here stays 320 x 240. Glyph cells come from the 8x8 font sheet on the disc.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from PIL import Image

CANVAS = (320, 240)
CELL = 8                  # cell width and height of the 8x8 font, in pixels
PITCH = 12                # one text line every 12 px (CutsceneUnk3 / rect.y = nextCharY * 12)
TEXT_WIDTH = 192          # the text strip: u1 = 192 (cutscene_script_box.h), 24 cells
TEXT_DX = 12              # fitted: first body line x = startX + 12 (owner_02, ST0 line, POS 60, 36)
TEXT_DY = 5               # fitted: first body line y = startY + 5 (same frame)
LINES = 4                 # lines a page shows (config.json lines_per_page)
DEFAULT_PLACE = (60, 36)  # used when a line has no POS before it: the POS of the owner's ST0 frame
SPEAKER_X = 56            # the name's x is fixed: 0x38 (src/st/cutscene_actor_name.h); fitted to owner_02
SPEAKER_DY = -12          # fitted: the name row is startY - 12 in the owner's frame (decomp: startY + 6)


@dataclass(frozen=True)
class Place:
    """Where the window's text starts: ``startX`` and ``startY`` of the script's POS command."""

    x: int
    y: int

    def line_origin(self, row: int) -> Tuple[int, int]:
        return self.x + TEXT_DX, self.y + TEXT_DY + row * PITCH


def render_dialogue(speaker: Sequence[int], lines: Sequence[Sequence[int]], sheet: Image.Image, place: Place,
                    background: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
    """The speaker name above the page's lines, in the same 8x8 font (speaker cells are passed as codes)."""
    frame = render_page(lines, sheet, place, background)
    if speaker:
        name_x, name_y = SPEAKER_X, place.y + SPEAKER_DY
        for index, code in enumerate(speaker):
            px = name_x + index * CELL
            if 0 <= px and 0 <= name_y and px + CELL <= CANVAS[0] and name_y + CELL <= CANVAS[1]:
                frame.alpha_composite(cell_sheet_crop(sheet, code), (px, name_y))
    return frame


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
