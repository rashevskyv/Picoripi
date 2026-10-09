"""Monolith Soft LAFT bitmap fonts (``.wifnt`` of the Switch Xenoblade games): a grid of fixed cells in one
Tegra R8 MIBL atlas, each glyph with its code point and its left and right ink edges inside the cell.

Layout (little endian): ``LAFT``, 10001, 0, glyph table offset, entries offset (2132), glyph count, bucket table
offset (84), 512, 511, texture offset, texture size, grid offset, 4, 20. Buckets: 512 x (u16 first entry,
u16 count): a code point is looked up in bucket ``code & 511``, whose entries (u16 glyph ids, sorted by code)
point into the glyph table (u16 code, u8 left, u8 right). Grid: u32 texture width, height, cell width (36),
cell height (41), columns, rows: glyph ``i`` is cell ``i`` row by row, cells are one pixel apart (pitch 37 x 42),
the texture ends with one more gap and is padded to 4 pixels. The texture (a MIBL block, see ``core.texture_formats.mibl``) starts on a
4096-byte page.

Model: one sheet whose cells are ``pitch`` wide and high (the gap included), ``WID1`` kerning = left edge,
width = right - left. ``params["free_rows"]`` (default 8) adds that many empty rows of cells to the sheet, for
new letters: on save the atlas grows to the last row that has ink or a character. Packing an unedited model gives
the original bytes back.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_map, char_code, coverage, grey_sheet, map_entries
from core.texture_formats import mibl

ADDS_GLYPHS = True
MAGIC = b"LAFT"
HEADER = struct.Struct("<4s13I")
HEADER_SIZE = 0x54
BUCKETS = 512
ENTRIES_AT = HEADER_SIZE + BUCKETS * 4
PAGE = 4096
GAP = 1
R8 = 1


def is_laft(data: bytes) -> bool:
    return bytes(data[:4]) == MAGIC


def _parse(data: bytes):
    (magic, _version, _zero, glyphs_at, _entries_at, count, _buckets_at, _b, _mask, tex_at, _tex_size, grid_at,
     _u4, _u20) = HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise ValueError("Not a LAFT font")
    glyphs = [struct.unpack_from("<HBB", data, glyphs_at + 4 * i) for i in range(count)]
    width, height, cell_w, cell_h, columns, rows = struct.unpack_from("<6I", data, grid_at)
    return glyphs, (width, height, cell_w, cell_h, columns, rows), tex_at


def _atlas(data: bytes, tex_at: int) -> Image.Image:
    """The R8 atlas as one channel of ink."""
    return mibl.read(data[tex_at:], {})[0].image.getchannel("R")


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    glyphs, (width, height, cell_w, cell_h, columns, rows), tex_at = _parse(data)
    pitch_w, pitch_h = cell_w + GAP, cell_h + GAP
    free_rows = int(params.get("free_rows", 8))
    total_rows = rows + free_rows
    ink = Image.new("L", (columns * pitch_w, total_rows * pitch_h), 0)
    ink.paste(_atlas(data, tex_at).crop((0, 0, min(width, ink.width), min(height, ink.height))), (0, 0))
    count = columns * total_rows
    packets = [{"kerning": 0, "width": cell_w} for _ in range(count)]
    for index, (code, left, right) in enumerate(glyphs):
        packets[index] = {"kerning": left, "width": right - left}
    metadata = {
        "header": {"signature": "LAFT", "num_chunks": 4, "glyph_count": len(glyphs), "rows": rows},
        "INF1": [{"encoding": 0, "ascent": cell_h, "descent": 0, "width": cell_w, "leading": cell_h,
                  "fallback_code": glyphs[0][0] if glyphs else 0x20, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": pitch_w, "cell_height": pitch_h,
                  "page_data_size": 0, "texture_format": R8, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": total_rows, "texture_width": ink.width, "texture_height": ink.height}],
        "MAP1": [map_entries([(char_code(chr(code)), index) for index, (code, _l, _r) in enumerate(glyphs)])],
        "WID1": [{"first_code_included": 0, "last_code_included": count, "packets": packets}],
    }
    return metadata, [grey_sheet(ink)]


def _used_rows(ink: Image.Image, mapping: Dict[int, int], columns: int, pitch_h: int, original_rows: int) -> int:
    rows = original_rows
    if mapping:
        rows = max(rows, max(mapping) // columns + 1)
    box = ink.point(lambda v: 255 if v else 0).getbbox()
    if box:
        rows = max(rows, -(-box[3] // pitch_h))
    return rows


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    glyphs, (width, height, cell_w, cell_h, columns, rows), tex_at = _parse(original)
    pitch_w, pitch_h = cell_w + GAP, cell_h + GAP
    mapping = {glyph: ord(char) for char, glyph in char_map(metadata).items()}   # glyph id -> code point
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    ink = coverage(sheets[0])
    old = _atlas(original, tex_at)
    new_rows = _used_rows(ink, mapping, columns, pitch_h, rows)
    count = max([len(glyphs), *(g + 1 for g in mapping)])
    table: List[Tuple[int, int, int]] = []
    for index in range(count):
        code = mapping.get(index, 0xE000 + index)
        packet = packets[index] if index < len(packets) else {"kerning": 0, "width": cell_w}
        left = int(packet.get("kerning", 0))
        table.append((code, max(0, min(255, left)), max(0, min(255, left + int(packet.get("width", 0))))))
    new_w, new_h = -(-(columns * pitch_w + GAP) // 4) * 4, -(-(new_rows * pitch_h + GAP) // 4) * 4   # a trailing gap, padded to 4
    atlas = Image.new("L", (new_w, new_h), 0)
    atlas.paste(ink.crop((0, 0, min(ink.width, new_w), min(ink.height, new_h))), (0, 0))
    same_atlas = (new_w, new_h) == (width, height) and atlas.tobytes() == old.tobytes()
    if same_atlas and table == glyphs:
        return bytes(original)
    # tables
    by_bucket: Dict[int, List[int]] = {}
    for index, (code, _l, _r) in enumerate(table):
        by_bucket.setdefault(code & (BUCKETS - 1), []).append(index)
    buckets, entries = bytearray(), []
    for bucket in range(BUCKETS):
        ids = sorted(by_bucket.get(bucket, []), key=lambda i: table[i][0])
        buckets += struct.pack("<HH", len(entries), len(ids))
        entries += ids
    entries_blob = struct.pack(f"<{len(entries)}H", *entries)
    entries_blob += bytes(-len(entries_blob) % 4)
    glyphs_at = ENTRIES_AT + len(entries_blob)
    grid_at = glyphs_at + 4 * count
    body = bytearray(original[:HEADER_SIZE]) + buckets + entries_blob
    for code, left, right in table:
        body += struct.pack("<HBB", code, left, right)
    body += struct.pack("<6I", new_w, new_h, cell_w, cell_h, columns, new_rows)
    new_tex_at = -(-len(body) // PAGE) * PAGE
    body += bytes(new_tex_at - len(body))
    if same_atlas:
        texture = original[tex_at:]
    else:
        rgba = Image.merge("RGBA", (atlas, Image.new("L", atlas.size, 0), Image.new("L", atlas.size, 0),
                                    Image.new("L", atlas.size, 255)))
        texture = mibl.build(rgba, R8, 1)
    struct.pack_into("<I", body, 0x0C, glyphs_at)
    struct.pack_into("<I", body, 0x14, count)
    struct.pack_into("<I", body, 0x24, new_tex_at)
    struct.pack_into("<I", body, 0x28, len(texture))
    struct.pack_into("<I", body, 0x2C, grid_at)
    return bytes(body) + texture
