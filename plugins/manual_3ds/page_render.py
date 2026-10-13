"""Draws one manual page as the console shows it: a 320 px column of text, with the owner's layout model.

The page is read from Manual.bcma through the folder's own tools (see repo_tools). A BCLYT pane is placed
relative to its parent group, so the position of a pane on the page is the sum of its ancestors' translations
(read here from the order of the file's sections). Sub-pages (K = 0..n) are stacked, each under the one before.
Text is wrapped with manual.layout_for, the same call the console build uses. Pictures are not decoded: each
picture pane is drawn as a grey box of its size.

Overflow is shown in red: a piece that ends past its line's right limit, and every line the paragraph has no
pane for.
"""
from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QPainter

from plugins.manual_3ds.repo_tools import Tools

COLUMN_WIDTH = 400          # the image is wider than the 320 px column: an overflow past the edge stays visible
SCREEN_COLUMN = 320         # the column width on the console
TEXT_RGB = (0, 0, 0)
OVERFLOW_RGB = (200, 0, 0)
PAPER_RGB = (255, 255, 255)
PICTURE_RGB = (214, 214, 214)
PICTURE_EDGE_RGB = (150, 150, 150)
OVERFLOW_FILL = (255, 0, 0, 56)
PAGE_PATTERN = re.compile(r"Page_(\d+)_(large|small)_(\d+)")
STRING_KEY_PATTERN = re.compile(r"(large|small)/Page_(\d+)_(large|small)_\d+")
PANE_KINDS = (b"pan1", b"pic1", b"txt1", b"wnd1", b"bnd1")
TRANSLATE_AT = 0x24
PANE_SIZE_AT = 0x44
PANE_NAME_AT = 0x0C
PANE_NAME_LEN = 0x18


class RenderCancelled(Exception):
    """The caller asked the render to stop."""


@dataclass
class SubPage:
    """One sub-page: its paragraphs (manual Flow objects, in the order the keys use) and its boxes."""

    key: str                                   # "large/Page_003_large_0"
    flows: List[Any]
    # Text pane name -> (x, y) on the sub-page. y is BCLYT's: 0 at the top, negative below.
    positions: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    pictures: List[Tuple[float, float, float, float]] = field(default_factory=list)  # x, top, width, height
    extent: float = 0.0                        # the height the sub-page takes in the column


@dataclass
class ColumnRender:
    """The result of one page render."""

    image: QImage
    height: float
    overflow_keys: Set[str] = field(default_factory=set)
    missing_glyphs: Set[str] = field(default_factory=set)
    failed_keys: Dict[str, str] = field(default_factory=dict)
    sub_pages: List[Tuple[str, float]] = field(default_factory=list)   # key and the offset it is drawn at
    title: str = ""                            # the page's fixed heading texts (the tab bar of the viewer)


def _panes(data: bytes) -> Iterator[Tuple[bytes, str, float, float, float, float]]:
    """Every pane of a BCLYT file in file order: (kind, name, x, y, width, height) with x and y on the page.

    A pane is placed relative to the pane that opened its group (pas1 .. pae1), so each one adds the
    translations of its ancestors. Rotation and scale of the groups are not applied.
    """
    header = struct.unpack_from("<H", data, 0x06)[0]
    count = struct.unpack_from("<H", data, 0x10)[0]
    pos = header
    stack: List[Tuple[float, float]] = []
    last = (0.0, 0.0)
    for _ in range(count):
        magic = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        if magic == b"pas1":
            stack.append(last)
        elif magic == b"pae1" and stack:
            stack.pop()
        elif magic in PANE_KINDS:
            x, y = struct.unpack_from("<ff", data, pos + TRANSLATE_AT)
            width, height = struct.unpack_from("<ff", data, pos + PANE_SIZE_AT)
            name = data[pos + PANE_NAME_AT:pos + PANE_NAME_AT + PANE_NAME_LEN].split(b"\0")[0].decode("ascii", "replace")
            parent_x, parent_y = stack[-1] if stack else (0.0, 0.0)
            last = (parent_x + x, parent_y + y)
            yield magic, name, last[0], last[1], width, height
        pos += size


