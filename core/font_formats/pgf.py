"""PSP PGF fonts (``PGF0``, the system font format ``sceFont`` reads, revision 2).

Layout (little endian): a 0x188-byte header (char map length and bits per entry at 0x10/0x18, char pointer
count and bits at 0x14/0x1C, first/last code at 0xB6/0xB8, the four metric table lengths at 0x102, shadow map
length and bits at 0x16C/0x170); the dimension, x-bearing, y-bearing and advance tables (pairs of s32); the
shadow map, the char map (code - first code -> glyph, bit-packed) and the char pointer table (glyph -> 32-bit
word offset into the glyph data, bit-packed), each padded to 32 bits; the glyph data. Bits are read from
little-endian 32-bit words, low bit first.

A glyph record: u14 size in bytes (its shadow glyph follows at that offset), u7 width, u7 height, s7 left,
s7 top, u6 flags, 2+2+3 shadow flags, u9 shadow id, then the dimension, x and y bearing and advance:
an 8-bit table index when flag 0x04 / 0x08 / 0x10 / 0x20 is set, else two s32 (26.6 fixed point); then the
4-bit pixels, run-length coded in nibbles (n < 8: n + 1 copies of the next nibble; n >= 8: 16 - n plain
nibbles), row by row (flags & 3 == 1) or column by column.

The editor model: one sheet of equal cells; a glyph stands with its pen origin at the same point of every cell
(``params`` of the model keep that point). Packing encodes again only the glyphs whose pixels or advance
changed (box, bearing from the new ink; advance in pixels) and lays the glyph data out anew; an unedited model
gives the file back byte for byte.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, code_char, coverage, grey_sheet, map_entries

MAGIC = b"PGF0"
HEADER = 0x188
COLUMNS = 16


class _Bits:
    def __init__(self, data: bytes):
        self.value = int.from_bytes(data, "little")

    def get(self, pos: int, count: int) -> int:
        return (self.value >> pos) & ((1 << count) - 1)


def _pack_bits(values: List[int], bits: int) -> bytes:
    total = 0
    for index, value in enumerate(values):
        total |= (value & ((1 << bits) - 1)) << (index * bits)
    size = ((len(values) * bits + 31) // 32) * 4
    return total.to_bytes(size, "little")


def _signed7(value: int) -> int:
    return value - 128 if value >= 64 else value


def _s32(value: int) -> int:
    return value - (1 << 32) if value >= 1 << 31 else value


class Font:
    """A parsed PGF: header fields, tables, char map and the glyph records."""

    def __init__(self, data: bytes):
        if data[4:8] != MAGIC or len(data) < HEADER:
            raise ValueError("Not a PGF font")
        self.data = data
        (self.revision, _version, self.map_len, self.ptr_len, self.map_bpe,
         self.ptr_bpe) = struct.unpack_from("<6i", data, 8)
        if self.revision != 2:
            raise ValueError(f"PGF revision {self.revision} is not supported (2 is)")
        self.first, self.last = struct.unpack_from("<HH", data, 0xB6)
        self.max_width, self.max_height = struct.unpack_from("<HH", data, 0xFC)
        lengths = data[0x102:0x106]
        self.shadow_len, self.shadow_bpe = struct.unpack_from("<ii", data, 0x16C)
        at = HEADER
        self.tables = []
        for length in lengths:
            pairs = [struct.unpack_from("<ii", data, at + 8 * i) for i in range(length)]
            self.tables.append(pairs)
            at += 8 * length
        at += ((self.shadow_len * self.shadow_bpe + 31) // 32) * 4
        self.map_at = at
        map_size = ((self.map_len * self.map_bpe + 31) // 32) * 4
        bits = _Bits(data[at:at + map_size])
        self.charmap = [bits.get(i * self.map_bpe, self.map_bpe) for i in range(self.map_len)]
        at += map_size
        self.ptr_at = at
        ptr_size = ((self.ptr_len * self.ptr_bpe + 31) // 32) * 4
        bits = _Bits(data[at:at + ptr_size])
        self.pointers = [bits.get(i * self.ptr_bpe, self.ptr_bpe) for i in range(self.ptr_len)]
        self.glyph_at = at + ptr_size
        self.glyph_data = data[self.glyph_at:]
        self.bits = _Bits(self.glyph_data)
        self.glyphs = [self._glyph(i) for i in range(self.ptr_len)]

    def _glyph(self, index: int) -> Dict[str, Any]:
        b = self.bits
        start = self.pointers[index] * 32
        pos = start
        size = b.get(pos, 14)
        w, h = b.get(pos + 14, 7), b.get(pos + 21, 7)
        left, top = _signed7(b.get(pos + 28, 7)), _signed7(b.get(pos + 35, 7))
        flags = b.get(pos + 42, 6)
        pos += 48 + 16
        metrics = []
        for number, flag in enumerate((0x04, 0x08, 0x10, 0x20)):
            if flags & flag:
                metrics.append(tuple(self.tables[number][b.get(pos, 8)]))
                pos += 8
            else:
                metrics.append((_s32(b.get(pos, 32)), _s32(b.get(pos + 32, 32))))
                pos += 64
        pixels = []
        count = w * h
        while len(pixels) < count:
            nibble = b.get(pos, 4)
            pos += 4
            if nibble < 8:
                pixels += [b.get(pos, 4)] * (nibble + 1)
                pos += 4
            else:
                for _ in range(16 - nibble):
                    pixels.append(b.get(pos, 4))
                    pos += 4
        pixels = pixels[:count]
        shadow_at = start // 8 + size
        shadow_size = b.get(shadow_at * 8, 14)
        return {"start": start // 8, "size": size, "end": shadow_at + shadow_size, "w": w, "h": h, "left": left,
                "top": top, "flags": flags, "head": b.get(start + 48, 16), "metrics": metrics,
                "pixels": pixels}

    def image(self, glyph: Dict[str, Any]) -> Image.Image:
        """The glyph's pixels (0-15) as an L image of its box."""
        w, h = glyph["w"], glyph["h"]
        out = Image.new("L", (max(w, 1), max(h, 1)))
        if not w or not h:
            return out
        values = glyph["pixels"]
        rows = glyph["flags"] & 3 == 1
        px = out.load()
        for i, value in enumerate(values):
            x, y = (i % w, i // w) if rows else (i // h, i % h)
            px[x, y] = value * 17
        return out


def _layout(font: Font) -> Dict[str, int]:
    """Where the pen origin stands in a cell, and the cell size, so every glyph fits."""
    lefts = [g["left"] for g in font.glyphs] or [0]
    tops = [g["top"] for g in font.glyphs] or [0]
    rights = [g["left"] + g["w"] for g in font.glyphs] or [1]
    bottoms = [g["top"] - g["h"] for g in font.glyphs] or [0]
    origin_x, origin_y = -min(min(lefts), 0), max(max(tops), 1)
    return {"origin_x": origin_x, "origin_y": origin_y,
            "cell_width": origin_x + max(rights) + 2, "cell_height": origin_y - min(min(bottoms), 0) + 2}


def _advance(glyph: Dict[str, Any]) -> int:
    return (glyph["metrics"][3][0] + 32) >> 6


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = Font(data)
    lay = _layout(font)
    cw, ch = lay["cell_width"], lay["cell_height"]
    count = len(font.glyphs)
    rows = (count + COLUMNS - 1) // COLUMNS
    ink = Image.new("L", (cw * COLUMNS, ch * rows))
    for index, glyph in enumerate(font.glyphs):
        x0 = (index % COLUMNS) * cw + lay["origin_x"] + glyph["left"]
        y0 = (index // COLUMNS) * ch + lay["origin_y"] - glyph["top"]
        if glyph["w"] and glyph["h"]:
            ink.paste(font.image(glyph), (x0, y0))
    pairs = [(char_code(chr(font.first + offset)), glyph) for offset, glyph in enumerate(font.charmap)
             if glyph < count]
    advance = max((_advance(g) for g in font.glyphs), default=8)
    metadata = {
        "header": {"signature": "PGF0", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": lay["origin_y"], "descent": ch - lay["origin_y"], "width": advance,
                  "leading": ch, "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": cw, "cell_height": ch,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": rows, "texture_width": cw * COLUMNS, "texture_height": ch * rows,
                  "base_line": lay["origin_y"]}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count - 1,
                  "packets": [{"kerning": -lay["origin_x"], "width": _advance(g)} for g in font.glyphs]}],
        "PGF": {"origin_x": lay["origin_x"], "origin_y": lay["origin_y"]},
    }
    return metadata, [grey_sheet(ink)]


