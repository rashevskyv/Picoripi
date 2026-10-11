"""PhyreEngine bitmap fonts (``*.fgen.NXGL.phyre``; Dragon Quest Builders 1, Switch).

A ``PBitmapFont`` cluster: the Phyre class table, then the character records, then the texture record and,
as the last bytes, the atlas (8 bits per pixel, a signed distance field). A character record is 45 bytes:
u32 code, f32 0, f32 0, f32 x, f32 y, f32 width, f32 height, f32 offset x, f32 offset y, f32 advance, u8 rotated.
The rectangle (x, y, width, height) is in the atlas rows as stored; a rotated glyph lies on its side there with
the sides swapped (width and height name the upright glyph).

Model: one cell per character, 32 to a row, holding the upright glyph rectangle; the sheet is grey (the field).
Packing an unedited model gives the file back; a redrawn cell is written into its atlas rectangle. Advances
and new characters are not changed: a new character needs a new record and a new rectangle in the atlas.
"""
from __future__ import annotations

import math
import struct
from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

_COLUMNS = 32
_RECORD = 45


def _records(data: bytes):
    """(first record offset, [(code, x, y, w, h, off_x, off_y, advance, rotated)], end offset)."""
    section = 84 + struct.unpack_from("<I", data, 8)[0]
    for start in range(section, section + 0x600):
        at, prev, out = start, 0, []
        while at + _RECORD <= len(data):
            code = struct.unpack_from("<I", data, at)[0]
            f = struct.unpack_from("<10f", data, at + 4)
            if not (0x20 <= code < 0x110000 and code > prev and data[at + 44] in (0, 1)
                    and all(math.isfinite(v) and -2000 <= v < 20000 for v in f)):
                break
            out.append((code, int(f[2]), int(f[3]), int(f[4]), int(f[5]), f[6], f[7], f[8], data[at + 44]))
            prev, at = code, at + _RECORD
        if len(out) >= 8:
            return start, out, at
    raise ValueError("Not a Phyre bitmap font")


def _atlas(data: bytes, end: int) -> Tuple[int, int, int]:
    """(width, height, offset of the first pixel): 8 bits per pixel, the last bytes of the file."""
    for at in range(end, min(end + 0x100, len(data) - 26)):
        _marker, _a, _b, _c, width, height, one, zero = struct.unpack_from("<BIIIIIIB", data, at)
        if zero == 0 and one == 1 and 16 <= width <= 8192 and 16 <= height <= 8192 and width * height <= len(data) - end:
            return width, height, len(data) - width * height
    raise ValueError("The Phyre bitmap font has no 8-bit texture record")


def _box(record) -> Tuple[int, int, int, int]:
    _code, x, y, w, h, *_rest, rotated = record
    return (x, y, x + h, y + w) if rotated else (x, y, x + w, y + h)


def _upright(crop: Image.Image, rotated: int) -> Image.Image:
    if rotated:
        return crop.transpose(Image.Transpose.ROTATE_270).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return crop


def _stored(upright: Image.Image, rotated: int) -> Image.Image:
    if rotated:
        return upright.transpose(Image.Transpose.FLIP_LEFT_RIGHT).transpose(Image.Transpose.ROTATE_90)
    return upright


def detect(data: bytes) -> bool:
    if bytes(data[:4]) != b"RYHP" or b"PBitmapFont" not in bytes(data[:0x1000]):
        return False
    try:
        _atlas(bytes(data), _records(bytes(data))[2])
    except (ValueError, struct.error):
        return False
    return True


def _cell_size(records) -> Tuple[int, int]:
    return max(r[3] for r in records), max(r[4] for r in records)


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    _start, records, end = _records(data)
    width, height, base = _atlas(data, end)
    atlas = Image.frombytes("L", (width, height), data[base:])
    cell_w, cell_h = _cell_size(records)
    rows = max(1, -(-len(records) // _COLUMNS))
    ink = Image.new("L", (_COLUMNS * cell_w, rows * cell_h), 0)
    for index, record in enumerate(records):
        row, column = divmod(index, _COLUMNS)
        glyph = _upright(atlas.crop(_box(record)), record[8])
        ink.paste(glyph, (column * cell_w, row * cell_h))
    pairs = [(char_code(chr(r[0])), index) for index, r in enumerate(records)]
    metadata = {
        "header": {"signature": "PhyreEngine bitmap font", "textures_editable": True},
        "INF1": [{"encoding": 1, "ascent": cell_h, "descent": 0, "width": cell_w, "leading": cell_h,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": len(records) - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "glyph_horizontal_count": _COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": _COLUMNS * cell_w, "texture_height": rows * cell_h}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": len(records),
                  "packets": [{"kerning": 0, "width": round(r[7])} for r in records]}],
    }
    return metadata, [grey_sheet(ink)]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    """``original`` when nothing changed; else the redrawn cells written into their atlas rectangles."""
    _start, records, end = _records(original)
    width, height, base = _atlas(original, end)
    _again, again_sheets = extract(original, params)
    if not sheets:
        return bytes(original)
    drawn, old = sheets[0].convert("RGBA"), again_sheets[0]
    cell_w, cell_h = _cell_size(records)
    atlas = Image.frombytes("L", (width, height), original[base:])
    changed = False
    for index, record in enumerate(records):
        row, column = divmod(index, _COLUMNS)
        cell = (column * cell_w, row * cell_h, column * cell_w + record[3], row * cell_h + record[4])
        if drawn.crop(cell).tobytes() != old.crop(cell).tobytes():
            left, top, _right, _bottom = _box(record)
            atlas.paste(_stored(coverage(drawn.crop(cell)), record[8]), (left, top))
            changed = True
    if not changed:
        return bytes(original)
    return bytes(original[:base]) + atlas.tobytes()
