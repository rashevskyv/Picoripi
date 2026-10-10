"""Fonts of Rayman Raving Rabbids 1 and 2 (Jade engine, Montpellier): a ``.jfnt`` file of the workspace is the
font's FONTDESC item, its texture item and its palette item, each u32 size + bytes
(``core.texture_formats.jade`` reads the texture).

FONTDESC (little endian): ``FONTDESC``, u32 0xE0, then per glyph s32 character (a cp1252 byte) and f32 left,
bottom, right, top texture coordinates -- v counts from the texture's first stored row, the bottom of the
picture; left > right or bottom > top draws the rectangle mirrored (``)`` is ``(`` mirrored) -- ended by s32
-1; whatever follows stays as it is.

The model copies every glyph's rectangle, mirrored back, into a cell of a 16-column grid at its top-left; a
glyph's width is its rectangle's width. Packing writes back only the cells that changed (mirrored again, the
colours mapped to the texture's palette); codes, rectangles and widths stay, so an unedited model packs to the
original bytes. New glyphs cannot be added (the texture has no free room): a new letter is drawn over a glyph
the text does not use and mapped to it in the translation map.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, map_entries
from core.texture_formats import jade as jade_texture

COLUMNS = 16


def _parts(data: bytes) -> Tuple[bytes, bytes, bytes]:
    items = jade_texture.split(data)
    if not items or items[0][:8] != b"FONTDESC":
        raise ValueError("Not a Jade font (no FONTDESC item)")
    return items[0], items[1], (items[2] if len(items) > 2 else b"")


def glyphs(desc: bytes) -> List[Tuple[int, float, float, float, float]]:
    out, at = [], 12
    while at + 4 <= len(desc):
        code = struct.unpack_from("<i", desc, at)[0]
        if code == -1:
            break
        out.append((code, *struct.unpack_from("<4f", desc, at + 4)))
        at += 20
    return out


def _box(glyph, width: int, height: int) -> Tuple[Tuple[int, int, int, int], bool, bool]:
    """``(box in the picture, mirrored left-right, mirrored up-down)``."""
    _code, u1, v1, u2, v2 = glyph
    box = (round(min(u1, u2) * width), round((1 - max(v1, v2)) * height),
           round(max(u1, u2) * width), round((1 - min(v1, v2)) * height))
    return box, u2 < u1, v2 < v1


def _cut(picture: Image.Image, glyph) -> Image.Image:
    box, flip_x, flip_y = _box(glyph, *picture.size)
    cell = picture.crop(box)
    if flip_x:
        cell = cell.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_y:
        cell = cell.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return cell


def _layout(glyph_list, width: int, height: int) -> Tuple[int, int]:
    boxes = [_box(g, width, height)[0] for g in glyph_list]
    return (max([b[2] - b[0] for b in boxes] + [1]), max([b[3] - b[1] for b in boxes] + [1]))


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    desc, item, pal = _parts(data)
    picture = jade_texture.decode(item, pal)
    glyph_list = glyphs(desc)
    cell_w, cell_h = _layout(glyph_list, *picture.size)
    rows = max(1, -(-len(glyph_list) // COLUMNS))
    sheet = Image.new("RGBA", (COLUMNS * cell_w, rows * cell_h))
    packets = []
    for i, glyph in enumerate(glyph_list):
        cell = _cut(picture, glyph)
        sheet.paste(cell, ((i % COLUMNS) * cell_w, (i // COLUMNS) * cell_h))
        packets.append({"kerning": 0, "width": cell.width})
    space = next((p["width"] for g, p in zip(glyph_list, packets) if g[0] == 0x20), cell_w // 2)
    metadata = {
        "header": {"signature": "FONTDESC", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": cell_h, "descent": 0, "width": space, "leading": cell_h,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": rows * COLUMNS - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries([(g[0], i) for i, g in enumerate(glyph_list)])],
        "WID1": [{"first_code_included": 0, "last_code_included": len(glyph_list), "packets": packets}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    desc, item, pal = _parts(original)
    picture = jade_texture.decode(item, pal)
    glyph_list = glyphs(desc)
    cell_w, cell_h = _layout(glyph_list, *picture.size)
    edited = picture.copy()
    changed = False
    for i, glyph in enumerate(glyph_list):
        box, flip_x, flip_y = _box(glyph, *picture.size)
        x, y = (i % COLUMNS) * cell_w, (i // COLUMNS) * cell_h
        if not sheets or y + cell_h > sheets[0].height:
            continue
        cell = sheets[0].convert("RGBA").crop((x, y, x + box[2] - box[0], y + box[3] - box[1]))
        if cell.tobytes() == _cut(picture, glyph).tobytes():
            continue
        if flip_y:
            cell = cell.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if flip_x:
            cell = cell.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        edited.paste(cell, box[:2])
        changed = True
    if not changed:
        return bytes(original)
    return jade_texture.join([desc, jade_texture.encode(item, edited, pal)] + ([pal] if pal else []))
