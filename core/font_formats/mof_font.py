"""Castlevania: Lords of Shadow - Mirror of Fate (3DS) bitmap fonts: ``system/fonts/*.bfont``.

A ``.bfont`` is a CGFX file (``core.texture_formats.cgfx``: one A4 or LA4 atlas texture) with a glyph table after
the end of the CGFX (the file size at 0x0C), an ``MST`` block (the letters MST and a zero byte, u32 size, as the loose
``gui/symbols/*.mst`` files): u32 100, u32 atlas width, u32 atlas height, u32 glyph count, then
``count`` records ``u16 x, y, w, h`` -- the glyph's box in the atlas. Record ``i`` is character code ``0x1F + i``
(index 0 is the empty record of code 0x1F, 1 the space), a Windows-1252 byte in the English fonts; the Japanese
fonts carry more records after the 0xFF ones, which the model shows as plain cells without a character.

The model puts glyph ``i`` in cell ``i`` of one sheet (cells of the largest box, ``columns`` per row), the glyph's
box at the cell's top-left corner. The game advances the pen by the box width, so the width table is the box
width: a narrower value crops the glyph. A glyph that is drawn wider or taller than its box moves to free room of
the atlas (a free pixel after it); the font has no room for new codes (``ADDS_GLYPHS`` is off). Packing an unedited
model gives the original bytes back; only the touched boxes of the atlas are written.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries
from core.texture_formats import cgfx

FIRST_CODE = 0x1F
COLUMNS = 16
HEADER = 16


def _split(data: bytes) -> Tuple[bytes, int, List[List[int]]]:
    """``(CGFX part, table offset, [[x, y, w, h]])``."""
    if data[:4] != b"CGFX":
        raise ValueError("Not a Mirror of Fate .bfont (no CGFX)")
    end = struct.unpack_from("<I", data, 0x0C)[0]
    if not 0x100 < end <= len(data) - 8 - HEADER or data[end:end + 4] != b"MST\0":
        raise ValueError("The MST glyph table is missing")
    size = struct.unpack_from("<I", data, end + 4)[0]
    _hundred, _width, _height, count = struct.unpack_from("<4I", data, end + 8)
    if size != HEADER + count * 8 or end + 8 + size != len(data):
        raise ValueError("The glyph table does not end the file")
    boxes = [list(struct.unpack_from("<4H", data, end + 8 + HEADER + i * 8)) for i in range(count)]
    return data[:end], end, boxes


def _atlas(part: bytes) -> Image.Image:
    return cgfx.read(part, {})[0].image.convert("RGBA")


def _grid(boxes: List[List[int]]) -> Tuple[int, int, int, int]:
    cw = max([b[2] for b in boxes] + [1])
    ch = max([b[3] for b in boxes] + [1])
    rows = -(-len(boxes) // COLUMNS)
    return cw, ch, COLUMNS, rows


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    part, _end, boxes = _split(bytes(data))
    cw, ch, columns, rows = _grid(boxes)
    ink = coverage(_atlas(part))
    sheet = Image.new("L", (columns * cw, rows * ch))
    packets, pairs = [], []
    for glyph, (x, y, w, h) in enumerate(boxes):
        if w and h:
            sheet.paste(ink.crop((x, y, x + w, y + h)), ((glyph % columns) * cw, (glyph // columns) * ch))
        packets.append({"kerning": 0, "width": w})
        code = FIRST_CODE + glyph
        if glyph and code < 0x100:
            char = bytes([code]).decode("cp1252", "replace")
            if char != "�":
                pairs.append((char_code(char), glyph))
    count = columns * rows
    packets += [{"kerning": 0, "width": 0} for _ in range(count - len(packets))]
    space = boxes[1][2] if len(boxes) > 1 else cw // 2
    metadata = {
        "header": {"signature": "bfont", "num_chunks": 1},
        "INF1": [{"encoding": 1, "ascent": ch * 3 // 4, "descent": ch - ch * 3 // 4, "width": space, "leading": ch,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": cw, "cell_height": ch,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count - 1, "packets": packets}],
    }
    return metadata, [grey_sheet(sheet)]


def _free_box(taken: List[bytearray], width: int, height: int, w: int, h: int) -> Tuple[int, int]:
    """Top-left of a free ``w`` x ``h`` box with a free pixel after it, searched row by row."""
    for y in range(1, height - h):
        x = 1
        while x + w < width:
            blocker = max((taken[row].rfind(1, x, x + w + 1) for row in range(y, y + h + 1)), default=-1)
            if blocker < 0:
                return x, y
            x = blocker + 1
    raise ValueError(f"No free room for a {w}x{h} glyph in the font atlas")


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    original = bytes(original)
    part, end, boxes = _split(original)
    cw, ch, columns, _rows = _grid(boxes)
    gly = metadata["GLY1"][0]
    if (gly["cell_width"], gly["cell_height"], gly["glyph_horizontal_count"]) != (cw, ch, columns):
        raise ValueError("The font's cell grid changed; it cannot be written back")
    _old_meta, old_sheets = extract(original, params)
    new_ink, old_ink = coverage(sheets[0]), coverage(old_sheets[0])
    packets = metadata["WID1"][0]["packets"]
    image = _atlas(part)
    plane = coverage(image)
    taken = [bytearray(plane.width) for _ in range(plane.height)]
    for x, y, w, h in boxes:
        for row in range(y, min(y + h + 1, plane.height)):
            taken[row][x:x + w + 1] = b"\x01" * (w + 1)
    dirty: List[Tuple[int, int, int, int]] = []
    new_boxes = [list(b) for b in boxes]

    def cell(glyph: int) -> Tuple[int, int, int, int]:
        x, y = (glyph % columns) * cw, (glyph // columns) * ch
        return x, y, x + cw, y + ch

    changed = False
    for glyph, box in enumerate(new_boxes):
        x, y, w, h = box
        width = int(packets[glyph]["width"]) if glyph < len(packets) else w
        if not 0 <= width <= cw:
            raise ValueError(f"Width of glyph {glyph} must be 0..{cw}")
        pixels_changed = new_ink.crop(cell(glyph)).tobytes() != old_ink.crop(cell(glyph)).tobytes()
        if not pixels_changed and width == w:
            continue
        changed = True
        picture = new_ink.crop(cell(glyph))
        ink_box = picture.getbbox()
        need_w = max(width, ink_box[2] if ink_box else 0) if pixels_changed else width
        need_h = max(h, ink_box[3] if ink_box else 0) if pixels_changed else h
        if w and h:
            plane.paste(0, (x, y, x + w, y + h))
            dirty.append((x, y, x + w, y + h))
            for row in range(y, min(y + h + 1, plane.height)):
                taken[row][x:x + w + 1] = bytes(w + 1)
        if need_w > w or need_h > h or not (w and h):
            box[2], box[3] = max(need_w, 1), max(need_h, 1)
            box[0], box[1] = _free_box(taken, plane.width, plane.height, box[2], box[3])
        else:
            box[2] = need_w
        x, y, w, h = box
        for row in range(y, min(y + h + 1, plane.height)):
            taken[row][x:x + w + 1] = b"\x01" * (w + 1)
        plane.paste(picture.crop((0, 0, w, h)), (x, y))
        dirty.append((x, y, x + w, y + h))
    if not changed:
        return original
    for left, top, right, bottom in dirty:
        r, g, b, _a = image.crop((left, top, right, bottom)).split()
        ink = plane.crop((left, top, right, bottom))
        image.paste(Image.merge("RGBA", (r, g, b, ink)), (left, top))
    out = bytearray(cgfx.write(part, {0: image}, {}))
    out += original[end:end + 8 + HEADER]
    for box in new_boxes:
        out += struct.pack("<4H", *box)
    return bytes(out)