def _rle(values: List[int]) -> List[int]:
    """Nibbles of the run-length code of ``values``."""
    out: List[int] = []
    i = 0
    while i < len(values):
        run = 1
        while i + run < len(values) and run < 8 and values[i + run] == values[i]:
            run += 1
        if run >= 2:
            out += [run - 1, values[i]]
            i += run
            continue
        plain = [values[i]]
        i += 1
        while i < len(values) and len(plain) < 8:
            if i + 1 < len(values) and values[i + 1] == values[i]:
                break
            plain.append(values[i])
            i += 1
        out += [16 - len(plain)] + plain
    return out


class _Writer:
    def __init__(self):
        self.value = 0
        self.pos = 0

    def put(self, value: int, bits: int) -> None:
        self.value |= (value & ((1 << bits) - 1)) << self.pos
        self.pos += bits

    def bytes(self) -> bytes:
        return self.value.to_bytes((self.pos + 7) // 8, "little")


def _record(font: Font, glyph: Dict[str, Any], cell: Image.Image, origin: Tuple[int, int], advance: int) -> bytes:
    """A new glyph record (with the old shadow glyph after it) for the ink of ``cell``."""
    ink = cell.point(lambda v: min(15, (v + 8) // 17))
    box = ink.getbbox()
    if box:
        x0, y0, x1, y1 = box
        w, h, left, top = x1 - x0, y1 - y0, x0 - origin[0], origin[1] - y0
        values = list(ink.crop(box).getdata())
    else:
        w = h = left = top = 0
        values = []
    if not (0 <= w < 128 and 0 <= h < 128 and -64 <= left < 64 and -64 <= top < 64):
        raise ValueError("A PGF glyph must fit 127 x 127 pixels around its origin")
    metrics = list(glyph["metrics"])
    metrics[0] = (w << 6, h << 6)
    if advance != _advance(glyph):
        metrics[3] = (advance << 6, metrics[3][1])
    flags = 1                                          # explicit metrics, pixels row by row
    bits = _Writer()
    bits.put(0, 14)
    for value, count in ((w, 7), (h, 7), (left, 7), (top, 7), (flags, 6), (glyph["head"], 16)):
        bits.put(value, count)
    for first, second in metrics:
        bits.put(first, 32)
        bits.put(second, 32)
    for nibble in _rle(values):
        bits.put(nibble, 4)
    record = bytearray(bits.bytes())
    size = len(record)
    if size >= 1 << 14:
        raise ValueError("PGF glyph record too large")
    record[0] = size & 0xFF
    record[1] = (record[1] & 0xC0) | (size >> 8)
    shadow = font.glyph_data[glyph["start"] + glyph["size"]:glyph["end"]]
    return bytes(record) + shadow


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = Font(original)
    meta_original, sheets_original = extract(original, params)
    gly = metadata["GLY1"][0]
    cw, ch = gly["cell_width"], gly["cell_height"]
    origin = (metadata.get("PGF", {}).get("origin_x", 0), metadata.get("PGF", {}).get("origin_y", 0))
    ink, old_ink = coverage(sheets[0]), coverage(sheets_original[0])
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    old_packets = meta_original["WID1"][0]["packets"]
    records: List[Optional[bytes]] = []
    changed = False
    for index, glyph in enumerate(font.glyphs):
        box = ((index % COLUMNS) * cw, (index // COLUMNS) * ch, (index % COLUMNS + 1) * cw, (index // COLUMNS + 1) * ch)
        cell = ink.crop(box)
        advance = int(packets[index]["width"]) if index < len(packets) else _advance(glyph)
        if cell.tobytes() == old_ink.crop(box).tobytes() and advance == old_packets[index]["width"]:
            records.append(None)
            continue
        records.append(_record(font, glyph, cell, origin, advance))
        changed = True
    if not changed:
        return original
    body = bytearray()
    pointers = []
    for glyph, record in zip(font.glyphs, records):
        pointers.append(len(body) // 4)
        body += record if record is not None else font.glyph_data[glyph["start"]:glyph["end"]]
        body += bytes(-len(body) % 4)
    bpe = font.ptr_bpe
    while max(pointers) >= 1 << bpe:
        bpe += 1
    head = bytearray(original[:font.ptr_at])
    struct.pack_into("<i", head, 0x1C, bpe)
    return bytes(head) + _pack_bits(pointers, bpe) + bytes(body)


def characters(data: bytes) -> Dict[int, str]:
    """Glyph index -> character, for reports."""
    font = Font(data)
    return {glyph: code_char(char_code(chr(font.first + offset))) for offset, glyph in enumerate(font.charmap)
            if glyph < len(font.glyphs)}
