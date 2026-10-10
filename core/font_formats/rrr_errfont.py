"""The disc error font of Rayman Raving Rabbids 2 (Wii): ``rrr2/misc/err_msg.fnt`` with its texture
``err_msg_8bits.tex`` as the companion file (one ``sources.join_pair`` blob).

``err_msg.fnt``: 16-byte glyph records, then u16 (little endian) record count. A record: the character (an
ASCII byte after a zero byte, or the two Shift-JIS bytes swapped), u16 x, u16 y (big endian), u8 width, u8
height, then three spacing bytes a, b, c stored + 0x80 (left gap, glyph width, right gap), zero padding.
``err_msg_8bits.tex``: u16 width, u16 height (little endian), then 8-bit intensity pixels, top row first.

The model copies every glyph rectangle into a cell of a 16-column grid; the glyph width is a + b + c, its
kerning -a. Packing writes back the changed cells (intensity = the ink of the colour) and changed widths (as
b, the glyph's own width); rectangles and codes stay, so an unedited model packs to the original bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, map_entries
from core.font_formats.sources import join_pair, split_pair

COLUMNS = 16


def _records(fnt: bytes) -> List[Dict[str, Any]]:
    count = struct.unpack_from("<H", fnt, len(fnt) - 2)[0]
    out = []
    for i in range(count):
        r = fnt[i * 16:i * 16 + 16]
        char = chr(r[1]) if r[0] == 0 else bytes([r[1], r[0]]).decode("shift_jis", errors="replace")
        x, y = struct.unpack_from(">HH", r, 2)
        out.append({"char": char, "box": (x, y, x + r[6], y + r[7]), "a": r[8] - 0x80, "b": r[9] - 0x80,
                    "c": r[10] - 0x80})
    return out


def _picture(tex: bytes) -> Image.Image:
    w, h = struct.unpack_from("<HH", tex)
    grey = Image.frombytes("L", (w, h), tex[4:4 + w * h])
    return Image.merge("RGBA", (Image.new("L", (w, h), 255),) * 3 + (grey,))


def _cells(records) -> Tuple[int, int]:
    return (max(r["box"][2] - r["box"][0] for r in records), max(r["box"][3] - r["box"][1] for r in records))


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    fnt, tex = split_pair(data)
    records, picture = _records(fnt), _picture(tex)
    cell_w, cell_h = _cells(records)
    rows = -(-len(records) // COLUMNS)
    sheet = Image.new("RGBA", (COLUMNS * cell_w, rows * cell_h))
    for i, r in enumerate(records):
        sheet.paste(picture.crop(r["box"]), ((i % COLUMNS) * cell_w, (i // COLUMNS) * cell_h))
    packets = [{"kerning": -r["a"], "width": r["a"] + r["b"] + r["c"]} for r in records]
    metadata = {
        "header": {"signature": "err_msg.fnt", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": cell_h, "descent": 0, "width": packets[0]["width"], "leading": cell_h,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": rows * COLUMNS - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries([(char_code(r["char"]), i) for i, r in enumerate(records)])],
        "WID1": [{"first_code_included": 0, "last_code_included": len(records), "packets": packets}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    fnt, tex = split_pair(original)
    records, picture = _records(fnt), _picture(tex)
    cell_w, cell_h = _cells(records)
    alpha = bytearray(tex[4:])
    w = picture.width
    out_fnt = bytearray(fnt)
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    for i, r in enumerate(records):
        x, y = (i % COLUMNS) * cell_w, (i // COLUMNS) * cell_h
        x0, y0, x1, y1 = r["box"]
        cell = sheets[0].convert("RGBA").crop((x, y, x + x1 - x0, y + y1 - y0))
        if cell.tobytes() != picture.crop(r["box"]).tobytes():
            for k, (cr, cg, cb, ca) in enumerate(cell.getdata()):
                alpha[(y0 + k // cell.width) * w + x0 + k % cell.width] = min(max(cr, cg, cb), ca)
        if i < len(packets):
            b = int(packets[i]["width"]) - r["a"] - r["c"]
            if b != r["b"]:
                out_fnt[i * 16 + 9] = max(0, min(255, b + 0x80))
    return join_pair(bytes(out_fnt), bytes(tex[:4]) + bytes(alpha))
