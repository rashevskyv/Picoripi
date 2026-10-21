"""Symphony of the Night menu screens drawn the way the game draws them (pure, no Qt, no file I/O).

Positions are the draw calls of the decomp (src/dra/menu.c, US build): ``MenuDrawStats`` (the status and
equipment overview blocks), ``MenuSystemDraw``, ``MenuSoundConfigDraw``, the US ``func_800F8754`` command
box, ``func_800F5AE4`` (the info bar), ``func_800F5E68`` / ``MenuDrawRect`` (the highlight) and
``MenuDrawLine`` (the window border). Coordinates are native PlayStation pixels of the display area.

Glyphs come from the caller: ``mask_of(cell)`` returns an 8 x 8 ``L`` image (255 = ink) of an 8x8 font cell and
``cell_of(char)`` the cell of a character. The info-bar line comes from ``menu_text`` (the BIOS KROM2 font).
"""
from __future__ import annotations

from typing import Callable, Dict, Optional, Sequence, Tuple

from PIL import Image

from plugins.castlevania_sotn import menu_text

CANVAS = (368, 240)
CELL = 8
INK = 255
HIGHLIGHT = (0x80, 0x00, 0x00, 255)   # func_800F5E68 with bColorMode 0: r 0x80, g 0, b 0
BORDER = (0xFF, 0xFF, 0xFF, 255)      # MenuDrawLine with a static colour: 0xFF
INFO_BAR_X, INFO_BAR_Y = 72, 201      # func_800F5AE4: three 128-px quads from (72, 201)
STAT_X, STAT_Y, STAT_PITCH = 12, 70, 12          # MenuDrawStats: labels at (x, y + 12 i) (equip overview)
STAT_VALUE_DX, STAT_PLUS_DX, STAT_BONUS_DX = 44, 52, 68
ATT_X, ATT_Y, DEF_OFFSET = 232, 80, 26           # equip overview: attack at (x, y), (x, y + 10), defence y + 26
ATT_VALUE_DX = 76
NAME_X, NAME_Y, NAME_PITCH = 112, 30, 13         # equip overview names at (112, 30 + 13 i)
OVERVIEW_CURSOR = (8, 40)                        # the equipment category label (g_MenuStr[cursor + 85])
STATUS_NAME = (128, 40)
STATUS_LABELS = {   # MenuDrawStats(MENU_DG_BG): (x, y) of each label and right edge of each value
    "HP": (96, 56), "MP": (96, 68), "HEART": (96, 80),
    "EXP": (32, 176), "NEXT": (32, 188), "GOLD": (32, 200),
    "LEVEL": (248, 40), "STATUS": (248, 56), "ROOMS": (240, 150), "KILLS": (240, 164), "TIME": (208, 192),
}
STATUS_STAT_X, STATUS_STAT_Y = 32, 120           # status block: STR, CON, INT, LCK
SYSTEM_X, SYSTEM_Y, SYSTEM_PITCH = 0x20, 0x30, 0x10   # MenuSystemDraw rows
COMMAND_LABELS = (("Equip", 18, 4), ("Spells", 14, 20), ("Relics", 14, 36), ("System", 14, 52),
                  ("Familiars", 2, 68))           # func_800F8754 (US) offsets from the window origin
POPUP_ITEMS = (("Stereo", 4, 4), ("Mono", 4, 20))  # MenuSoundConfigDraw: (cursorX + 4, cursorY + 4/20)


def new_canvas() -> Image.Image:
    return Image.new("RGBA", CANVAS, (0, 0, 0, 0))


def panel(background: Tuple[int, int, int, int] = (16, 18, 60, 255)) -> Image.Image:
    """A flat menu panel for previews; the game draws a gradient (not part of this layout)."""
    return Image.new("RGBA", CANVAS, background)


class Glyphs:
    """Cell lookup for one font: ``mask_of(cell)`` an 8x8 ``L`` mask, ``cell_of(char)`` a cell number."""

    def __init__(self, mask_of: Callable[[int], Image.Image], cell_of: Callable[[str], int]):
        self.mask_of = mask_of
        self.cell_of = cell_of


def blit_mask(canvas: Image.Image, mask: Image.Image, x: int, y: int, color: Tuple[int, int, int, int]) -> None:
    """Paint ``color`` where the mask has ink, clipped to the canvas."""
    layer = Image.new("RGBA", mask.size, color)
    layer.putalpha(mask.point(lambda v: 255 if v else 0))
    _clipped(canvas, layer, x, y)


def _clipped(canvas: Image.Image, layer: Image.Image, x: int, y: int) -> None:
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.width, x + layer.width), min(canvas.height, y + layer.height)
    if x1 <= x0 or y1 <= y0:
        return
    crop = layer.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    canvas.alpha_composite(crop, dest=(x0, y0))


