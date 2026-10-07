"""M2 (emote) PSB fonts: Metal Gear Solid Master Collection's menu fonts (``system/font/*.psb``).

The PSB (version 4) holds ``code`` -- ``{character: {x, y, w, h, id, a, b, d, ...}}``: the glyph's box
``w`` x ``h`` at ``x, y`` of page ``id``, its left bearing ``a``, its top ``b`` above the baseline and its
advance ``d`` -- and ``source``, the pages: ``{type, width, height, pixel}`` with ``pixel`` a resource of raw
pixels (``A8``; ``A8L8`` = bytes L, A; ``RGBA8`` = bytes B, G, R, A). The ink is the alpha.

The editor sheet has one cell per glyph (by character code), each glyph's box placed so that the baselines
line up (``OFFS1``: its place in the cell). Packing writes each glyph's box back into its page in place:
the boxes and the metrics stay as they are (a PSB version 4 is not written again), so a glyph may be redrawn
within its box but not widened. A "character" far bigger than the others (a picture kept in the font) is
left out of the sheet. Packing an unedited model gives the file back.
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Tuple

from PIL import Image

from core import m2_psb
from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

COLUMNS = 64
BIG = 4                      # a glyph more than BIG times the middle size is a picture, not a letter
_BYTES = {"A8": 1, "A8L8": 2, "RGBA8": 4}


def is_m2_font(data: bytes) -> bool:
    if bytes(data[:4]) != b"PSB\0":
        return False
    try:
        root = m2_psb.load(bytes(data))[0]
    except (ValueError, IndexError, KeyError, UnicodeDecodeError):
        return False
    return isinstance(root, dict) and root.get("id") == "font" and isinstance(root.get("code"), dict)


def _font(data: bytes):
    root, psb = m2_psb.load(bytes(data))
    if root.get("id") != "font":
        raise ValueError("Not an M2 font")
    pages = []
    for page in root["source"]:
        kind = page["type"]
        if kind not in _BYTES:
            raise ValueError(f"M2 font page format {kind} is not supported")
        offset, size = psb.chunk_spans[int(page["pixel"])]
        if size < page["width"] * page["height"] * _BYTES[kind]:
            raise ValueError("M2 font page shorter than its size")
        pages.append({"type": kind, "width": int(page["width"]), "height": int(page["height"]), "offset": offset})
    glyphs = sorted(((char_code(ch), ch, g) for ch, g in root["code"].items() if len(ch) == 1), key=lambda t: t[0])
    if glyphs:      # a few fonts keep big pictures (a 500 x 235 bar) as characters: they stay out of the sheet
        mid_w = statistics.median(float(g["w"]) for _c, _ch, g in glyphs)
        mid_h = statistics.median(int(g["h"]) for _c, _ch, g in glyphs)
        glyphs = [t for t in glyphs if float(t[2]["w"]) <= BIG * max(mid_w, 1) and int(t[2]["h"]) <= BIG * max(mid_h, 1)]
    return root, pages, glyphs


def _alpha(data: bytes, page: Dict[str, Any]) -> Image.Image:
    n, w, h, at = _BYTES[page["type"]], page["width"], page["height"], page["offset"]
    raw = data[at:at + w * h * n]
    return Image.frombytes("L", (w, h), bytes(raw[n - 1::n]))


def _layout(glyphs) -> Tuple[int, int, int]:
    top = max(int(g["b"]) for _c, _ch, g in glyphs)
    cell_w = max(math.ceil(float(g["w"])) for _c, _ch, g in glyphs) + 2
    cell_h = max(top - int(g["b"]) + int(g["h"]) for _c, _ch, g in glyphs) + 2
    return top, cell_w, cell_h


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    root, pages, glyphs = _font(data)
    inks = [_alpha(data, page) for page in pages]
    top, cell_w, cell_h = _layout(glyphs)
    rows = (len(glyphs) + COLUMNS - 1) // COLUMNS
    sheet = Image.new("L", (COLUMNS * cell_w, rows * cell_h))
    offsets = []
    for i, (_code, _ch, g) in enumerate(glyphs):
        x, y, w, h = int(g["x"]), int(g["y"]), math.ceil(float(g["w"])), int(g["h"])
        dx, dy = 1, 1 + top - int(g["b"])
        box = inks[int(g["id"])].crop((x, y, x + w, y + h))
        sheet.paste(box, (i % COLUMNS * cell_w + dx, i // COLUMNS * cell_h + dy))
        offsets.append([dx, dy])
    metadata = {
        "header": {"signature": "M2FONT", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": top + 1, "descent": cell_h - top - 1, "width": cell_w,
                  "leading": cell_h, "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": len(glyphs) - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "texture_format": 0, "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": COLUMNS * cell_w, "texture_height": rows * cell_h}],
        "MAP1": [map_entries([(code, i) for i, (code, _ch, _g) in enumerate(glyphs)])],
        "WID1": [{"first_code_included": 0, "last_code_included": len(glyphs),
                  "packets": [{"kerning": -int(g["a"]), "width": int(round(float(g["d"])))} for _c, _ch, g in glyphs]}],
        "OFFS1": offsets,
    }
    return metadata, [grey_sheet(sheet)]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    _root, pages, glyphs = _font(original)
    inks = [_alpha(original, page) for page in pages]
    _top, cell_w, cell_h = _layout(glyphs)
    ink = coverage(sheets[0])
    offsets = metadata.get("OFFS1") or []
    out = bytearray(original)
    for i, (_code, _ch, g) in enumerate(glyphs):
        x, y, w, h = int(g["x"]), int(g["y"]), math.ceil(float(g["w"])), int(g["h"])
        dx, dy = offsets[i] if i < len(offsets) else (1, 1)
        cx, cy = i % COLUMNS * cell_w + dx, i // COLUMNS * cell_h + dy
        new = ink.crop((cx, cy, cx + w, cy + h))
        page = pages[int(g["id"])]
        if new.tobytes() == inks[int(g["id"])].crop((x, y, x + w, y + h)).tobytes():
            continue
        n, stride = _BYTES[page["type"]], page["width"] * _BYTES[page["type"]]
        values = new.tobytes()
        for row in range(h):
            for col in range(w):
                at = page["offset"] + (y + row) * stride + (x + col) * n
                alpha = values[row * w + col]
                if n == 1:
                    out[at] = alpha
                elif n == 2:
                    out[at:at + 2] = bytes((255, alpha))
                else:
                    out[at:at + 4] = bytes((255, 255, 255, alpha))
    return bytes(out) if out != original else original


def glyph_chars(data: bytes) -> List[str]:
    """The characters the font has a glyph for."""
    return [ch for _code, ch, _g in _font(data)[2]]
