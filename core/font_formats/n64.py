"""Zelda 64 (OoT, MM) message font: 16x16 I4 glyphs in one ROM file, a float advance table in ``code``.

Glyph ``i`` is character ``first_code + i``; its texture is 128 bytes at ``i * 128`` of the font
file (rows of 8 bytes, high nibble first). Its advance is ``f32`` number ``i`` of the width table.
Saving replaces the two files in the ROM (``plugins.common.n64_rom``): the font file in place, the
re-compressed ``code`` where it fits; the header CRC is recomputed.

Parameters (from the plugin's font source): ``rom_id`` and ``rom_version`` (bytes 0x3B-0x3F),
``font_file`` and ``glyph_count``, ``widths_file`` (dmadata index of ``code``), ``widths_offset``
and ``widths_count``, ``first_code`` (0x20), ``extra_chars`` (``{"0x80": "ÀîÂ..."}``: the font's
characters beyond ASCII, consecutive from that code), optional ``columns`` and ``ascent``.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries
from plugins.common.n64_rom import N64Rom

GLYPH = 16
GLYPH_BYTES = GLYPH * GLYPH // 2


def _int(value: Any) -> int:
    """A number from JSON: an int, or a string such as "0x101EA0"."""
    return int(value, 0) if isinstance(value, str) else int(value)


def _rom(data: bytes, params: Dict[str, Any]) -> N64Rom:
    rom = N64Rom(data)
    game, version = bytes(rom.data[0x3B:0x3F]).decode("ascii", "replace"), rom.data[0x3F]
    if params.get("rom_id") and (game != params["rom_id"] or version != _int(params.get("rom_version", 0))):
        raise ValueError(f"This font is described for ROM {params['rom_id']} v{params.get('rom_version', 0)}, "
                         f"not {game} v{version}")
    return rom


def _characters(params: Dict[str, Any]) -> Dict[int, str]:
    chars = {code: chr(code) for code in range(0x20, 0x7F)}
    for start, run in (params.get("extra_chars") or {}).items():
        for offset, char in enumerate(run):
            chars[int(str(start), 0) + offset] = char
    return chars


def _widths(code: bytes, params: Dict[str, Any]) -> List[float]:
    count = _int(params["widths_count"])
    return list(struct.unpack_from(f">{count}f", code, _int(params["widths_offset"])))


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    rom = _rom(data, params)
    count, first = _int(params["glyph_count"]), _int(params.get("first_code", 0x20))
    columns = _int(params.get("columns", 16))
    rows = -(-count // columns)
    font = rom.read_file(_int(params["font_file"]))
    if len(font) < count * GLYPH_BYTES:
        raise ValueError(f"Font file holds {len(font) // GLYPH_BYTES} glyphs, expected {count}")
    widths = _widths(rom.read_file(_int(params["widths_file"])), params)

    ink = bytearray(columns * GLYPH * rows * GLYPH)
    stride = columns * GLYPH
    for glyph in range(count):
        x0, y0 = (glyph % columns) * GLYPH, (glyph // columns) * GLYPH
        base = glyph * GLYPH_BYTES
        for y in range(GLYPH):
            row = (y0 + y) * stride + x0
            for x in range(0, GLYPH, 2):
                byte = font[base + y * 8 + x // 2]
                ink[row + x] = (byte >> 4) * 17
                ink[row + x + 1] = (byte & 0xF) * 17
    sheet = grey_sheet(Image.frombytes("L", (stride, rows * GLYPH), bytes(ink)))

    chars = _characters(params)
    pairs = [(char_code(chars[first + glyph]), glyph) for glyph in range(count) if first + glyph in chars]
    packets = [{"kerning": 0, "width": int(round(widths[glyph])) if glyph < len(widths) else 0}
               for glyph in range(count)]
    space = widths[0] if widths else GLYPH // 2
    metadata = {
        "header": {"signature": "Zelda64 font", "num_chunks": 4},
        "INF1": [{"encoding": 0, "ascent": _int(params.get("ascent", 12)), "descent": GLYPH - _int(params.get("ascent", 12)),
                  "width": int(round(space)), "leading": GLYPH, "fallback_code": first, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": GLYPH, "cell_height": GLYPH,
                  "page_data_size": count * GLYPH_BYTES, "texture_format": 0,
                  "glyph_horizontal_count": columns, "glyph_vertical_count": rows,
                  "texture_width": stride, "texture_height": rows * GLYPH}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count, "packets": packets}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    rom = _rom(original, params)
    count = _int(params["glyph_count"])
    columns = _int(params.get("columns", 16))
    font_index, code_index = _int(params["font_file"]), _int(params["widths_file"])

    old_font = rom.read_file(font_index)
    ink = coverage(sheets[0]).tobytes()
    stride = sheets[0].width
    font = bytearray(old_font)
    for glyph in range(count):
        x0, y0 = (glyph % columns) * GLYPH, (glyph // columns) * GLYPH
        base = glyph * GLYPH_BYTES
        for y in range(GLYPH):
            row = (y0 + y) * stride + x0
            for x in range(0, GLYPH, 2):
                high = min(15, (ink[row + x] + 8) // 17)
                low = min(15, (ink[row + x + 1] + 8) // 17)
                font[base + y * 8 + x // 2] = high << 4 | low

    code = rom.read_file(code_index)
    new_code = bytearray(code)
    old_widths = _widths(code, params)
    packets = metadata["WID1"][0]["packets"]
    offset = _int(params["widths_offset"])
    for glyph in range(min(count, len(old_widths), len(packets))):
        width = int(packets[glyph]["width"])
        if int(round(old_widths[glyph])) != width:   # keep the exact float unless the width was edited
            struct.pack_into(">f", new_code, offset + glyph * 4, float(width))

    changes = {}
    if bytes(font) != old_font:
        changes[font_index] = bytes(font)
    if bytes(new_code) != code:
        changes[code_index] = bytes(new_code)
    return rom.replace_files(changes) if changes else bytes(original)
