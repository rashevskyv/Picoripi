"""Dragon Quest IX (DS) fonts: ``data/pack_lv5/fi_<name>.bin`` (glyph list) + ``fd_<name>.bin`` (pixels) (``dq9``).

The two files come as one ``join_pair`` blob (``fi`` first, ``fd`` the companion).

``fd``: ``1.0\\0``, u16 strip width, u16 height, u32 pixel bytes, u32 header size (16), then one strip of 1-bit
pixels, rows of ``width / 8`` bytes, high bit first (1 = ink).

``fi``: ``1.1\\0``, u32 glyph count, u32 kerning pair count, u32 header size (24), u32 glyph table offset, u32
name area offset; the kerning pairs (4 bytes, kept as they are); one 8-byte entry per glyph: u32 offset of its
name (in the file), u8 width, u8 flags (kept), u16 x of the glyph in the strip; the NUL-terminated names. A name
is the text the glyph draws: one character (``A``) or a tag (``<1>`` the apostrophe, ``<`a>`` à...). The game
matches names against the text bytes, so a new glyph is named with the UTF-8 bytes of its character.

The model: one cell (16 x height) per glyph, the cell's left ``width`` columns being the glyph; MAP1 maps the
one-character names. Packing writes changed pixels in place; a changed width or a new glyph (a letter typed into
one of the ``spare`` empty cells) lays the strip out again (one empty column between glyphs) and rewrites the
glyph table. An unedited font packs to the same bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, grey_sheet, map_entries
from core.font_formats.sources import join_pair, split_pair

ADDS_GLYPHS = True
CELL_W = 16
COLUMNS = 16


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _read(blob: bytes):
    fi, fd = split_pair(blob)
    if fi[:4] != b"1.1\0" or fd[:4] != b"1.0\0":
        raise ValueError("Not a Dragon Quest IX font (fi / fd)")
    count, kerning, _head, table, names_at = struct.unpack_from("<5I", fi, 4)
    width, height, size, data_at = struct.unpack_from("<HHII", fd, 4)
    glyphs = []
    for i in range(count):
        name_at, glyph_w, flags, x = struct.unpack_from("<IBBH", fi, table + 8 * i)
        name = fi[name_at:fi.index(b"\0", name_at)]
        glyphs.append({"name": name, "width": glyph_w, "flags": flags, "x": x})
    stride = width // 8
    pixels = fd[data_at:data_at + size]
    return fi, fd, glyphs, (width, height, stride, pixels), (kerning, table, names_at)


def _ink(strip, x: int, y: int) -> bool:
    _w, _h, stride, pixels = strip
    return bool(pixels[y * stride + x // 8] >> (7 - x % 8) & 1)


def _name_char(name: bytes):
    try:
        text = name.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if len(text) == 1 else None


def extract(data: bytes, params: Dict[str, Any]):
    _fi, _fd, glyphs, strip, _k = _read(data)
    height = strip[1]
    total = len(glyphs) + _int(params.get("spare", 0))
    rows = -(-total // COLUMNS)
    ink = Image.new("L", (COLUMNS * CELL_W, rows * height))
    px = ink.load()
    for i, glyph in enumerate(glyphs):
        cx, cy = (i % COLUMNS) * CELL_W, (i // COLUMNS) * height
        for x in range(min(glyph["width"], CELL_W)):
            for y in range(height):
                if glyph["x"] + x < strip[0] and _ink(strip, glyph["x"] + x, y):
                    px[cx + x, cy + y] = 255
    pairs = []
    for i, glyph in enumerate(glyphs):
        char = _name_char(glyph["name"])
        if char is not None:
            pairs.append((char_code(char), i))
    widths = [g["width"] for g in glyphs] + [0] * (total - len(glyphs))
    metadata: Metadata = {
        "header": {"signature": "DQ9F", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": height - 2, "descent": 2, "width": 6, "leading": height,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": total - 1, "cell_width": CELL_W, "cell_height": height,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": rows, "texture_width": COLUMNS * CELL_W, "texture_height": rows * height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": total,
                  "packets": [{"kerning": 0, "width": w + 1} for w in widths]}],
    }
    return metadata, [grey_sheet(ink)]


def _cell_columns(ink: Image.Image, index: int, width: int, height: int) -> List[List[bool]]:
    px = ink.load()
    cx, cy = (index % COLUMNS) * CELL_W, (index // COLUMNS) * height
    return [[px[cx + x, cy + y] >= 128 for y in range(height)] for x in range(width)]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    fi, fd, glyphs, strip, (kerning, table, names_at) = _read(original)
    width, height, stride, pixels = strip
    ink = coverage(sheets[0])
    total = len(glyphs) + _int(params.get("spare", 0))
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    widths = [max(0, min(CELL_W, int(p.get("width", 1)) - 1)) for p in packets[:total]]
    widths += [0] * (total - len(widths))
    mapped = char_map(metadata)
    new = []                                     # (index, name) of letters typed into spare cells
    for char, index in sorted(mapped.items(), key=lambda item: item[1]):
        if index >= len(glyphs) and index < total:
            new.append((index, char.encode("utf-8")))
    for index, _name in new:
        if not widths[index]:
            columns = _cell_columns(ink, index, CELL_W, height)
            widths[index] = max([x + 1 for x, col in enumerate(columns) if any(col)] or [1])
    relayout = bool(new) or any(widths[i] != g["width"] for i, g in enumerate(glyphs))
    if not relayout:
        out = bytearray(pixels)
        for i, glyph in enumerate(glyphs):
            for x, column in enumerate(_cell_columns(ink, i, glyph["width"], height)):
                sx = glyph["x"] + x
                if sx >= width:
                    continue
                for y, on in enumerate(column):
                    at, bit = y * stride + sx // 8, 0x80 >> (sx % 8)
                    out[at] = out[at] | bit if on else out[at] & ~bit
        data_at = struct.unpack_from("<I", fd, 12)[0]
        return join_pair(fi, fd[:data_at] + bytes(out) + fd[data_at + len(pixels):])
    order = list(range(len(glyphs))) + [index for index, _name in new]
    names = {i: g["name"] for i, g in enumerate(glyphs)}
    names.update(dict(new))
    xs, at = {}, 0
    for i in order:
        xs[i] = at
        at += widths[i] + 1
    strip_w = -(-at // 8) * 8
    new_stride = strip_w // 8
    out = bytearray(new_stride * height)
    for i in order:
        for x, column in enumerate(_cell_columns(ink, i, widths[i], height)):
            sx = xs[i] + x
            for y, on in enumerate(column):
                if on:
                    out[y * new_stride + sx // 8] |= 0x80 >> (sx % 8)
    if strip_w > 0xFFFF:
        raise ValueError("The font strip is too wide")
    fd_head = bytearray(fd[:struct.unpack_from("<I", fd, 12)[0]])
    struct.pack_into("<HHI", fd_head, 4, strip_w, height, len(out))
    new_table = bytearray()
    name_area = bytearray()
    first_name = table + 8 * len(order)
    for i in order:
        flags = glyphs[i]["flags"] if i < len(glyphs) else 1
        new_table += struct.pack("<IBBH", first_name + len(name_area), widths[i], flags, xs[i])
        name_area += names[i] + b"\0"
    old_names_end = max(fi.index(b"\0", g_at) + 1 for g_at in
                        (struct.unpack_from("<I", fi, table + 8 * k)[0] for k in range(len(glyphs))))
    tail = fi[old_names_end:]                        # bytes after the names (padding), kept
    fi_new = bytearray(fi[:table]) + new_table + name_area + tail
    struct.pack_into("<I", fi_new, 4, len(order))
    struct.pack_into("<I", fi_new, 20, first_name)
    return join_pair(bytes(fi_new), bytes(fd_head) + bytes(out))
