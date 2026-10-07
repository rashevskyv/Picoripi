"""Retro Studios FONT (Metroid Prime 4: Beyond, Prime Remastered) with its texture pages, as ``1_unpack`` bundles them.

A ``.rfont`` file is the ``RFRM FONT`` form followed by its TXTR pages (``core.texture_formats.txtr``,
decompressed), in the order of the five page GUIDs at 0x24 of the font. The font holds the size (f32 at
0x78), the glyph count (u32 at 0x328) and from 0x330 one 46-byte record per glyph: u16 character,
u32 flags (low byte: the page, i.e. the language set -- 0 Latin, 1 Japanese, 2 and 3 Chinese, 4 Korean),
f32 left, top, width, height, the page's texture coordinates u0, v0 (bottom), u1, v1 (top), f32 advance
and f32 0. Pages are R8 signed-distance-field atlases, rows bottom up.

Prime Remastered has the same fields 4 bytes later (size at 0x7c, glyph count at
0x32c, records from 0x334) and 48-byte records: u16 character, u16 page, u32 flags, the same nine f32,
then u32 n and n kerning pairs of 6 bytes (u16 next character, f32 adjustment).

The model shows one page (``params.page``, default 0): each glyph's rectangle of the atlas is copied into
a cell of a grid (``params.columns`` wide, 256 cells per sheet), grey = the stored distance value. Packing
copies every cell back into its rectangle and writes the advance of a glyph whose width changed; an
unedited model packs to the original bytes. New glyphs cannot be added (no room in the atlas).
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries
from core.texture_formats import txtr

RECORDS = 0x330
RECORD = struct.Struct("<HI10f")
PER_SHEET = 256


def split(bundle: bytes) -> Tuple[bytes, List[bytes]]:
    """``(FONT form, [TXTR forms])`` of an ``.rfont`` file."""
    forms, position = [], 0
    while position < len(bundle):
        if bundle[position:position + 4] != b"RFRM":
            raise ValueError(f"Not an RFRM form at {position:#x}")
        size = struct.unpack_from("<Q", bundle, position + 4)[0] + 0x20
        forms.append(bytes(bundle[position:position + size]))
        position += size
    if not forms or forms[0][20:24] != b"FONT":
        raise ValueError("Not a Retro FONT bundle")
    return forms[0], forms[1:]


def _remastered(form: bytes) -> bool:
    """The Prime Remastered layout: no glyph count at 0x328, one at 0x32c (form versions overlap: 18, 23, 24)."""
    first, second = struct.unpack_from("<II", form, RECORDS - 8)
    return first == 0 and second > 0


def _records(form: bytes) -> List[Tuple[int, List]]:
    """``[(offset of the advance, [character, flags or page, left, top, width, height, u0, v0, u1, v1,
    advance])]`` of every glyph."""
    if not _remastered(form):
        count = struct.unpack_from("<I", form, RECORDS - 8)[0]
        return [(RECORDS + RECORD.size * i + 38, list(RECORD.unpack_from(form, RECORDS + RECORD.size * i)))
                for i in range(count)]
    out, position = [], RECORDS + 4
    for _ in range(struct.unpack_from("<I", form, RECORDS - 4)[0]):
        char, page, _flags, *floats, kerning = struct.unpack_from("<HHI9fI", form, position)
        out.append((position + 40, [char, page, *floats]))
        position += 48 + 6 * kerning
    return out


def _glyphs(form: bytes, page: int):
    """``[(offset of the advance, record)]`` of the glyphs on one page."""
    return [(at, r) for at, r in _records(form) if r[1] & 0xFF == page]


def _rect(record, width: int, height: int) -> Tuple[int, int, int, int]:
    """The glyph's box in the upright atlas image."""
    u0, v0, u1, v1 = record[6:10]
    return round(u0 * width), round((1 - v0) * height), round(u1 * width), round((1 - v1) * height)


def _atlas(pages: List[bytes], page: int) -> Image.Image:
    if page >= len(pages):
        raise ValueError(f"The font has {len(pages)} pages, not {page + 1}")
    return txtr.read(pages[page], {})[0].image


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    form, pages = split(data)
    page = int(params.get("page", 0))
    columns = int(params.get("columns", 16))
    atlas = _atlas(pages, page)
    ink = atlas.getchannel("R")
    glyphs = _glyphs(form, page)
    rects = [_rect(record, *atlas.size) for _i, record in glyphs]
    cell_w = max([r[2] - r[0] for r in rects] + [1])
    cell_h = max([r[3] - r[1] for r in rects] + [1])
    rows = PER_SHEET // columns
    sheets = []
    for start in range(0, max(1, len(glyphs)), PER_SHEET):
        sheet = Image.new("L", (columns * cell_w, rows * cell_h))
        for cell, rect in enumerate(rects[start:start + PER_SHEET]):
            if rect[2] > rect[0] and rect[3] > rect[1]:
                sheet.paste(ink.crop(rect), ((cell % columns) * cell_w, (cell // columns) * cell_h))
        sheets.append(grey_sheet(sheet))
    size = struct.unpack_from("<f", form, 0x7C if _remastered(form) else 0x78)[0]
    entries = [(char_code(chr(record[0])), index) for index, (_i, record) in enumerate(glyphs)]
    packets = [{"kerning": -round(record[2]), "width": round(record[10])} for _i, record in glyphs]
    space = next((round(record[10]) for _i, record in glyphs if record[0] == 0x20), cell_w // 2)
    metadata = {
        "header": {"signature": "RFNT", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": round(size), "descent": max(1, cell_h - round(size)), "width": space,
                  "leading": cell_h, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": len(sheets) * PER_SHEET - 1, "cell_width": cell_w,
                  "cell_height": cell_h, "glyph_horizontal_count": columns, "glyph_vertical_count": rows,
                  "texture_width": columns * cell_w, "texture_height": rows * cell_h}],
        "MAP1": [map_entries(entries)],
        "WID1": [{"first_code_included": 0, "last_code_included": len(sheets) * PER_SHEET, "packets": packets}],
    }
    return metadata, sheets


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    form, pages = split(original)
    page = int(params.get("page", 0))
    columns = int(params.get("columns", 16))
    atlas = _atlas(pages, page)
    ink = atlas.getchannel("R")
    glyphs = _glyphs(form, page)
    cell_w = int(metadata["GLY1"][0]["cell_width"])
    cell_h = int(metadata["GLY1"][0]["cell_height"])
    inks = [coverage(sheet) for sheet in sheets]
    for cell, (_index, record) in enumerate(glyphs):
        left, top, right, bottom = _rect(record, *atlas.size)
        if right <= left or bottom <= top:
            continue
        sheet, slot = divmod(cell, PER_SHEET)
        x, y = (slot % columns) * cell_w, (slot // columns) * cell_h
        ink.paste(inks[sheet].crop((x, y, x + right - left, y + bottom - top)), (left, top))
    new_atlas = Image.merge("RGBA", (ink, ink, ink, Image.new("L", ink.size, 255)))
    pages = list(pages)
    pages[page] = txtr.write(pages[page], {0: new_atlas}, {})
    new_form = bytearray(form)
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    for cell, (at, record) in enumerate(glyphs):
        if cell < len(packets) and int(packets[cell]["width"]) != round(record[10]):
            struct.pack_into("<f", new_form, at, float(packets[cell]["width"]))
    return bytes(new_form) + b"".join(pages)
