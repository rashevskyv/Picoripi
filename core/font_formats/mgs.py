"""Proportional 2bpp font of the MGS2 engine (Metal Gear Solid: The Twin Snakes, ext 0x11 files).

Layout (little-endian)::

    u16 data_offset, 6 bytes kept as they are,
    (data_offset - 8) / 4 entries ``u16 glyph offset, u16 flags``  -- glyph i is code first_code + i
    glyph bitmaps from data_offset

``(flags >> 4) & 0x1F`` is the glyph's width minus one. ``flags >> 9`` moves the glyph down by
half that many pixels when it is drawn (a glyph with a descender is stored higher so that it fits
the cell); the model keeps the other bits per glyph in ``metadata["MGS"]["flags"]``.
A bitmap is ``width x height`` pixels of 2 bits, row after row with no padding between rows,
high bits first. The advance of a glyph is its width.

Parameters (from the plugin's font source): ``height`` (rows per glyph), ``first_code``,
``upper_codepage`` (the encoding that names the codes from 0x80, e.g. ``mac_roman``), optional
``columns`` and ``ascent``.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

CELL = 32          # widest glyph the 5-bit width field can describe
WIDTH_BITS = 0x1F0


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _table(data: bytes) -> Tuple[int, List[Tuple[int, int]]]:
    if len(data) < 12:
        raise ValueError("Font file too short")
    data_offset = struct.unpack_from("<H", data, 0)[0]
    if data_offset < 12 or (data_offset - 8) % 4 or data_offset > len(data):
        raise ValueError(f"Not an MGS font (data offset {data_offset:#x})")
    count = (data_offset - 8) // 4
    entries = [struct.unpack_from("<HH", data, 8 + 4 * i) for i in range(count)]
    return data_offset, entries


def _bitmap_size(width: int, height: int) -> int:
    return (width * height * 2 + 7) // 8


def _decode(data: bytes, width: int, height: int) -> List[int]:
    pixels = []
    for byte in data:
        pixels += [(byte >> 6) & 3, (byte >> 4) & 3, (byte >> 2) & 3, byte & 3]
    return pixels[:width * height]


def _encode(pixels: List[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(pixels), 4):
        quad = (pixels[i:i + 4] + [0, 0, 0])[:4]
        out.append(quad[0] << 6 | quad[1] << 4 | quad[2] << 2 | quad[3])
    return bytes(out)


def _char(code: int, params: Dict[str, Any]) -> str:
    if code < 0x80:
        return chr(code)
    return bytes([code]).decode(str(params.get("upper_codepage") or "latin-1"), "replace")


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    height = _int(params.get("height", 24))
    first = _int(params.get("first_code", 0x20))
    columns = _int(params.get("columns", 16))
    data_offset, entries = _table(data)
    count = len(entries)
    rows = -(-count // columns)
    ink = bytearray(columns * CELL * rows * height)
    stride = columns * CELL
    packets = []
    for glyph, (offset, flags) in enumerate(entries):
        width = ((flags & WIDTH_BITS) >> 4) + 1
        start = data_offset + offset
        pixels = _decode(data[start:start + _bitmap_size(width, height)], width, height)
        x0, y0 = (glyph % columns) * CELL, (glyph // columns) * height
        for y in range(height):
            for x in range(width):
                ink[(y0 + y) * stride + x0 + x] = pixels[y * width + x] * 85
        packets.append({"kerning": 0, "width": width})
    sheet = grey_sheet(Image.frombytes("L", (stride, rows * height), bytes(ink)))
    pairs = [(char_code(_char(first + glyph, params)), glyph) for glyph in range(count)]
    ascent = _int(params.get("ascent", height))
    metadata = {
        "header": {"signature": "MGS font", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": ascent, "descent": height - ascent,
                  "width": packets[0]["width"] if packets else 8, "leading": height,
                  "fallback_code": first, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": CELL, "cell_height": height,
                  "page_data_size": len(data) - data_offset, "texture_format": 0,
                  "glyph_horizontal_count": columns, "glyph_vertical_count": rows,
                  "texture_width": stride, "texture_height": rows * height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count, "packets": packets}],
        "MGS": {"flags": [flags & ~WIDTH_BITS for _offset, flags in entries]},
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    height = _int(params.get("height", 24))
    columns = _int(params.get("columns", 16))
    data_offset, entries = _table(original)
    packets = metadata["WID1"][0]["packets"]
    flag_list = (metadata.get("MGS") or {}).get("flags") or []
    ink = coverage(sheets[0]).tobytes()
    stride = sheets[0].width
    table = bytearray(original[:data_offset])
    body = bytearray()
    changed = False
    for glyph, (offset, flags) in enumerate(entries):
        old_width = ((flags & WIDTH_BITS) >> 4) + 1
        width = max(1, min(CELL, int(packets[glyph]["width"]))) if glyph < len(packets) else old_width
        x0, y0 = (glyph % columns) * CELL, (glyph // columns) * height
        pixels = [min(3, (ink[(y0 + y) * stride + x0 + x] + 42) // 85) for y in range(height) for x in range(width)]
        old = original[data_offset + offset:data_offset + offset + _bitmap_size(old_width, height)]
        bitmap = _encode(pixels)
        new_flags = int(flag_list[glyph]) & ~WIDTH_BITS if glyph < len(flag_list) else flags & ~WIDTH_BITS
        if new_flags != flags & ~WIDTH_BITS:
            changed = True
        if width == old_width and _decode(old, width, height) == pixels:
            bitmap = old                       # keep the original bytes, padding bits included
        else:
            changed = True
        if len(body) > 0xFFFF:
            raise ValueError("Font data grew past 64 KB; make some glyphs narrower")
        struct.pack_into("<HH", table, 8 + 4 * glyph, len(body), new_flags | ((width - 1) << 4))
        body += bitmap
    if not changed:
        return bytes(original)
    last_offset, last_flags = entries[-1]
    tail_start = data_offset + last_offset + _bitmap_size(((last_flags & WIDTH_BITS) >> 4) + 1, height)
    return bytes(table + body + original[tail_start:])
