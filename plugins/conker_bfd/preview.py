"""Source-metric preview and width of Conker text: glyph metrics from the decompiled text code.

Rules (decompilation, reading only): the lookup maps an input byte to a glyph index (lowercase folds to uppercase;
a byte with no map entry falls back to its own value). Index 0x60 is the space: advance 4, line at least 12.
Index 0xA8 and up are icons: advance = width x scale from the code's table (below). A glyph advances by its width
plus header byte 2, drawn at pen + header byte 2; its line extent is height + 1 + header byte 3. Byte 0xBC is a
three-byte control code and takes no space. A line break moves down by the line extent (minimum 12).

Not verified against an emulator frame: canvas size (320 x 240 is assumed), box position and colours, the wrap
width, icon artwork (drawn as a gap), and the scale globals (taken as 1.0, the value the chapter text uses).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from PIL import Image

from .font import Glyph, glyph_index

CANVAS = (320, 240)
SPACE_ADVANCE = 4
MIN_LINE_HEIGHT = 12
NEWLINE = 0x0A
CONTROL_CODE = 0xBC
SHADOW_OFFSET = (1, 1)
ICON_FALLBACK = (12, 1.0)
# index -> (width, scale), from func_150415E0 (indices 0xA8-0xFF; others use ICON_FALLBACK).
ICON_WIDTHS = {
    0xA8: (0x20, 1.0), 0xA9: (0x20, 1.0),
    0xAA: (0x20, 0.603), 0xAB: (0x20, 0.603), 0xAC: (0x20, 0.603), 0xAD: (0x20, 0.603),
    0xAE: (0x10, 1.0), 0xAF: (0x2E, 1.0), 0xB0: (0x2E, 1.0),
    0xB1: (0x26, 0.726),
    0xB6: (0x10, 1.0), 0xB7: (0x10, 1.0), 0xB8: (0x10, 1.0), 0xB9: (0x10, 1.0),
    0xBA: (0x37, 1.0),
}


@dataclass(frozen=True)
class Metric:
    width: int
    height: int
    meta: bytes  # header bytes 2 and 3: horizontal and vertical offset


def metrics_of(glyphs: Sequence[Glyph]) -> List[Metric]:
    return [Metric(width=g.width, height=g.height, meta=g.meta) for g in glyphs]


def _icon_advance(index: int) -> int:
    width, scale = ICON_WIDTHS.get(index, ICON_FALLBACK)
    return int(width * scale)


def _place(text: bytes, metrics: Sequence[Metric], glyph_map: bytes):
    """Yield (kind, x, y, metric or None) in text order. kind: glyph, icon, space or newline."""
    x = 0
    y = 0
    line_height = 0
    pos = 0
    while pos < len(text):
        byte = text[pos]
        pos += 1
        if byte == NEWLINE:
            yield ("newline", x, y, None)
            y += max(line_height, MIN_LINE_HEIGHT)
            x = 0
            line_height = 0
            continue
        if byte == CONTROL_CODE:
            pos += 2  # the two bytes after the code are its arguments
            continue
        if byte == 0x20:
            yield ("space", x, y, None)
            x += SPACE_ADVANCE
            line_height = max(line_height, MIN_LINE_HEIGHT)
            continue
        index = glyph_index(byte, glyph_map)
        if index is None:
            index = byte  # the lookup falls back to the input byte
        if index >= 0xA8:
            yield ("icon", x, y, None)
            x += _icon_advance(index)
            line_height = max(line_height, MIN_LINE_HEIGHT)
            continue
        if index >= len(metrics):
            continue  # 0x61-0xA7 have no glyph and no icon: the game draws nothing measurable
        metric = metrics[index]
        yield ("glyph", x + metric.meta[0], y + metric.meta[1], index)
        x += metric.width + metric.meta[0]
        line_height = max(line_height, metric.height + 1 + metric.meta[1], MIN_LINE_HEIGHT)


def layout_line_items(text: bytes, glyphs: Sequence[Glyph], glyph_map: bytes) -> List[Tuple[int, int, Glyph]]:
    """Glyphs to draw as (x, y, glyph) in canvas space. Icons and spaces draw nothing."""
    items: List[Tuple[int, int, Glyph]] = []
    for kind, x, y, index in _place(text, glyphs, glyph_map):
        if kind == "glyph":
            items.append((x, y, glyphs[index]))
    return items


def measure_px(text: bytes, metrics: Sequence[Metric], glyph_map: bytes) -> int:
    """Width in pixels of the widest line, as the game sums it (advances, icons, spaces)."""
    widest = 0
    x = 0
    pos = 0
    while pos < len(text):
        byte = text[pos]
        pos += 1
        if byte == NEWLINE:
            widest = max(widest, x)
            x = 0
            continue
        if byte == CONTROL_CODE:
            pos += 2
            continue
        if byte == 0x20:
            x += SPACE_ADVANCE
            continue
        index = glyph_index(byte, glyph_map)
        if index is None:
            index = byte
        if index >= 0xA8:
            x += _icon_advance(index)
            continue
        if index >= len(metrics):
            continue
        x += metrics[index].width + metrics[index].meta[0]
    return max(widest, x)


def _glyph_layer(glyph: Glyph, colour: Tuple[int, int, int]) -> Image.Image:
    mask = Image.frombytes("L", (glyph.width, glyph.height), glyph.pixels)
    layer = Image.new("RGBA", (glyph.width, glyph.height), colour + (0,))
    layer.putalpha(mask)
    return layer


def render_text(text: bytes, glyphs: Sequence[Glyph], glyph_map: bytes,
                origin: Tuple[int, int] = (16, 16), zoom: int = 1,
                canvas_size: Tuple[int, int] = CANVAS) -> Image.Image:
    """Draw ``text`` on a transparent canvas, with the glyph shadow. ``zoom`` is a whole-number factor."""
    if zoom < 1:
        raise ValueError("zoom must be a whole number of at least 1")
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    items = layout_line_items(text, glyphs, glyph_map)
    ox, oy = origin
    for colour, dx, dy in (((0, 0, 0), SHADOW_OFFSET[0], SHADOW_OFFSET[1]), ((255, 255, 255), 0, 0)):
        for gx, gy, glyph in items:
            x, y = ox + gx + dx, oy + gy + dy
            if x < 0 or y < 0 or x + glyph.width > canvas_size[0] or y + glyph.height > canvas_size[1]:
                continue
            canvas.alpha_composite(_glyph_layer(glyph, colour), (x, y))
    if zoom > 1:
        canvas = canvas.resize((canvas_size[0] * zoom, canvas_size[1] * zoom), Image.NEAREST)
    return canvas
