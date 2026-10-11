"""Peace Walker (HD / Master Collection) fonts ``FONT/*_FONT.xpr``: an XPR2 resource pack (big-endian) holding a
``FontTexture`` (8-bit linear atlas) and ``FontData``.

XPR2: ``"XPR2", u32 header size, u32 data size, u32 count``, then ``count`` 24-byte entries ``type, offset, size, 0,
name offset, 0`` (offsets from byte 12); the texture's pixels are the data block after the header (``12 + header size``).
FontData: 0x18 bytes of header, a table ``u16 [0x10000 - 0xA0]`` code -> glyph number (0 = no glyph; glyph number
n is record n - 1), then 16-byte records ``u16 left, top, right, bottom, i16 x offset, u16 width, u16 advance, 0``.

Model: one cell per record, 32 to a row, the record's rectangle of the atlas in grey (``grey_sheet``). Widths
are the advances. Packing an unedited model gives the original bytes; a redrawn cell is written back into its
rectangle, a changed width becomes the record's advance. New characters are not added.
"""
from __future__ import annotations

import math
import struct
from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

_COLUMNS = 32
_TABLE_AT = 0x18
_RECORD = 16


def is_pw_xpr(data: bytes) -> bool:
    return bytes(data[:4]) == b"XPR2" and b"FontData" in bytes(data[:0x200])


def _layout(data: bytes):
    """(texture offset, width, height, FontData offset, FontData size)."""
    _magic, header, size, count = struct.unpack_from(">4sIII", data, 0)
    font = None
    for index in range(count):
        kind, offset, length, _zero, name_at = struct.unpack_from(">4sIIII", data, 16 + 24 * index)
        name = bytes(data[12 + name_at:data.index(b"\0", 12 + name_at)])
        if kind == b"USER" and name == b"FontData":
            font = (12 + offset, length)
    if font is None:
        raise ValueError("XPR2 without FontData")
    side = int(math.isqrt(size))
    width, height = (side, side) if side * side == size else (4096, size // 4096)
    return 12 + header, width, height, font[0], font[1]


def _records(data: bytes, at: int, length: int):
    codes = (length - _TABLE_AT) // 2
    table_end = at + _TABLE_AT
    # the table runs until the records start: records fill the rest of FontData exactly
    count = 0
    for table_len in range(0xFF00, 0x10001):
        rest = length - _TABLE_AT - 2 * table_len
        if rest > 0 and rest % _RECORD == 0:
            last = struct.unpack_from(">H", data, table_end + 2 * (table_len - 1))[0]
            if last and last == rest // _RECORD:
                count, codes = rest // _RECORD, table_len
                break
    if not count:
        raise ValueError("FontData: cannot find where the glyph records start")
    table = struct.unpack_from(f">{codes}H", data, table_end)
    records_at = table_end + 2 * codes
    records = [list(struct.unpack_from(">4HhHHH", data, records_at + _RECORD * i)) for i in range(count)]
    return table, records, records_at


def _read(data: bytes):
    tex_at, width, height, font_at, font_len = _layout(data)
    atlas = Image.frombytes("L", (width, height), bytes(data[tex_at:tex_at + width * height]))
    table, records, records_at = _records(data, font_at, font_len)
    return atlas, table, records, records_at, tex_at


def _grid(records):
    cell_w = max([max(1, r[2] - r[0]) for r in records] or [1])
    cell_h = max([max(1, r[3] - r[1]) for r in records] or [1])
    return cell_w, cell_h, max(1, -(-len(records) // _COLUMNS))


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    atlas, table, records, _at, _tex = _read(bytes(data))
    cell_w, cell_h, rows = _grid(records)
    ink = Image.new("L", (_COLUMNS * cell_w, rows * cell_h), 0)
    for index, (left, top, right, bottom, *_rest) in enumerate(records):
        row, column = divmod(index, _COLUMNS)
        if right > left and bottom > top:
            ink.paste(atlas.crop((left, top, right, bottom)), (column * cell_w, row * cell_h))
    pairs = [(char_code(chr(code)), number - 1) for code, number in enumerate(table) if number]
    packets = [{"kerning": 0, "width": record[6]} for record in records]
    metadata = {
        "header": {"signature": "Peace Walker XPR2 font", "textures_editable": True},
        "INF1": [{"encoding": 1, "ascent": cell_h, "descent": 0, "width": cell_w, "leading": cell_h,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": len(records) - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "glyph_horizontal_count": _COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": _COLUMNS * cell_w, "texture_height": rows * cell_h}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": len(records), "packets": packets}],
    }
    return metadata, [grey_sheet(ink)]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    """``original`` when nothing changed; else the redrawn cells in the atlas and the changed advances."""
    original = bytes(original)
    atlas, _table, records, records_at, tex_at = _read(original)
    again, again_sheets = extract(original, params)
    cell_w, cell_h, _rows = _grid(records)
    drawn = sheets[0].convert("RGBA") if sheets else again_sheets[0]
    old = again_sheets[0]
    out = bytearray(original)
    atlas_changed = False
    for index, (left, top, right, bottom, *_rest) in enumerate(records):
        row, column = divmod(index, _COLUMNS)
        cell = (column * cell_w, row * cell_h, column * cell_w + right - left, row * cell_h + bottom - top)
        if right > left and bottom > top and drawn.crop(cell).tobytes() != old.crop(cell).tobytes():
            atlas.paste(coverage(drawn.crop(cell)), (left, top))
            atlas_changed = True
    if atlas_changed:
        pixels = atlas.tobytes()
        out[tex_at:tex_at + len(pixels)] = pixels
    for index, (old_p, new_p) in enumerate(zip(again["WID1"][0]["packets"], metadata["WID1"][0]["packets"])):
        if old_p["width"] != new_p["width"]:
            struct.pack_into(">H", out, records_at + _RECORD * index + 12, int(new_p["width"]))
    return bytes(out)
