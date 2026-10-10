"""Metal Gear Solid 2 / 3 Master Collection text font ``MGS_Font_nht.raw`` (taken out of the game program).

Layout (little endian)::

    0x00 "TNOF"  0x04 u32 0x28  0x08 u32 0x28  0x0C u32 4  0x10 u32 0x18  0x14 u32 entry count
    0x18 entries: u32 Unicode code point, u32 glyph offset (from the file start), sorted by code point;
         two codes may share a glyph
    glyphs: u8 width, u8 height, s8 x offset, s8 y offset (from the line top), u8 advance,
            then width x height bytes of 8-bit coverage

The model: a grid of cells of ``CELL_W`` x ``CELL_H``; a glyph stands at its offsets from the cell origin
(``ORIGIN_Y`` rows down, so accents above the line fit), WID1 width = advance, kerning 0. ``spare`` empty cells
after the glyphs take new characters (``ADDS_GLYPHS``). Packing writes the file again: an unchanged glyph keeps
its bytes, a changed or new one is cut to its ink box; the entry table is sorted again. An unedited model packs to
the original bytes.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, code_char, coverage, grey_sheet, map_entries

ADDS_GLYPHS = True
MAGIC = b"TNOF"
CELL_W, CELL_H, ORIGIN_Y = 44, 48, 4


def _signed(value: int) -> int:
    return value - 256 if value > 127 else value


def _parse(data: bytes):
    """``(entries [(code, glyph)], glyph offsets in file order)``."""
    if data[:4] != MAGIC:
        raise ValueError("Not an MGS Master Collection font (TNOF)")
    count = struct.unpack_from("<I", data, 0x14)[0]
    raw = [struct.unpack_from("<II", data, 0x18 + 8 * i) for i in range(count)]
    offsets = sorted({offset for _code, offset in raw})
    index = {offset: i for i, offset in enumerate(offsets)}
    return [(code, index[offset]) for code, offset in raw], offsets


def _record(data: bytes, offset: int) -> bytes:
    return data[offset:offset + 5 + data[offset] * data[offset + 1]]


def _grid(glyphs: int, params: Dict[str, Any]) -> Tuple[int, int]:
    columns = int(params.get("columns", 32))
    return columns, (glyphs + int(params.get("spare", 160)) + columns - 1) // columns


def _cell_image(record: bytes) -> Image.Image:
    width, height, x, y = record[0], record[1], _signed(record[2]), _signed(record[3])
    cell = Image.new("L", (CELL_W, CELL_H), 0)
    if width and height:
        cell.paste(Image.frombytes("L", (width, height), record[5:5 + width * height]), (x, y + ORIGIN_Y))
    return cell


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    entries, offsets = _parse(data)
    columns, rows = _grid(len(offsets), params)
    ink = Image.new("L", (columns * CELL_W, rows * CELL_H), 0)
    packets = []
    for index, offset in enumerate(offsets):
        record = _record(data, offset)
        ink.paste(_cell_image(record), ((index % columns) * CELL_W, (index // columns) * CELL_H))
        packets.append({"kerning": 0, "width": record[4]})
    packets += [{"kerning": 0, "width": 0}] * (columns * rows - len(packets))
    base = _record(data, offsets[dict(entries).get(ord("A"), 0)])
    baseline = ORIGIN_Y + _signed(base[3]) + base[1]
    metadata = {
        "header": {"signature": "MGS MC font (MGS_Font_nht.raw)", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": baseline, "descent": CELL_H - baseline, "width": base[4],
                  "leading": CELL_H, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": columns * rows - 1, "cell_width": CELL_W, "cell_height": CELL_H,
                  "page_data_size": 0, "texture_format": 8, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": columns * CELL_W, "texture_height": rows * CELL_H}],
        "MAP1": [map_entries([(char_code(chr(code)), glyph) for code, glyph in entries])],
        "WID1": [{"first_code_included": 0, "last_code_included": columns * rows, "packets": packets}],
    }
    return metadata, [grey_sheet(ink)]


def _encode(cell: Image.Image, advance: int) -> bytes:
    box = cell.getbbox()
    if not box:
        return bytes([0, 0, 0, 0, advance & 0xFF])
    left, top, right, bottom = box
    glyph = cell.crop(box)
    return bytes([right - left, bottom - top, left & 0xFF, (top - ORIGIN_Y) & 0xFF, advance & 0xFF]) + glyph.tobytes()


def _pairs(metadata: Metadata) -> List[Tuple[int, int]]:
    out = []
    for block in metadata.get("MAP1", []):
        entries = block.get("entries", [])
        half = len(entries) // 2
        out += [(ord(code_char(code)), glyph) for code, glyph in zip(entries[:half], entries[half:])]
    return out


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    entries, offsets = _parse(original)
    columns, rows = _grid(len(offsets), params)
    new_ink = coverage(sheets[0])
    if new_ink.size != (columns * CELL_W, rows * CELL_H):
        raise ValueError(f"The sheet is {new_ink.size}, the font grid {columns * CELL_W}x{rows * CELL_H}")
    packets = metadata["WID1"][0]["packets"]
    pairs = _pairs(metadata)
    used = max([len(offsets) - 1, *(glyph for _code, glyph in pairs)])
    if used >= columns * rows:
        raise ValueError(f"Glyph {used} is outside the grid of {columns * rows} cells")
    old_pairs = set(entries)
    if set(pairs) == old_pairs:
        table = entries                             # keep the original order (two codes may share a glyph)
    else:
        kept = [pair for pair in entries if pair in set(pairs)]
        table = sorted(kept + [pair for pair in pairs if pair not in old_pairs], key=lambda pair: pair[0])
    records = []
    for index in range(used + 1):
        box = ((index % columns) * CELL_W, (index // columns) * CELL_H)
        cell = new_ink.crop(box + (box[0] + CELL_W, box[1] + CELL_H))
        width = max(0, min(255, int(packets[index]["width"]) if index < len(packets) else 0))
        if index < len(offsets):
            record = _record(original, offsets[index])
            if cell.tobytes() == _cell_image(record).tobytes() and width == record[4]:
                records.append(record)
                continue
        records.append(_encode(cell, width))
    # Bytes no entry points at (a second copy of a shared glyph) stay after the glyph before them.
    spares = []
    for index, offset in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(original)
        spares.append(original[offset + len(_record(original, offset)):end])
    start = 0x18 + 8 * len(table)
    places, at = [], start
    for index, record in enumerate(records):
        if index < len(spares):
            records[index] = record = record + spares[index]
        places.append(at)
        at += len(record)
    head = bytearray(original[:0x18])
    struct.pack_into("<I", head, 0x14, len(table))
    body = b"".join(struct.pack("<II", code, places[glyph]) for code, glyph in table)
    return bytes(head) + body + b"".join(records)
