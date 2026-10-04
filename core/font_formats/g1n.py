"""Koei Tecmo G1N bitmap fonts (``_N1G0000``): several sizes of one face, 4-bit glyph bitmaps, a full UTF-16 map.

Layout (little endian)::

    0x00 "_N1G0000"  0x08 u32 file size  0x0C u32 header size  0x10 u32 ?  0x14 u32 bitmap data offset
    0x18 u32 font count  0x1C u32 palette count  0x20 u32 font offset[font count]
    palettes: 16 x u32 per font (white, alpha 0x00..0xFF)
    per font: u16 glyph index[65536] (character -> glyph; 0 is glyph 0 and "none"), then 12 bytes per glyph:
              u8 width, u8 height, s8 x offset, u8 top, u8 advance, s8 y offset, u8 0, u8 cell height,
              u32 bitmap offset (from the bitmap data)
    bitmaps: 4 bits per pixel, low nibble first, rows of ceil(width / 2) bytes; every glyph owns a
             slot of cell x cell / 2 bytes, so a glyph can be redrawn up to the cell width in place.

``params``: ``font`` (which size, default 0), ``columns`` of the editor grid (default 32), ``spare``
empty cells after the glyphs for new characters (default 128). Editing: a changed glyph is encoded
again in its slot (width = its advance); a character mapped to a cell past the last glyph adds glyphs
(their records at the end of the font, bitmaps at the end of the file, offsets updated). An unedited
model packs to the original bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, code_char, coverage, grey_sheet, map_entries

ADDS_GLYPHS = True  # a character mapped to a cell past the font's glyphs gets a new glyph
_RECORD = struct.Struct("<8BI")


class _Font:
    """One size of the file: its map, glyph records and where they are."""

    def __init__(self, data: bytes, index: int):
        if data[:8] != b"_N1G0000":
            raise ValueError("Not a G1N font")
        self.base, self.count = struct.unpack_from("<II", data, 0x14)
        if not 0 <= index < self.count:
            raise ValueError(f"The G1N file has {self.count} fonts, not {index + 1}")
        self.offsets = list(struct.unpack_from(f"<{self.count}I", data, 0x20))
        self.index = index
        self.start = self.offsets[index]
        end = self.offsets[index + 1] if index + 1 < self.count else self.base
        self.glyphs = (end - self.start - 0x20000) // 12
        self.map = list(struct.unpack_from("<65536H", data, self.start))
        self.records = [list(_RECORD.unpack_from(data, self.start + 0x20000 + 12 * i)) for i in range(self.glyphs)]
        self.cell = max(max(r[7], r[0]) for r in self.records) if self.records else 1
        self.slot = self.cell * self.cell // 2


_LOW = bytes((b & 15) * 17 for b in range(256))
_HIGH = bytes((b >> 4) * 17 for b in range(256))
_LEVEL = bytes((v + 8) // 17 for v in range(256))


def _decode(data: bytes, base: int, record) -> Image.Image:
    width, height, offset = record[0], record[1], record[8]
    stride = (width + 1) // 2
    raw = data[base + offset:base + offset + stride * height]
    pixels = bytearray(2 * len(raw))
    pixels[0::2], pixels[1::2] = raw.translate(_LOW), raw.translate(_HIGH)
    if width % 2:  # each row has one padding pixel
        pixels = b"".join(pixels[y * 2 * stride:y * 2 * stride + width] for y in range(height))
    return Image.frombytes("L", (width, height), bytes(pixels))


def _encode(ink: Image.Image) -> bytes:
    width, height = ink.size
    if width % 2:
        padded = Image.new("L", (width + 1, height), 0)
        padded.paste(ink, (0, 0))
        ink = padded
    levels = ink.tobytes().translate(_LEVEL)
    return bytes(low | high << 4 for low, high in zip(levels[0::2], levels[1::2]))


def _grid(font: _Font, params: Dict[str, Any]) -> Tuple[int, int]:
    columns = int(params.get("columns", 32))
    cells = font.glyphs + int(params.get("spare", 128))
    return columns, (cells + columns - 1) // columns


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = _Font(data, int(params.get("font", 0)))
    columns, rows = _grid(font, params)
    cell = font.cell
    ink = Image.new("L", (columns * cell, rows * cell), 0)
    packets = []
    for index, record in enumerate(font.records):
        if record[0] and record[1]:
            ink.paste(_decode(data, font.base, record), ((index % columns) * cell, (index // columns) * cell))
        packets.append({"kerning": -_signed(record[2]), "width": record[4]})
    packets += [{"kerning": 0, "width": 0}] * (columns * rows - len(packets))
    pairs = [(char_code(chr(code)), glyph) for code, glyph in enumerate(font.map) if glyph]
    if font.map[0x20] == 0 and font.glyphs:
        pairs.append((0x20, 0))
    first = font.records[0] if font.records else [0] * 9
    metadata = {
        "header": {"signature": "G1N font", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": first[1] // 2, "descent": first[1] - first[1] // 2,
                  "width": first[4], "leading": first[1], "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": columns * rows - 1, "cell_width": cell, "cell_height": cell,
                  "page_data_size": font.slot, "texture_format": 4, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": columns * cell, "texture_height": rows * cell}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": columns * rows, "packets": packets}],
    }
    return metadata, [grey_sheet(ink)]


def _pairs(metadata: Metadata) -> set:
    """``{(model code, glyph)}`` of MAP1."""
    pairs = set()
    for block in metadata.get("MAP1", []):
        if block.get("mapping_type") == 3:
            half = len(block["entries"]) // 2
            pairs.update(zip(block["entries"][:half], block["entries"][half:]))
        else:
            pairs.update((char_code(char), glyph) for char, glyph in char_map({"MAP1": [block]}).items())
    return pairs


def _signed(value: int) -> int:
    return value - 256 if value > 127 else value


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = _Font(original, int(params.get("font", 0)))
    columns, rows = _grid(font, params)
    cell = font.cell
    packets = metadata["WID1"][0]["packets"]
    new_ink = coverage(sheets[0])
    if new_ink.size != (columns * cell, rows * cell):
        raise ValueError(f"The sheet is {new_ink.size}, the font grid {columns * cell}x{rows * cell}")
    old_metadata, old_sheets = extract(original, params)
    old_ink = coverage(old_sheets[0])

    pairs = _pairs(metadata)
    old_pairs = _pairs(old_metadata)
    used = max([font.glyphs - 1, *(glyph for _code, glyph in pairs)])
    if used >= columns * rows:
        raise ValueError(f"Glyph {used} is outside the grid of {columns * rows} cells")
    out = bytearray(original)
    added: List[bytes] = []
    template = font.records[font.map[ord("A")]] if font.map[ord("A")] else font.records[0]
    records = [list(r) for r in font.records]
    for index in range(used + 1):
        box = ((index % columns) * cell, (index // columns) * cell)
        box = box + (box[0] + cell, box[1] + cell)
        width = max(0, min(cell, int(packets[index]["width"]) if index < len(packets) else 0))
        crop = new_ink.crop(box)
        if index < font.glyphs:
            record = records[index]
            changed = crop.tobytes() != old_ink.crop(box).tobytes() or width != record[4]
            if not changed:
                continue
            record[0] = record[4] = width
            record[2] = (-int(packets[index]["kerning"])) & 0xFF
            bitmap = _encode(crop.crop((0, 0, width, record[1])))
            if len(bitmap) > font.slot:
                raise ValueError(f"Glyph {index} does not fit its slot")
            at = font.base + record[8]
            out[at:at + len(bitmap)] = bitmap
            _RECORD.pack_into(out, font.start + 0x20000 + 12 * index, *record)
        else:
            record = list(template)
            record[0] = record[4] = width
            record[2] = (-int(packets[index]["kerning"])) & 0xFF
            record[8] = len(original) - font.base + font.slot * len(added)
            bitmap = _encode(crop.crop((0, 0, width, record[1])))
            added.append(bitmap + b"\0" * (font.slot - len(bitmap)))
            records.append(record)
    if pairs != old_pairs:  # model codes below 256 are cp1252 bytes: undo only what changed
        unicode = {char_code(chr(code)): code for code, glyph in enumerate(font.map) if glyph}
        table = list(font.map)
        for code, _glyph in old_pairs - pairs:
            table[unicode.get(code, ord(code_char(code)))] = 0
        for code, glyph in pairs - old_pairs:
            point = ord(code_char(code))
            if point < 65536:
                table[point] = glyph
        struct.pack_into("<65536H", out, font.start, *table)
    if not added:
        return bytes(out)
    grow = 12 * len(added)
    at = font.start + 0x20000 + 12 * font.glyphs
    body = out[:at] + b"".join(_RECORD.pack(*r) for r in records[font.glyphs:]) + out[at:] + b"".join(added)
    struct.pack_into("<I", body, 0x14, font.base + grow)
    for index in range(font.index + 1, font.count):
        struct.pack_into("<I", body, 0x20 + 4 * index, font.offsets[index] + grow)
    struct.pack_into("<I", body, 0x08, len(body))
    return bytes(body)
