"""Composes the two console screens of the manual viewer around a rendered page column (Pillow, no Qt).

The viewer draws both screens as one 400 x 480 canvas: the top screen is rows 0..239, the bottom screen rows
240..479 at x 40..359. The page column (320 px) sits at x 40..359; page y = 0 is canvas row PAGE_TOP at scroll
0 (measured: shots_r17b 2011-01-04_01-59-44.529 matches the column at row 38 exactly). Around it the viewer's
own chrome: the white header with the page badge and title, the scroll track and bar, the neighbour pages'
edges, the bottom bar. The chrome textures are not in the dumps the owner has; they are cut out of console
screenshots into a git-ignored folder (``chrome_dir``), and the measured geometry is in CHROME below (every
number from scratch measurements on shots_r17b, see the chrome report in the owner's notes).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw

from plugins.manual_3ds import console_render as cr

CANVAS = (400, 480)
TOP = (400, 240)
BOTTOM = (320, 240)
CARD_X = 40                 # the page column's left edge on the canvas
PAGE_TOP = 38               # canvas row of page y = 0 at scroll 0 (the header is rows 0..37)
HEADER_ROWS = 38
HEADER_X = (34, 366)        # the header bar overlaps the tracks by 6 px each side
HEADER_SHADOW = (173, 187, 203, 219, 234, 245, 251, 253)   # rows 38..45, multiplied over the page (shot 04 mode)
HEADER_CORNER = (34, 35, 36, 37, 38)                       # left edge x of rows 33..37 (right edge mirrored)
BADGE = (40, 4, 68, 32)     # x0, y0, x1, y1 (outer, inclusive); solid core rows 8..28
BADGE_RADIUS = 6
# The badge digit and the title are drawn with the system font. The viewer's PageNum / SoftTitleHeader layouts
# say 21.25 and 15 x 18 px, but the console draws them at these sizes (fit by least difference against five
# shots_r17b headers: pages 1, 7, 10, 17 and 21).
BADGE_FONT = 15.5
BADGE_BASELINE = 24.5       # the digit's baseline row; centred at x 54
BADGE_CENTRE_X = 54
TITLE_FONT = (17.5, 21.0)
TITLE_X = 78.0              # pen x of the title (ink starts at 79-80 with the glyph's left bearing)
TITLE_BASELINE = 25
TITLE_INK = (50, 50, 50, 255)
TRACK_X = (360, 380)        # the scroll track on the right of the card; mirrored at x 20..39 when a page precedes
BAR_X = (364, 368)          # the teal scroll bar (exclusive end), 1 px light outline around it
BAR_FILL = (90, 157, 158)
BAR_OUTLINE = (221, 221, 221)
BAR_TOP = 42                # the bar's first row at scroll 0
BAR_BOTTOM = 232            # one past the bar's last row at the end of the page (shot 24: rows 204..231)
BOTTOM_BAR_ROW = 452        # rows 452..479 of the canvas
BOTTOM_LABEL_FONT = 17.5    # T_BtnF_Text fontSize
BOTTOM_LABEL_BASELINE = 471
BOTTOM_LABEL_INK = (50, 50, 50, 255)
ZOOM_LABEL_X = {2: 247, 3: 257}   # ink left of the Y label word by bottom-bar layout (buttons)
# Badge fill per category index of the manual's Index (Category_000 is the one without a heading).
# Measured: health page 1 (category 0) salmon; HOME page 2 (category 1) green; page 3 (category 2) light blue;
# pages 7, 10 (category 3) yellow; pages 17, 21 (category 4) purple. Categories 5+ are not in any screenshot.
BADGE_COLOURS = {0: (237, 136, 136), 1: (154, 212, 105), 2: (117, 183, 217), 3: (226, 202, 91), 4: (156, 139, 214)}
BADGE_FALLBACK = (160, 160, 160)
NO_PREVIOUS_STRIP = (242, 242, 241, 241, 241, 240, 239, 239, 239, 238, 237, 237, 237, 236, 236, 236, 235, 235, 234, 233)


@dataclass
class Chrome:
    """The screenshot crops the chrome is drawn with (git-ignored folder); None when the folder is missing."""

    side_left: Optional[Image.Image] = None      # 40 x 240, page 1 (no previous page): strip + card shadow
    scroll_track: Optional[Image.Image] = None   # 20 x 240 with the bar at rows 42..69 (replaced with rows 70..97)
    bottom_bar: Dict[int, Optional[Image.Image]] = None  # type: ignore[assignment]  # buttons -> 320 x 28
    arrows: Tuple[Optional[Image.Image], Optional[Image.Image]] = (None, None)   # 40 x 60 at rows 90..149

    @classmethod
    def load(cls, folder: Optional[Path]) -> "Chrome":
        chrome = cls(bottom_bar={})
        if folder is None or not folder.is_dir():
            return chrome

        def crop(name: str) -> Optional[Image.Image]:
            path = folder / name
            return Image.open(path).convert("RGBA") if path.is_file() else None

        chrome.side_left = crop("side_left.png")
        track = crop("scroll_track.png")
        if track is not None:
            clean = track.copy()
            clean.paste(track.crop((0, 70, 20, 98)), (0, 42))   # the bar rows, filled with the rows below them
            chrome.scroll_track = clean
        chrome.bottom_bar = {2: crop("bottom_bar_2buttons.png"), 3: crop("bottom_bar_3buttons.png")}
        chrome.arrows = (crop("arrow_left.png"), crop("arrow_right.png"))
        return chrome


@dataclass
class PageInfo:
    """What the chrome shows about the page: its badge number, title, category and neighbours."""

    number: int                 # the console's page number (1-based)
    title: str
    category: int               # index into the manual's Index categories (Category_000 = 0)
    has_previous: bool = True
    has_next: bool = True
    large: bool = False         # the Y button reads "Зменшити" when the page is large
    buttons: int = 3            # bottom bar layout: 2 (no close button) or 3


VISIBLE_ROWS = BOTTOM_BAR_ROW - PAGE_TOP   # page rows between the header and the bottom bar (414)
# The page scrolls until the card's bottom margin (TOP_MARGIN below the content) reaches the bottom bar: the
# end-of-page shots (shots_r12 2011-01-03_23-35-05.157 and _23-35-22.475) show the page's last rule with the
# margin below it and nothing else, which no scroll up to the content's bottom reproduces.
END_PAD = cr.TOP_MARGIN_ROWS


def scroll_range(column_height: int) -> int:
    """The most the page can scroll: the card's bottom (content plus its margin) reaches the bottom bar."""
    content = column_height - 2 * cr.TOP_MARGIN_ROWS
    return max(0, content - VISIBLE_ROWS + END_PAD)


