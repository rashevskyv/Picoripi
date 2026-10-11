"""Arc System Works ``.jfnt`` fonts of the 3DS (Dragon Ball Fusions): the atlas type.

Layout (little endian): ``jFNT``, u32, four bytes (``00 2C 00 01``: the atlas type; ``00 2F 00 04`` is the packed
outline type of ``default01.jfnt``, not read), four bytes (cell width - 3, cell height - 3, ...), u16 range count,
``count`` ranges of u16 (first code, last code, first glyph), u16 glyph count, a metrics table (two bytes per
glyph and more), and an embedded ``jIMG`` A8 atlas (``core/texture_formats/jimg``) at a 0x80-aligned offset.

The glyphs lie in the atlas row by row in cells of ``(a + 3) x (b + 3)`` pixels, as many to a row as fit. The model
is that cell grid. Glyph pictures are edited and written back in place; the metrics table and the ranges are kept
(``ADDS_GLYPHS`` is off: a new letter would need new ranges and metrics, which are not decoded).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries
from core.texture_formats import jimg

ADDS_GLYPHS = False


def _parse(data: bytes) -> Dict[str, Any]:
    if data[:4] != b"jFNT" or len(data) < 0x20:
        raise ValueError("Not a jFNT font")
    if data[8:10] != b"\x00\x2c":
        raise ValueError("This jFNT font is the packed outline type (default01), which is not supported")
    a, b = data[12], data[13]
    count = struct.unpack_from("<H", data, 0x10)[0]
    ranges = [struct.unpack_from("<3H", data, 0x12 + i * 6) for i in range(count)]
    at = 0x12 + count * 6
    glyphs = struct.unpack_from("<H", data, at)[0]
    pos = data.find(b"jIMG", at)
    if pos < 0:
        raise ValueError("No atlas in the jFNT font")
    tex = jimg.info(data, pos)
    cw, ch = a + 3, b + 3
    columns = max(1, tex["width"] // cw)
    rows = -(-glyphs // columns)
    if rows * ch > tex["height"]:
        raise ValueError("The glyph cells do not fit the atlas")
    return {"ranges": ranges, "glyphs": glyphs, "table": at + 2, "jimg": pos, "tex": tex, "cw": cw, "ch": ch,
            "columns": columns, "rows": rows}


def _atlas(data: bytes, font: Dict[str, Any]) -> Image.Image:
    t = font["tex"]
    from core.texture_formats import surface
    return surface.read(data, t["at"], t["codec"], t["width"], t["height"])


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = _parse(data)
    cw, ch, columns, rows = font["cw"], font["ch"], font["columns"], font["rows"]
    ink = _atlas(data, font).convert("RGBA").split()[-1]
    sheet = ink.crop((0, 0, columns * cw, rows * ch)).copy()
    table = data[font["table"]:font["table"] + font["glyphs"] * 2]
    packets = [{"kerning": table[2 * i] if len(table) > 2 * i + 1 else 0,
                "width": table[2 * i + 1] if len(table) > 2 * i + 1 else cw}
               for i in range(font["glyphs"])]
    packets += [{"kerning": 0, "width": 0} for _ in range(columns * rows - len(packets))]
    pairs, seen = [], set()
    for first, last, glyph in font["ranges"]:
        for code in range(first, last + 1):
            g = glyph + code - first
            if code not in seen and g < font["glyphs"]:
                seen.add(code)
                pairs.append((char_code(chr(code)), g))
    metadata = {
        "header": {"signature": "jFNT", "num_chunks": 1},
        "INF1": [{"encoding": 1, "ascent": ch * 3 // 4, "descent": ch - ch * 3 // 4, "width": cw, "leading": ch,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": columns * rows - 1, "cell_width": cw, "cell_height": ch,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": columns * rows - 1, "packets": packets}],
    }
    return metadata, [grey_sheet(sheet)]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    from core.texture_formats import surface
    font = _parse(original)
    gly = metadata["GLY1"][0]
    if (gly["cell_width"], gly["cell_height"], gly["glyph_horizontal_count"]) != (font["cw"], font["ch"], font["columns"]):
        raise ValueError("The font's cell grid changed; it cannot be written back")
    old = _atlas(original, font)
    plane = old.convert("RGBA").split()[-1].copy()
    new_ink = coverage(sheets[0])
    box = (0, 0, font["columns"] * font["cw"], font["rows"] * font["ch"])
    if new_ink.size != (box[2], box[3]):
        raise ValueError("The font sheet changed size; it cannot be written back")
    if new_ink.tobytes() == plane.crop(box).tobytes():
        return bytes(original)
    plane.paste(new_ink, box[:2])
    image = old.convert("RGBA")
    image.putalpha(plane)
    out = bytearray(original)
    t = font["tex"]
    surface.write(out, t["at"], t["codec"], t["width"], t["height"], image)
    return bytes(out)


def letters(data: bytes) -> set:
    font = _parse(data)
    return {chr(code) for first, last, _g in font["ranges"] for code in range(first, last + 1) if code < 0x110000}


def glyph_list(data: bytes) -> List[int]:
    return [g for _first, _last, g in _parse(data)["ranges"]]
