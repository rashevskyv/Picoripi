"""Professor Layton and the Spectre's Call (DS): ``GFNT`` bitmap fonts (``fnt/font_en2.cf``, ``color.cp`` ...).

A GFNT file (Level-5 compressed inside ``lt4_main_uk.fa``): ``GFNT``, u32 entry count of the first table, u32 0x18
(where the entries start), u32 end of the entries, u32 start of the glyph data, u32 glyph data length; then 6-byte
entries -- u16 character code (ASCII or Shift-JIS), u8 flags, u8 width, u16 data offset -- a 24-byte tail and the
glyphs. A glyph is ``width`` columns by 11 rows of 1-bit pixels, row after row, the lowest bit first, padded to
4 bytes (a width above 11 -- the second table of ``color.cp`` -- is a glyph 11 columns wide). The data offset is
16 bits: it starts again from 0 after 65532 and the glyphs after the wrap lie 0x10000 further.

The editor shows the glyphs in a grid of 12 x 12 cells; the pixels of a cell inside the glyph's width are the
glyph. Packing writes every glyph's bytes again in place; widths, codes and offsets stay as they are.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, Tuple

from PIL import Image

from core.containers import level5, lz10
from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

CELL = 12
ROWS = 11
COLUMNS = 64


def _plain(data: bytes) -> Tuple[bytes, bool]:
    if data[:4] == b"GFNT":
        return bytes(data), False
    plain = level5.decompress(data)
    if plain[:4] != b"GFNT":
        raise ValueError("not a GFNT font")
    return plain, True


def is_font(data: bytes) -> bool:
    try:
        return _plain(data)[0][:4] == b"GFNT"
    except (ValueError, IndexError):
        return False


def _glyph_bytes(width: int) -> int:
    bits = min(width, 11) * ROWS
    size = (bits + 7) // 8
    return size + (-size % 4)


def _entries(plain: bytes):
    _count, start, end, data_at, data_size = struct.unpack_from("<5I", plain, 4)
    entries, block, previous = [], 0, -1
    for i in range((end - start) // 6):
        code, flags, width, offset = struct.unpack_from("<HBBH", plain, start + 6 * i)
        if offset < previous:
            block += 1
        previous = offset
        entries.append((code, flags, width, block * 0x10000 + offset))
    return entries, data_at, data_size


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    plain, _compressed = _plain(data)
    entries, data_at, data_size = _entries(plain)
    count = len(entries)
    lines = -(-count // COLUMNS)
    stride = COLUMNS * CELL
    ink = bytearray(stride * lines * CELL)
    widths = []
    for glyph, (code, _flags, width, offset) in enumerate(entries):
        w = min(width, 11)
        widths.append(w)
        raw = plain[data_at + offset:data_at + offset + _glyph_bytes(width)]
        x0, y0 = (glyph % COLUMNS) * CELL, (glyph // COLUMNS) * CELL
        for i in range(w * ROWS):
            if raw[i >> 3] >> (i & 7) & 1:
                ink[(y0 + i // w) * stride + x0 + i % w] = 255
    sheet = grey_sheet(Image.frombytes("L", (stride, lines * CELL), bytes(ink)))
    first: Dict[int, int] = {}
    for glyph, (code, *_rest) in enumerate(entries):
        first.setdefault(char_code(chr(code)) if 0x20 <= code < 0x7F else code, glyph)
    pairs = sorted(first.items())
    metadata = {
        "header": {"signature": "Layton GFNT font", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": 9, "descent": 2, "width": 6, "leading": 12, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": CELL, "cell_height": CELL,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": lines, "texture_width": stride, "texture_height": lines * CELL}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count,
                  "packets": [{"kerning": 0, "width": w} for w in widths]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    plain, compressed = _plain(original)
    entries, data_at, _size = _entries(plain)
    ink = coverage(sheets[0]).tobytes()
    stride = sheets[0].width
    out = bytearray(plain)
    for glyph, (_code, _flags, width, offset) in enumerate(entries):
        w = min(width, 11)
        if not w:
            continue
        x0, y0 = (glyph % COLUMNS) * CELL, (glyph // COLUMNS) * CELL
        bits = bytearray(plain[data_at + offset:data_at + offset + _glyph_bytes(width)])    # padding stays as it is
        for i in range(w * ROWS):
            if ink[(y0 + i // w) * stride + x0 + i % w] >= 128:
                bits[i >> 3] |= 1 << (i & 7)
            else:
                bits[i >> 3] &= ~(1 << (i & 7)) & 0xFF
        out[data_at + offset:data_at + offset + len(bits)] = bits
    if bytes(out) == plain:
        return bytes(original)
    if not compressed:
        return bytes(out)
    return struct.pack("<I", len(out) << 3 | 1) + lz10.compress(bytes(out))[4:]