def overlay(info: PageInfo, chrome: Chrome, glyphs: cr.Glyphs,
            neighbours: Tuple[Optional[Image.Image], Optional[Image.Image]] = (None, None),
            arrows: bool = False) -> Image.Image:
    """The chrome alone on a 400 x 480 canvas: everything but the card's interior, which stays transparent.

    `neighbours` are the previous and next pages' columns, whose edges show beside the card (drawn at scroll 0,
    as the viewer does when they were not visited). The header's shadow is black at the measured alpha, so
    composing the overlay over the page multiplies the rows under the header exactly as the console does.
    """
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, TOP[1], CARD_X - 1, CANVAS[1] - 1), fill=(0, 0, 0, 255))
    draw.rectangle((CARD_X + cr.COLUMN_WIDTH, TOP[1], CANVAS[0] - 1, CANVAS[1] - 1), fill=(0, 0, 0, 255))
    _draw_side(canvas, chrome, info, neighbours)
    for index, grey in enumerate(HEADER_SHADOW):
        draw.line((HEADER_X[0], HEADER_ROWS + index, HEADER_X[1] - 1, HEADER_ROWS + index), fill=(0, 0, 0, 255 - grey))
    _draw_header(canvas, info, glyphs)
    if arrows:
        for index, (x, image) in enumerate(((0, chrome.arrows[0]), (360, chrome.arrows[1]))):
            if image is not None and (info.has_previous if index == 0 else info.has_next):
                canvas.alpha_composite(image, (x, 90))
    _draw_bottom_bar(canvas, info, chrome, glyphs)
    return canvas


def compose(column: Image.Image, scroll: float, info: PageInfo, chrome: Chrome, glyphs: cr.Glyphs,
            neighbours: Tuple[Optional[Image.Image], Optional[Image.Image]] = (None, None),
            arrows: bool = False) -> Image.Image:
    """The 400 x 480 canvas: the white card with the page column at `scroll`, the chrome over it, the scroll bar."""
    return compose_with(column, scroll, overlay(info, chrome, glyphs, neighbours, arrows))