def groups_of(tools: Tools, path: Any) -> Dict[str, List[SubPage]]:
    """Every page group of a manual -> {"large/Page_003_large": [SubPage, ...] in K order}."""
    archive = tools.bcma.load(path)
    flows_by_key = tools.manual.pages_of(archive, tools.manual.BASE_SLOT)
    groups: Dict[str, List[SubPage]] = {}
    for part in ("large", "small"):
        for file_name, data in archive.read(f"{tools.manual.BASE_SLOT}_{part}").items():
            name = file_name.removesuffix(".bclyt")
            match = PAGE_PATTERN.fullmatch(name)
            if not match:
                continue
            positions: Dict[str, Tuple[float, float]] = {}
            pictures: List[Tuple[float, float, float, float]] = []
            extent = 0.0
            for magic, pane_name, x, y, width, height in _panes(data):
                if magic == b"txt1":
                    positions[pane_name] = (x, y)
                elif magic == b"pic1":
                    pictures.append((x, -y, width, height))
                if magic in (b"txt1", b"pic1", b"wnd1") or pane_name.startswith("__AREA"):
                    extent = max(extent, -y + height)
            key = f"{part}/{name}"
            sub = SubPage(key=key, flows=flows_by_key.get(key, []), positions=positions,
                          pictures=pictures, extent=extent)
            groups.setdefault(f"{part}/Page_{match.group(1)}_{part}", []).append(sub)
    for subs in groups.values():
        subs.sort(key=lambda sub: int(PAGE_PATTERN.fullmatch(sub.key.split("/", 1)[1]).group(3)))
    return groups


def group_key_of(string_key: str) -> Optional[str]:
    """"small/Page_003_small_1#4" -> "small/Page_003_small", or None for an index entry."""
    match = STRING_KEY_PATTERN.fullmatch(string_key.split("#", 1)[0])
    if not match:
        return None
    return f"{match.group(1)}/Page_{match.group(2)}_{match.group(1)}"


def is_over(x_end: float, margin: float, cap: float) -> bool:
    """A piece that ends past its line's right limit. The tolerance matches manual.layout's own check."""
    return x_end > margin + cap + 0.01


def _glyph_image(font: Any, bcfnt: Any, code: int, rgb: Tuple[int, int, int], cache: Dict[Any, Any]) -> Any:
    key = (code, rgb)
    if key in cache:
        return cache[key]
    image = None
    if code in font.cmap:
        rows = bcfnt.glyph_rows(font, code)
        height = len(rows)
        width = len(rows[0]) if height else 0
        if width and height:
            image = QImage(width, height, QImage.Format.Format_ARGB32)
            image.fill(0)
            red, green, blue = rgb
            for y, row in enumerate(rows):
                for x, value in enumerate(row):
                    alpha = value[1] if isinstance(value, tuple) else value
                    if alpha:
                        image.setPixelColor(x, y, QColor(red, green, blue, min(255, int(alpha) * 17)))
    cache[key] = image
    return image


def _line_place(sub: SubPage, flow: Any, line_index: int, placed: Dict[str, Tuple[float, float]]) -> Tuple[float, float]:
    """-> (top, dx) of a line on the sub-page: its top edge, and how far its pieces move from the x of the flow.

    A line sits on the position of its first text pane. A line the paragraph has no pane for is put one line
    height under the last pane line. ``placed`` remembers the last line of the paragraph.
    """
    if line_index < len(flow.lines):
        first = next((pane for pane in flow.lines[line_index] if pane.is_text), None)
        if first is not None:
            x, y = sub.positions.get(first.name, (first.x, first.y))
            placed["last"] = (-y, x - first.x)
            return placed["last"]
    top, dx = placed.get("last", (0.0, 0.0))
    return top + (line_index - (len(flow.lines) - 1)) * flow.line_height, dx


def _pane_cap(flow: Any, index: int, manual: Any) -> float:
    """The right limit of a pane line, relative to its margin (manual.layout's cap_of)."""
    return min(flow.pane_box(index) - manual.LINE_OFFSET, manual.PAGE_EDGE - flow.pane_x(index)) - manual.PANE_MARGIN


