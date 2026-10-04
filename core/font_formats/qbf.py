"""Grezzo QBF1 bitmap font (Ocarina of Time 3D ``message/eu/ltn16.qbf``, ``message/sys8.qbf``).

Layout (little endian): ``QBF1``, u16 character count, u16 cell count, u32 (42), u8 bits per pixel,
u8 cell width, u8 cell height, u8 (2 / 4); then per character, sorted by code: u16 UTF-16 code,
u16 cell, u8 left (cell columns skipped: the glyph is drawn at ``pen - left``), u8 advance, u16 flags;
then the cells, row by row. 4 bpp is grey ink (high nibble = left pixel); 8 bpp is LA4 (luminance in
the high nibble, alpha in the low one), which keeps the outline of ``sys8``. Characters may share a cell.

The model shows the cells 16 to a row with ``SPARE_CELLS`` empty ones after them: drawing a glyph in an
empty cell and giving it a character adds both (the table stays sorted, the cell count grows, as the
Russian release did). A character that shares a cell keeps its own metrics unless they were the cell's.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageChops

from core.font_formats import Metadata, Sheets, char_map, char_code, coverage, grey_sheet, map_entries

ADDS_GLYPHS = True  # a typed character gets its own table record (an empty or spare cell)

COLUMNS = 16
SPARE_CELLS = 128   # ponytail: a fixed reserve for new letters; raise it if a font needs more


def _parse(data: bytes) -> Dict[str, Any]:
    if data[:4] != b"QBF1":
        raise ValueError("Not a QBF1 font")
    chars, cells = struct.unpack_from("<HH", data, 4)
    bpp, width, height = data[12], data[13], data[14]
    if bpp not in (4, 8):
        raise ValueError(f"QBF with {bpp} bits per pixel is not supported (4 and 8 are)")
    entries = [struct.unpack_from("<HHBBH", data, 16 + 8 * index) for index in range(chars)]
    start = 16 + 8 * chars
    size = width * height * bpp // 8
    if start + cells * size > len(data):
        raise ValueError("QBF cells are cut short")
    return {"bpp": bpp, "width": width, "height": height, "entries": entries, "cells": cells,
            "start": start, "cell_size": size}


def _cell_image(raw: bytes, bpp: int, width: int, height: int) -> Image.Image:
    size = (width, height)
    if bpp == 4:
        ink = bytearray(width * height)
        ink[0::2] = raw.translate(bytes((b >> 4) * 17 for b in range(256)))
        ink[1::2] = raw.translate(bytes((b & 15) * 17 for b in range(256)))
        return grey_sheet(Image.frombytes("L", size, bytes(ink)))
    lum = Image.frombytes("L", size, raw.translate(bytes((b >> 4) * 17 for b in range(256))))
    alpha = Image.frombytes("L", size, raw.translate(bytes((b & 15) * 17 for b in range(256))))
    return Image.merge("RGBA", (lum, lum, lum, alpha))


def _four_bit(value: int) -> int:
    return min(15, (value + 8) // 17)


def _cell_bytes(image: Image.Image, bpp: int) -> bytes:
    if bpp == 4:
        ink = coverage(image).tobytes().translate(bytes(_four_bit(v) for v in range(256)))
        return bytes(high << 4 | low for high, low in zip(ink[0::2], ink[1::2]))
    red, green, blue, alpha = image.convert("RGBA").split()
    lum = ImageChops.lighter(ImageChops.lighter(red, green), blue).tobytes()
    return bytes(_four_bit(l_value) << 4 | _four_bit(a_value) for l_value, a_value in zip(lum, alpha.tobytes()))


def primary_metrics(entries: List[Tuple[int, int, int, int]]) -> Dict[int, Tuple[int, int]]:
    """``{glyph: (kerning, width)}`` of the first character of each glyph (``(code, glyph, kerning, width)``)."""
    result: Dict[int, Tuple[int, int]] = {}
    for _code, glyph, kerning, width in entries:
        result.setdefault(glyph, (kerning, width))
    return result


def edited_entries(metadata: Metadata, old: Dict[int, Tuple[int, int, int]]) -> List[Tuple[int, int, int, int]]:
    """``(code, glyph, kerning, width)`` per character of the model, sorted by code.

    ``old`` is ``{code: (glyph, kerning, width)}`` of the file. A character still on its glyph keeps
    its metrics unless they were the glyph's (the model's packet) and that packet was edited.
    """
    packets = metadata["WID1"][0]["packets"]
    primary = primary_metrics([(code, glyph, kerning, width) for code, (glyph, kerning, width) in old.items()])
    result = []
    for char, glyph in char_map(metadata).items():
        code = ord(char)
        packet = packets[glyph] if glyph < len(packets) else {"kerning": 0, "width": 0}
        edited = (int(packet["kerning"]), int(packet["width"]))
        if code in old and old[code][0] == glyph:
            kerning, width = old[code][1:]
            if (kerning, width) == primary.get(glyph) and edited != primary.get(glyph):
                kerning, width = edited
        else:
            kerning, width = edited
        result.append((code, glyph, kerning, width))
    return sorted(result)


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = _parse(data)
    width, height, bpp = font["width"], font["height"], font["bpp"]
    capacity = -(-(font["cells"] + SPARE_CELLS) // COLUMNS) * COLUMNS
    rows = capacity // COLUMNS
    sheet = Image.new("RGBA", (COLUMNS * width, rows * height))
    for cell in range(font["cells"]):
        raw = data[font["start"] + cell * font["cell_size"]:][:font["cell_size"]]
        sheet.paste(_cell_image(raw, bpp, width, height), ((cell % COLUMNS) * width, (cell // COLUMNS) * height))

    entries = [(code, cell, left, advance) for code, cell, left, advance, _flags in font["entries"]]
    packets = [{"kerning": 0, "width": 0} for _ in range(capacity)]
    for glyph, (kerning, advance) in primary_metrics(entries).items():
        if glyph < capacity:
            packets[glyph] = {"kerning": kerning, "width": advance}
    space = next((advance for code, _cell, _left, advance in entries if code == 0x20), width // 2)
    metadata = {
        "header": {"signature": "QBF1", "num_chunks": 4, "bits_per_pixel": bpp},
        "INF1": [{"encoding": 1, "ascent": height * 3 // 4, "descent": height - height * 3 // 4, "width": space,
                  "leading": height, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": capacity - 1, "cell_width": width, "cell_height": height,
                  "page_data_size": font["cell_size"] * font["cells"], "texture_format": bpp,
                  "glyph_horizontal_count": COLUMNS, "glyph_vertical_count": rows,
                  "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries([(char_code(chr(code)), cell) for code, cell, _left, _advance in entries])],
        "WID1": [{"first_code_included": 0, "last_code_included": capacity, "packets": packets}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = _parse(original)
    width, height, bpp = font["width"], font["height"], font["bpp"]
    flags = {code: flag for code, _cell, _left, _advance, flag in font["entries"]}
    old = {code: (cell, left, advance) for code, cell, left, advance, _flags in font["entries"]}
    entries = edited_entries(metadata, old)
    capacity = metadata["GLY1"][0]["end_glyph"] + 1
    if entries and max(glyph for _code, glyph, _k, _w in entries) >= capacity:
        raise ValueError("A character points past the font's cells")
    if entries and max(code for code, _glyph, _k, _w in entries) > 0xFFFF:
        raise ValueError("QBF maps 16-bit character codes only")
    cells = max([font["cells"]] + [glyph + 1 for _code, glyph, _k, _w in entries])

    out = bytearray(original[:16])
    struct.pack_into("<HH", out, 4, len(entries), cells)
    for code, glyph, kerning, advance in entries:
        out += struct.pack("<HHBBH", code, glyph, max(0, min(255, kerning)), max(0, min(255, advance)),
                           flags.get(code, 0) if code in old and old[code][0] == glyph else 0)
    sheet = sheets[0].convert("RGBA")
    for cell in range(cells):
        x, y = (cell % COLUMNS) * width, (cell // COLUMNS) * height
        out += _cell_bytes(sheet.crop((x, y, x + width, y + height)), bpp)
    out += original[font["start"] + font["cells"] * font["cell_size"]:]   # anything after the cells
    return bytes(out)
