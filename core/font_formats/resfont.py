"""Nintendo ResFONT (``FONTbfn1``) fonts as the GameCube game embeds them, e.g. Luigi's Mansion's dialogue font in main.dol.

The file: a 0x20-byte header (``FONTbfn1``, size, block count) and blocks in order. Blocks used:

- ``INF1``: ascent (+0xA), default advance (+0xE), leading (+0x10);
- ``GLY1``: first and last glyph (+0x8, +0xA), cell width and height (+0xC, +0xE), bytes per sheet (+0x10), texture
  format (+0x14, 0 = I4), cells per row (+0x16), cells per column (+0x18), texture width (+0x1A); the sheets follow at
  +0x20, one after another;
- ``MAP1``: character code -> glyph, in methods 0 (linear), 2 (table) and 3 (pairs);
- ``WID1``: per glyph a kerning byte and an advance byte (+0xC, +0xD onward).

A sheet is I4: 8x8 tiles of 32 bytes, tiles in rows of ``texture width / 8``. A glyph ``g`` is cell ``g % per_sheet``
of sheet ``g // per_sheet``, cells row by row (cell x = ``cell % cells_per_row``). The model shows each sheet as grey
ink with alpha equal to the ink (``core.font_formats.grey_sheet``), so the editor and the image editor see the glyphs.

Model codes: a MAP1 code is written as the Unicode character it decodes to in Shift-JIS (``cp932``), so the editor shows
``Ё`` for code 0x8446. Packing writes only the sheet nibbles back over the original bytes: an unedited model packs to the
original file, an edit changes only the texels it touches, and a sheet that would grow is refused. MAP1 and WID1 stay as
they are; they are read for the editor but not written.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, coverage, grey_sheet, map_entries

MAGIC = b"FONTbfn1"
HEADER = 0x20


def _blocks(data: bytes) -> List[Tuple[bytes, int, int]]:
    """``(tag, offset, size)`` of each block of the file."""
    if bytes(data[:8]) != MAGIC:
        raise ValueError("Not a FONTbfn1 font")
    count = struct.unpack_from(">I", data, 12)[0]
    found, at = [], HEADER
    for _ in range(count):
        if at + 8 > len(data):
            break
        size = struct.unpack_from(">I", data, at + 4)[0]
        if size == 0:
            break
        found.append((bytes(data[at:at + 4]), at, size))
        at += size
    return found


def _code_of(code: int) -> int:
    """The character a code stands for: a Shift-JIS pair becomes its Unicode code point, a one-byte code stays."""
    if code < 0x100:
        return code
    try:
        return ord(code.to_bytes(2, "big").decode("cp932"))
    except UnicodeDecodeError:
        return code


def _map_pairs(data: bytes, offset: int, size: int) -> List[Tuple[int, int]]:
    method, start, end, count = struct.unpack_from(">HHHH", data, offset + 8)
    pairs: List[Tuple[int, int]] = []
    if method == 0:
        first = struct.unpack_from(">H", data, offset + 0x10)[0]
        pairs = [(c, first + c - start) for c in range(start, end + 1)]
    elif method == 2:
        pairs = [(c, struct.unpack_from(">H", data, offset + 0x10 + 2 * (c - start))[0])
                 for c in range(start, end + 1) if 0x10 + 2 * (c - start) + 2 <= size]
    elif method == 3:
        pairs = [struct.unpack_from(">HH", data, offset + 0x10 + 4 * i) for i in range(count)
                 if 0x10 + 4 * i + 4 <= size]
    return [(_code_of(c), g) for c, g in pairs]


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    blocks = _blocks(data)
    inf = next(((o, s) for t, o, s in blocks if t == b"INF1"), None)
    gly_at = next(((o, s) for t, o, s in blocks if t == b"GLY1"), None)
    if gly_at is None:
        raise ValueError("FONTbfn1 without a GLY1 block")
    g_off, g_size = gly_at
    first, last, cw, ch, sheet_bytes, fmt, per_row, per_col, tex_w = struct.unpack_from(">HHHHIHHHH", data, g_off + 8)
    if fmt != 0:
        raise ValueError(f"FONTbfn1 texture format {fmt} is not I4")
    per_sheet = per_row * per_col
    sheet_count = (g_size - HEADER) // sheet_bytes
    tex_h = sheet_bytes * 2 // tex_w
    gly = {"sheet_bytes": sheet_bytes, "offset": g_off, "tex_w": tex_w, "tex_h": tex_h, "sheets": sheet_count}
    sheets = [_decode(data, g_off + HEADER + i * sheet_bytes, tex_w, tex_h) for i in range(sheet_count)]

    metadata: Metadata = {"header": {"signature": "FONTbfn1", "format": "resfont"}}
    ascent, width, leading = 0, 0, 0
    if inf is not None:
        i_off = inf[0]
        ascent, width, leading = (struct.unpack_from(">H", data, i_off + 0xA)[0],
                                  struct.unpack_from(">H", data, i_off + 0xE)[0],
                                  struct.unpack_from(">H", data, i_off + 0x10)[0])
    metadata["INF1"] = [{"ascent": ascent, "descent": ch - ascent, "width": width, "leading": leading,
                         "fallback_code": 0x3F, "encoding": 1}]
    metadata["GLY1"] = [{"start_glyph": first, "end_glyph": last, "cell_width": cw, "cell_height": ch,
                         "glyph_horizontal_count": per_row, "glyph_vertical_count": per_col,
                         "texture_width": tex_w, "texture_height": tex_h, "texture_format": fmt,
                         "sheet_bytes": sheet_bytes, "sheets": sheet_count}]
    maps = [b for b in blocks if b[0] == b"MAP1"]
    pairs = []
    for _tag, o, s in maps:
        pairs.extend(_map_pairs(data, o, s))
    metadata["MAP1"] = [map_entries(pairs)] if pairs else []
    wid = next(((o, s) for t, o, s in blocks if t == b"WID1"), None)
    packets: List[Dict[str, int]] = []
    if wid is not None:
        w_off, _w_size = wid
        wf, wl = struct.unpack_from(">HH", data, w_off + 8)
        for g in range(wf, wl + 1):
            at = w_off + 0xC + 2 * (g - wf)
            packets.append({"kerning": data[at], "width": data[at + 1]})
        metadata["WID1"] = [{"first_code_included": wf, "last_code_included": wl, "packets": packets}]
    else:
        metadata["WID1"] = []
    gly["per_sheet"] = per_sheet
    metadata["_resfont"] = gly
    return metadata, sheets


def _decode(data: bytes, base: int, width: int, height: int) -> Image.Image:
    ink = Image.new("L", (width, height))
    pix = ink.load()
    tiles_per_row = width // 8
    for y in range(height):
        for x in range(width):
            byte = base + ((y // 8) * tiles_per_row + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
            value = data[byte] & 15 if x % 2 else data[byte] >> 4
            pix[x, y] = value * 17
    return grey_sheet(ink)


def _encode_into(out: bytearray, base: int, sheet: Image.Image, width: int, height: int) -> None:
    ink = coverage(sheet.convert("RGBA")).convert("L")
    if ink.size != (width, height):
        raise ValueError(f"FONTbfn1 sheet is {ink.size[0]}x{ink.size[1]}; the font takes {width}x{height}")
    pix = ink.load()
    tiles_per_row = width // 8
    for y in range(height):
        for x in range(width):
            value = min(15, (pix[x, y] + 8) // 17)
            byte = base + ((y // 8) * tiles_per_row + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
            if x % 2:
                out[byte] = (out[byte] & 0xF0) | value
            else:
                out[byte] = (out[byte] & 0x0F) | (value << 4)


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    gly = metadata["_resfont"]
    if len(sheets) != gly["sheets"]:
        raise ValueError(f"FONTbfn1 holds {gly['sheets']} sheets, {len(sheets)} were given")
    out = bytearray(original)
    for index, sheet in enumerate(sheets):
        _encode_into(out, gly["offset"] + HEADER + index * gly["sheet_bytes"], sheet, gly["tex_w"], gly["tex_h"])
    return bytes(out)