def render_column(tools: Tools, font: Any, widths: Dict[int, int], homoglyphs: Dict[str, str],
                  groups: Dict[str, List[SubPage]], group_key: str, texts: Dict[str, str],
                  budgets: Dict[str, Any], should_stop: Optional[Callable[[], bool]] = None) -> ColumnRender:
    """Lay out and draw the page group ``group_key`` with the current ``texts`` (string key -> translation)."""
    manual = tools.manual
    subs = groups.get(group_key, [])
    total = sum(sub.extent for sub in subs)
    image = QImage(COLUMN_WIDTH, max(1, int(math.ceil(total)) + 1), QImage.Format.Format_ARGB32)
    image.fill(QColor(*PAPER_RGB))
    result = ColumnRender(image=image, height=total)
    painter = QPainter(image)
    glyph_cache: Dict[Any, Any] = {}
    try:
        offset = 0.0
        for sub_index, sub in enumerate(subs):
            result.sub_pages.append((sub.key, offset))
            for x, top, width, height in sub.pictures:
                _draw_picture(painter, x, offset + top, width, height)
            for index, flow in enumerate(sub.flows):
                if should_stop is not None and should_stop():
                    raise RenderCancelled()
                key = f"{sub.key}#{index}"
                text = texts.get(key)
                if text is None:
                    continue
                try:
                    rendered = manual.apply_homoglyphs(text, homoglyphs)
                    budget = budgets.get(key)
                    # No budget (or a zero one: no localisation drew the paragraph) -> the screen edge.
                    limit = (float(budget) if budget else SCREEN_COLUMN) + manual.WIDTH_SLACK
                    lines = manual.layout_for(rendered, flow, limit, widths)
                except Exception as exc:  # a text the model cannot lay out is shown in red, not dropped
                    result.failed_keys[key] = repr(exc)
                    result.overflow_keys.add(key)
                    continue
                if _draw_flow(painter, sub, flow, lines, limit, offset, result, font, tools, widths,
                              glyph_cache, manual):
                    result.overflow_keys.add(key)
                if flow.fixed and sub_index == 0 and lines and lines[0]:
                    result.title += "".join(piece.text for piece in lines[0] if piece.icon is None).strip() + " "
            offset += sub.extent
    finally:
        painter.end()
    result.title = result.title.strip()
    return result


def _draw_flow(painter: QPainter, sub: SubPage, flow: Any, lines: List[List[Any]], limit: float, offset: float,
               result: ColumnRender, font: Any, tools: Tools, widths: Dict[int, int], glyph_cache: Dict[Any, Any],
               manual: Any) -> bool:
    """Draw one laid-out paragraph. True when a piece is past its line or the text needs more lines than the page has."""
    pane_model = manual.is_pane_model(flow)
    flagged = False
    placed: Dict[str, Tuple[float, float]] = {}
    for line_index, line in enumerate(lines):
        rel_top, dx = _line_place(sub, flow, line_index, placed)
        top = offset + rel_top
        beyond_pane = line_index >= len(flow.lines)
        if pane_model and not beyond_pane:
            margin = flow.pane_x(line_index)
            cap = _pane_cap(flow, line_index, manual)
        else:
            margin = flow.margin(min(line_index, len(flow.lines) - 1))
            cap = limit
        if beyond_pane:
            flagged = True
            painter.fillRect(QRectF(margin + dx, top, cap, flow.line_height), QColor(*OVERFLOW_FILL))
        for piece in line:
            if piece.icon is not None:
                continue
            over = beyond_pane or is_over(piece.x + piece.width, margin, cap)
            flagged = flagged or over
            if over and not beyond_pane:
                painter.fillRect(QRectF(piece.x + dx, top, piece.width, flow.line_height), QColor(*OVERFLOW_FILL))
            rgb = OVERFLOW_RGB if over else TEXT_RGB
            _draw_piece(painter, piece.text, piece.x + dx, top, flow, font, tools, widths, rgb,
                        glyph_cache, result.missing_glyphs, manual)
    return flagged


def _draw_piece(painter: QPainter, text: str, x: float, top: float, flow: Any, font: Any, tools: Tools,
                widths: Dict[int, int], rgb: Tuple[int, int, int], cache: Dict[Any, Any],
                missing: Set[str], manual: Any) -> None:
    scale = (flow.font_size or 24.0) / 24.0
    cell_w = font.sheets.cell_width * scale
    cell_h = font.sheets.cell_height * scale
    cx = x
    for ch in text:
        advance = manual.measure(ch, flow, widths)
        if not ch.isspace():
            glyph = _glyph_image(font, tools.bcfnt, ord(ch), rgb, cache)
            if glyph is None:
                missing.add(ch)
            else:
                # The glyph's ink starts `left` units after its pen position (the font's CWDH left value).
                left = font.widths[font.cmap[ord(ch)]][0] if font.cmap[ord(ch)] < len(font.widths) else 0
                painter.drawImage(QRectF(cx + left * scale, top, cell_w, cell_h), glyph)
        cx += advance


def _draw_picture(painter: QPainter, x: float, top: float, width: float, height: float) -> None:
    rect = QRectF(x, top, width, height)
    painter.fillRect(rect, QColor(*PICTURE_RGB))
    painter.setPen(QColor(*PICTURE_EDGE_RGB))
    painter.drawRect(rect)