def compose_with(column: Image.Image, scroll: float, chrome_overlay: Image.Image) -> Image.Image:
    """`compose` with a ready overlay (the panel keeps one per page and scrolls the column under it)."""
    canvas = Image.new("RGBA", CANVAS, (255, 255, 255, 255))
    _paste_column(canvas, column, CARD_X, PAGE_TOP, scroll)
    canvas.alpha_composite(chrome_overlay)
    x0, y0, x1, y1 = bar_rect(column.height, scroll)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((x0 - 1, y0 - 1, x1 + 1, y1 + 1), fill=BAR_OUTLINE + (255,))
    draw.rectangle((x0, y0, x1, y1), fill=BAR_FILL + (255,))
    return canvas


def split(canvas: Image.Image) -> Tuple[Image.Image, Image.Image]:
    """-> (top 400 x 240, bottom 320 x 240) as the console's screenshots show them."""
    top = canvas.crop((0, 0, TOP[0], TOP[1])).convert("RGB")
    bottom = canvas.crop((CARD_X, TOP[1], CARD_X + BOTTOM[0], TOP[1] + BOTTOM[1])).convert("RGB")
    return top, bottom


def _paste_column(canvas: Image.Image, column: Image.Image, x: int, top_row: int, scroll: float) -> None:
    """The column so that page y = 0 lands on canvas row top_row - scroll (column row 0 is page y = +TOP_MARGIN).

    A fractional scroll shifts the column by the fraction with bilinear sampling: the console scrolls by
    fractions of a pixel too (its text is slightly blurred at some stops).
    """
    exact = top_row - cr.TOP_MARGIN_ROWS - scroll
    y = int(math.floor(exact))
    fraction = exact - y
    src_y0 = max(0, -y)
    dst_y0 = max(0, y)
    height = min(column.height - src_y0, canvas.height - dst_y0 + 1)
    if height <= 0:
        return
    piece = column.crop((0, src_y0, column.width, src_y0 + height))
    if fraction > 1e-3:
        piece = piece.transform(piece.size, Image.Transform.AFFINE, (1.0, 0.0, 0.0, 0.0, 1.0, -fraction),
                                Image.Resampling.BILINEAR)
    canvas.alpha_composite(piece.crop((0, 0, piece.width, min(piece.height, canvas.height - dst_y0))), (x, dst_y0))


def _draw_side(canvas: Image.Image, chrome: Chrome, info: PageInfo,
               neighbours: Tuple[Optional[Image.Image], Optional[Image.Image]]) -> None:
    draw = ImageDraw.Draw(canvas)
    previous, following = neighbours
    # Right side: the next page's left edge (x 380..399), then the track (x 360..379).
    draw.rectangle((360, 0, 399, 239), fill=(255, 255, 255, 255))
    if following is not None and info.has_next:
        _paste_column(canvas, following.crop((0, 0, 20, following.height)), 380, PAGE_TOP, 0.0)
    if chrome.scroll_track is not None:
        canvas.alpha_composite(chrome.scroll_track, (TRACK_X[0], 0))
    # Left side: the previous page's right edge (x 0..19) and a mirrored track, or page 1's plain strip.
    if info.has_previous:
        draw.rectangle((0, 0, 39, 239), fill=(255, 255, 255, 255))
        if previous is not None:
            _paste_column(canvas, previous.crop((300, 0, 320, previous.height)), 0, PAGE_TOP, 0.0)
        if chrome.scroll_track is not None:
            canvas.alpha_composite(chrome.scroll_track.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (20, 0))
    elif chrome.side_left is not None:
        canvas.alpha_composite(chrome.side_left, (0, 0))
    else:
        for x, grey in enumerate(NO_PREVIOUS_STRIP):
            draw.line((x, 0, x, 239), fill=(grey, grey, grey, 255))
        draw.rectangle((20, 0, 39, 239), fill=(255, 255, 255, 255))


