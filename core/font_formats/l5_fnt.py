"""Level-5 ``FNT`` bitmap fonts of Fantasy Life (3DS): a code list and one 4-bit bitmap per glyph.

Layout (little endian)::

    0x00 "FNT "  u16 cell width  u16 cell height  u16 N  u16 2*N
    0x0C N * u16 character codes (the first two are 0x0A, the line break; the other ascending), padded to 4 bytes
    u32 N, then N * u32 offsets, each relative to its own position, to
    a glyph record: u32 advance, u32 bitmap size, the bitmap (4 bits per pixel, the low nibble first, rows of the
    cell width rounded up to an even number of pixels), the record padded to 4 bytes

The model is one sheet with glyph ``i`` in cell ``i`` (64 cells per row). Packing writes the bitmaps of the cells
that changed and the advances; a font keeps the characters it has.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, map_entries

ADDS_GLYPHS = False
COLUMNS = 64


def detect(data: bytes) -> bool:
    return bytes(data[:4]) == b"FNT " and len(data) > 0x20


def _parse(data: bytes) -> Dict[str, Any]:
    if not detect(data):
        raise ValueError("Not a Level-5 FNT font")
    width, height, count, size = struct.unpack_from("<4H", data, 4)
    if size != 2 * count or 0x0C + size > len(data):
        raise ValueError("Broken FNT header")
    codes = list(struct.unpack_from(f"<{count}H", data, 0x0C))
    table = (0x0C + size + 3) & ~3
    if struct.unpack_from("<I", data, table)[0] != count:
        raise ValueError("Broken FNT offset table")
    records = []
    for i in range(count):
        at = table + 4 + 4 * i
        pos = at + struct.unpack_from("<I", data, at)[0]
        advance, bitmap = struct.unpack_from("<II", data, pos)
        records.append((pos, advance, bitmap))
    row = (width + 1) // 2
    if any(size != row * height for _pos, _adv, size in records):
        raise ValueError("FNT bitmaps do not match the cell size")
    return {"width": width, "height": height, "count": count, "codes": codes, "records": records, "row": row}


def _cell(data: bytes, info: Dict[str, Any], index: int) -> Image.Image:
    pos = info["records"][index][0] + 8
    w, h, row = info["width"], info["height"], info["row"]
    cell = Image.new("RGBA", (w, h))
    px = cell.load()
    for y in range(h):
        for x in range(w):
            byte = data[pos + y * row + x // 2]
            v = (byte >> 4 if x & 1 else byte & 15) * 17
            px[x, y] = (255, 255, 255, v)
    return cell


def _model_code(code: int) -> int:
    return 0xF0000 + code if 0x80 <= code <= 0x9F else char_code(chr(code))


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    info = _parse(data)
    w, h, count = info["width"], info["height"], info["count"]
    rows = -(-count // COLUMNS)
    sheet = Image.new("RGBA", (COLUMNS * w, rows * h))
    for i in range(count):
        sheet.paste(_cell(data, info, i), ((i % COLUMNS) * w, (i // COLUMNS) * h))
    pairs, seen = [], set()
    for i, code in enumerate(info["codes"]):
        if code not in seen:
            seen.add(code)
            pairs.append((_model_code(code), i))
    packets = [{"kerning": 0, "width": rec[1]} for rec in info["records"]]
    metadata = {
        "header": {"signature": "FNT", "num_chunks": 4, "texture_format": "I4"},
        "INF1": [{"encoding": 1, "ascent": h * 4 // 5, "descent": h - h * 4 // 5, "width": w // 2, "leading": h,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": w, "cell_height": h,
                  "page_data_size": w * h * count // 2, "texture_format": 0, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count - 1, "packets": packets}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    info = _parse(original)
    w, h, count, row = info["width"], info["height"], info["count"], info["row"]
    first: Dict[int, int] = {}
    for i, code in enumerate(info["codes"]):
        first.setdefault(code, i)
    wanted = {_model_code_inverse(c): g for c, g in char_map(metadata).items()}
    changed = [c for c, i in first.items() if wanted.get(c) != i]
    if changed:
        raise ValueError("This font keeps the characters it has; changed or removed: "
                         + " ".join(f"U+{c:04X}" for c in sorted(changed)[:10]))
    sheet = sheets[0].convert("RGBA")
    packets = metadata["WID1"][0]["packets"]
    out = bytearray(original)
    for i in range(count):
        pos, advance, _size = info["records"][i]
        box = ((i % COLUMNS) * w, (i // COLUMNS) * h, (i % COLUMNS) * w + w, (i // COLUMNS) * h + h)
        cell = sheet.crop(box)
        if cell.tobytes() != _cell(original, info, i).tobytes():
            ink = coverage(cell).load()
            body = bytearray(row * h)
            for y in range(h):
                for x in range(w):
                    v = min(15, (ink[x, y] + 8) // 17)
                    body[y * row + x // 2] |= v << 4 if x & 1 else v
            out[pos + 8:pos + 8 + len(body)] = body
        if i < len(packets):
            width = max(0, min(0xFF, int(packets[i]["width"])))
            if width != advance:
                struct.pack_into("<I", out, pos, width)
    return bytes(out)


def _model_code_inverse(char: str) -> int:
    code = char_code(char)
    return code - 0xF0000 if code >= 0xF0000 else (ord(char) if 0x80 <= code <= 0x9F else code)