def draw_str(canvas: Image.Image, glyphs: Glyphs, text: str, x: int, y: int, color=(255, 255, 255, 255)) -> None:
    """MenuDrawStr: one cell per character, left to right, 8 px each."""
    for k, ch in enumerate(text):
        blit_mask(canvas, glyphs.mask_of(glyphs.cell_of(ch)), x + CELL * k, y, color)


def draw_int(canvas: Image.Image, glyphs: Glyphs, number: int, x: int, y: int, color=(255, 255, 255, 255)) -> None:
    """MenuDrawInt: the units digit at x, then x - 8, ... (right aligned on x)."""
    while True:
        blit_mask(canvas, glyphs.mask_of(glyphs.cell_of(str(number % 10))), x, y, color)
        number //= 10
        x -= CELL
        if number == 0:
            break


def draw_time(canvas: Image.Image, glyphs: Glyphs, number: int, x: int, y: int, digits: int,
              color=(255, 255, 255, 255)) -> None:
    """MenuDrawTime: a fixed count of digits, right to left (zero padded)."""
    for _ in range(digits):
        blit_mask(canvas, glyphs.mask_of(glyphs.cell_of(str(number % 10))), x, y, color)
        number //= 10
        x -= CELL


def fill_rect(canvas: Image.Image, x: int, y: int, width: int, height: int,
              color: Tuple[int, int, int, int]) -> None:
    """MenuDrawRect: a flat rectangle (the highlight); the rectangle is clipped to the canvas."""
    layer = Image.new("RGBA", (width, height), color)
    _clipped(canvas, layer, x, y)


def frame_lines(canvas: Image.Image, x: int, y: int, width: int, height: int,
                color: Tuple[int, int, int, int] = BORDER) -> None:
    """MenuDrawLine x4: the one-pixel window border around (x, y) of the given size."""
    fill_rect(canvas, x, y, width, 1, color)
    fill_rect(canvas, x, y + height - 1, width, 1, color)
    fill_rect(canvas, x, y, 1, height, color)
    fill_rect(canvas, x + width - 1, y, 1, height, color)


def highlight(canvas: Image.Image, cursor: int, x: int, y: int, width: int, height: int, gap: int) -> None:
    """func_800F5E68: the highlight bar of row ``cursor`` at y + cursor * (height + gap)."""
    fill_rect(canvas, x, y + cursor * (height + gap), width, height, HIGHLIGHT)


def info_bar_strip(text: bytes, glyph_of: Callable[[int], Optional[bytes]]) -> Tuple[Image.Image, int]:
    """The info-bar line as a mask image (RGBA, ink white) and the count of characters outside the table."""
    strip, used, missing = menu_text.draw_line(text, glyph_of)
    rows = menu_text.ink_rows(strip, used)
    width = max(1, len(rows[0]))
    image = Image.new("RGBA", (width, menu_text.ROWS), (0, 0, 0, 0))
    pixels = image.load()
    for y, row in enumerate(rows):
        for x, on in enumerate(row):
            if on:
                pixels[x, y] = (255, 255, 255, 255)
    return image, missing


def paint_info_bar(canvas: Image.Image, text: bytes, glyph_of: Callable[[int], Optional[bytes]]) -> int:
    image, missing = info_bar_strip(text, glyph_of)
    canvas.alpha_composite(image, dest=(INFO_BAR_X, INFO_BAR_Y))
    return missing


def equip_overview(canvas: Image.Image, glyphs: Glyphs, category: str, stats: Sequence[Tuple[str, int, Optional[int]]],
                   names: Sequence[str], att: Tuple[int, int], dfn: int) -> None:
    """MENU_DG_EQUIP_OVERVIEW: the category, the STR/CON/INT/LCK block, the names and the ATT/DEF values."""
    draw_str(canvas, glyphs, category, *OVERVIEW_CURSOR)
    for i, (label, base, bonus) in enumerate(stats):
        y = STAT_Y + STAT_PITCH * i
        draw_str(canvas, glyphs, label, STAT_X, y)
        draw_int(canvas, glyphs, base, STAT_X + STAT_VALUE_DX, y)
        if bonus is not None:
            draw_str(canvas, glyphs, "+", STAT_X + STAT_PLUS_DX, y)
            draw_int(canvas, glyphs, bonus, STAT_X + STAT_BONUS_DX, y)
    for i, name in enumerate(names):
        draw_str(canvas, glyphs, name, NAME_X, NAME_Y + NAME_PITCH * i)
    draw_int(canvas, glyphs, att[0], ATT_X + ATT_VALUE_DX, ATT_Y)
    draw_int(canvas, glyphs, att[1], ATT_X + ATT_VALUE_DX, ATT_Y + 10)
    draw_int(canvas, glyphs, dfn, ATT_X + ATT_VALUE_DX, ATT_Y + DEF_OFFSET)