def _draw_header(canvas: Image.Image, info: PageInfo, glyphs: cr.Glyphs) -> None:
    draw = ImageDraw.Draw(canvas)
    x0, x1 = HEADER_X
    draw.rectangle((x0, 0, x1 - 1, HEADER_ROWS - 1), fill=(255, 255, 255, 255))
    # Rounded bottom corners: the rows 33..37 start later on each side.
    for index, edge in enumerate(HEADER_CORNER):
        row = HEADER_ROWS - len(HEADER_CORNER) + index
        for x in range(x0, edge):
            canvas.putpixel((x, row), (0, 0, 0, 0))
            canvas.putpixel((x1 - 1 - (x - x0), row), (0, 0, 0, 0))
    # The badge and its number.
    colour = BADGE_COLOURS.get(info.category, BADGE_FALLBACK) + (255,)
    draw.rounded_rectangle(BADGE, radius=BADGE_RADIUS, fill=colour)
    text = str(info.number)
    scale = BADGE_FONT / glyphs.width
    width = _text_width(glyphs, text, scale, 0.0)
    _draw_text(canvas, glyphs, text, BADGE_CENTRE_X - width / 2.0, BADGE_BASELINE, BADGE_FONT, BADGE_FONT * glyphs.height / glyphs.width,
               (255, 255, 255, 255))
    if info.title:
        _draw_text(canvas, glyphs, info.title, TITLE_X, TITLE_BASELINE, TITLE_FONT[0], TITLE_FONT[1], TITLE_INK)


def bar_rect(column_height: int, scroll: float) -> Tuple[int, int, int, int]:
    """The teal scroll bar (x0, y0, x1, y1 inclusive): its length is the visible share of the page, its
    position the scroll share of the track (BAR_TOP..BAR_BOTTOM)."""
    total = max(1, column_height - 2 * cr.TOP_MARGIN_ROWS)
    track = BAR_BOTTOM - BAR_TOP
    length = max(8, min(track, int(round(track * VISIBLE_ROWS / total))))
    limit = scroll_range(column_height)
    top = BAR_TOP + (int(round((track - length) * min(scroll, limit) / limit)) if limit > 0 else 0)
    return BAR_X[0], top, BAR_X[1] - 1, top + length - 1


def _draw_bottom_bar(canvas: Image.Image, info: PageInfo, chrome: Chrome, glyphs: cr.Glyphs) -> None:
    bar = chrome.bottom_bar.get(info.buttons) if chrome.bottom_bar else None
    if bar is None:
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((CARD_X, BOTTOM_BAR_ROW, CARD_X + 319, CANVAS[1] - 1), fill=(222, 222, 216, 255))
        return
    canvas.alpha_composite(bar, (CARD_X, BOTTOM_BAR_ROW))
    if info.large:
        # The crop reads "Збільшити" (the small pages' label): cover the word with the bar's own gradient and
        # write "Зменшити" where the word starts.
        x = ZOOM_LABEL_X[info.buttons]
        patch = bar.crop((x - CARD_X - 2, 0, 320 - 6, 28))
        strip = patch.crop((patch.width - 4, 0, patch.width, 28)).resize(patch.size, Image.Resampling.NEAREST)
        canvas.alpha_composite(strip, (x - 2, BOTTOM_BAR_ROW))
        _draw_text(canvas, glyphs, "Зменшити", x - 1.5, BOTTOM_LABEL_BASELINE, BOTTOM_LABEL_FONT, BOTTOM_LABEL_FONT * 1.2,
                   BOTTOM_LABEL_INK)


def _text_width(glyphs: cr.Glyphs, text: str, scale_x: float, char_space: float) -> float:
    return sum(glyphs.metrics(ord(ch))[2] * scale_x for ch in text) + char_space * max(0, len(text) - 1)


def _draw_text(canvas: Image.Image, glyphs: cr.Glyphs, text: str, x: float, baseline: float, size_x: float,
               size_y: float, colour: Tuple[int, int, int, int]) -> None:
    """Chrome text with the system font: `x` is the pen start, `baseline` the canvas row of the baseline."""
    scale_x = size_x / glyphs.width
    scale_y = size_y / glyphs.height
    top = baseline - glyphs.ascent * scale_y
    cell_w = glyphs.font.sheets.cell_width * scale_x
    cell_h = glyphs.font.sheets.cell_height * scale_y
    pen = x
    for ch in text:
        code = ord(ch)
        cell = glyphs.cell(code)
        if cell is not None and not ch.isspace():
            left, _glyph_w, _char_w = glyphs.metrics(code)
            cr.PageRenderer._blit_glyph(canvas, cell, pen + left * scale_x, top, cell_w, cell_h, colour, colour, 255)
        pen += glyphs.metrics(code)[2] * scale_x