def status(canvas: Image.Image, glyphs: Glyphs, name: str, values: Dict[str, Tuple[int, ...]],
           stats: Sequence[Tuple[str, int, Optional[int]]], att: Tuple[int, int], dfn: int, state: str) -> None:
    """MENU_DG_BG: the status screen (MenuDrawStats(1)) with the given values."""
    draw_str(canvas, glyphs, name, *STATUS_NAME)
    for label, y, (a, b) in (("HP", 56, values["HP"]), ("MP", 68, values["MP"]), ("HEART", 80, values["HEART"])):
        draw_str(canvas, glyphs, label, 96, y)
        draw_int(canvas, glyphs, a, 168, y)
        draw_str(canvas, glyphs, "/", 176, y)
        draw_int(canvas, glyphs, b, 208, y)
    draw_str(canvas, glyphs, "EXP", *STATUS_LABELS["EXP"])
    draw_int(canvas, glyphs, values["EXP"][0], 144, 176)
    draw_str(canvas, glyphs, "NEXT", *STATUS_LABELS["NEXT"])
    draw_int(canvas, glyphs, values["NEXT"][0], 144, 188)
    draw_str(canvas, glyphs, "GOLD", *STATUS_LABELS["GOLD"])
    draw_int(canvas, glyphs, values["GOLD"][0], 144, 200)
    draw_str(canvas, glyphs, "LEVEL", *STATUS_LABELS["LEVEL"])
    draw_int(canvas, glyphs, values["LEVEL"][0], 304, 40)
    draw_str(canvas, glyphs, "STATUS", *STATUS_LABELS["STATUS"])
    draw_str(canvas, glyphs, state, 260, 68)
    draw_str(canvas, glyphs, "ROOMS", *STATUS_LABELS["ROOMS"])
    draw_int(canvas, glyphs, values["ROOMS"][0], 328, 150)
    draw_str(canvas, glyphs, "KILLS", *STATUS_LABELS["KILLS"])
    draw_int(canvas, glyphs, values["KILLS"][0], 328, 164)
    draw_str(canvas, glyphs, "TIME", *STATUS_LABELS["TIME"])
    hours, minutes, seconds = values["TIME"]
    draw_int(canvas, glyphs, hours, 264, 192)
    draw_str(canvas, glyphs, ":", 272, 192)
    draw_time(canvas, glyphs, minutes, 288, 192, 2)
    draw_str(canvas, glyphs, ":", 296, 192)
    draw_time(canvas, glyphs, seconds, 312, 192, 2)
    draw_int(canvas, glyphs, att[0], 248 + ATT_VALUE_DX, 88)
    draw_int(canvas, glyphs, att[1], 248 + ATT_VALUE_DX, 98)
    draw_int(canvas, glyphs, dfn, 248 + ATT_VALUE_DX, 88 + DEF_OFFSET)
    for i, (label, base, bonus) in enumerate(stats):
        y = STATUS_STAT_Y + STAT_PITCH * i
        draw_str(canvas, glyphs, label, STATUS_STAT_X, y)
        draw_int(canvas, glyphs, base, STATUS_STAT_X + STAT_VALUE_DX, y)
        if bonus is not None:
            draw_str(canvas, glyphs, "+", STATUS_STAT_X + STAT_PLUS_DX, y)
            draw_int(canvas, glyphs, bonus, STATUS_STAT_X + STAT_BONUS_DX, y)


def command_box(canvas: Image.Image, glyphs: Glyphs, x: int, y: int, cursor: int,
                dim: Sequence[str] = ("Spells", "Familiars"), width: int = 60) -> None:
    """func_800F8754 (US) with its window: the border, the highlight of ``cursor`` and the five labels.

    ``width`` is the window width; the highlight spans the window (fitted, see OPEN_ITEMS).
    """
    frame_lines(canvas, x - 2, y - 2, width + 4, 80 + 4)
    highlight(canvas, cursor, x - 2, y - 2 + 4, width + 4, 12, 4)
    for label, dx, dy in COMMAND_LABELS:
        color = (96, 96, 96, 255) if label in dim else (255, 255, 255, 255)
        draw_str(canvas, glyphs, label, x + dx, y + dy, color)


def sound_popup(canvas: Image.Image, glyphs: Glyphs, x: int, y: int, mono: bool) -> None:
    """MenuSoundConfigDraw: the Stereo / Mono list at (cursorX, cursorY); the chosen item is highlighted."""
    frame_lines(canvas, x, y, 60, 36)
    highlight(canvas, 1 if mono else 0, x + 2, y + 2, 56, 12, 4)
    for label, dx, dy in POPUP_ITEMS:
        draw_str(canvas, glyphs, label, x + dx, y + dy)


def system_rows(canvas: Image.Image, glyphs: Glyphs, rows: Sequence[str]) -> None:
    """MenuSystemDraw: the rows at (0x20, 0x30 + 0x10 i)."""
    for i, text in enumerate(rows):
        draw_str(canvas, glyphs, text, SYSTEM_X, SYSTEM_Y + SYSTEM_PITCH * i)
