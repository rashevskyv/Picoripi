"""Final Fantasy Tactics A2 (DS) font: ``menu/font/UseMoji_image.bin`` and ``menu/font/FontWidthTable.bin``.

The two files come as one blob (``sources.join_pair``: the image file, the width table as ``companion``).

``UseMoji_image.bin``: u16 glyph count, u32 offset per glyph, then the glyphs: u8 record size (4 + 4 per row),
u8 placement (high nibble = top row in the 16 x 16 cell, low nibble kept as it is), u8 glyph number, u8 0, then
one u32 per row: 16 pixels of 2 bits, pixel 0 in the low bits. ``FontWidthTable.bin``: u16 count, one advance
byte per glyph, zero filler to 4 bytes. Text code ``c`` (below 0xC0) draws glyph ``c - 1`` (``CHARACTERS``).

The model: glyph ``i`` in cell ``i`` of a 16-column grid of 16 x 16 cells; ``params.spare`` empty cells follow
(default: up to code 0xBF, the last glyph code). Pixel values 1-3 are grey 85 / 170 / 255. A cell that did not
change keeps its bytes; a redrawn one is cut to its inked rows. A character typed into a spare cell adds a glyph
(its code is the cell number + 1) with its width.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, grey_sheet, map_entries
from core.font_formats.sources import join_pair, split_pair

ADDS_GLYPHS = True
CELL, COLUMNS, LAST_CODE = 16, 16, 0xBF

# Text code -> character (the plugin's text codec uses the same table). The square brackets are full width
# so they never read as a tag; codes without a character here (0x96, 0x97, 0xA0-0xA3) are icons.
CHARACTERS: Dict[int, str] = {1: " "}
for _i, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                        "ÀÁÂÄÆÇÈÉÊËÌÍÎÏÑÒÓÔÖŒÙÚÛÜßàáâäæçèéêëìíîïñòóôöœùúûü0123456789"
                        "~`!?#%^&*/_+=,.;:¥'\"„()［］{}|-ー—«»·¡¿°"):
    CHARACTERS[2 + _i] = _c
CHARACTERS.update({0x98: "♪", 0x99: "↓", 0x9A: "←", 0x9B: "↑", 0x9C: "→", 0x9D: "™", 0x9E: "®", 0x9F: "©",
                   0xA4: "<", 0xA5: ">", 0xA6: "≠", 0xA7: "≤", 0xA8: "≥"})


def _glyphs(image: bytes) -> List[bytes]:
    count = struct.unpack_from("<H", image, 0)[0]
    offsets = [struct.unpack_from("<I", image, 2 + 4 * i)[0] for i in range(count)]
    return [bytes(image[at:at + image[at]]) for at in offsets]


def _widths(table: bytes) -> List[int]:
    count = struct.unpack_from("<H", table, 0)[0]
    return list(table[2:2 + count])


def _decode(record: bytes) -> Image.Image:
    cell = Image.new("L", (CELL, CELL))
    top = record[1] >> 4 if record[1] != 0xFF else 0
    for row in range((record[0] - 4) // 4):
        value = struct.unpack_from("<I", record, 4 + 4 * row)[0]
        for x in range(CELL):
            level = value >> (2 * x) & 3
            if level and top + row < CELL:
                cell.putpixel((x, top + row), level * 85)
    return cell


def _encode(cell: Image.Image, number: int, low: int) -> bytes:
    levels = [[min(3, (cell.getpixel((x, y)) + 42) // 85) for x in range(CELL)] for y in range(CELL)]
    rows = [y for y in range(CELL) if any(levels[y])]
    if not rows:
        return bytes((4, 0xFF, number & 0xFF, 0))
    top, bottom = rows[0], rows[-1]
    out = bytearray((4 + 4 * (bottom - top + 1), top << 4 | (low & 15), number & 0xFF, 0))
    for y in range(top, bottom + 1):
        out += struct.pack("<I", sum(level << (2 * x) for x, level in enumerate(levels[y])))
    return bytes(out)


def _cells(params: Dict[str, Any], count: int) -> int:
    return max(count, count + int(params["spare"])) if "spare" in params else max(count, LAST_CODE)


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    image, table = split_pair(data)
    glyphs, widths = _glyphs(image), _widths(table)
    cells = _cells(params, len(glyphs))
    rows = -(-cells // COLUMNS)
    ink = Image.new("L", (COLUMNS * CELL, rows * CELL))
    for index, record in enumerate(glyphs):
        ink.paste(_decode(record), ((index % COLUMNS) * CELL, (index // COLUMNS) * CELL))
    packets = [{"kerning": 0, "width": widths[i] if i < len(widths) else 8} for i in range(COLUMNS * rows)]
    pairs = [(char_code(char), code - 1) for code, char in CHARACTERS.items() if code - 1 < len(glyphs)]
    metadata = {
        "header": {"signature": "UseMoji", "num_chunks": 2},
        "INF1": [{"encoding": 1, "ascent": 13, "descent": 3, "width": 8, "leading": CELL,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": COLUMNS * rows - 1, "cell_width": CELL, "cell_height": CELL,
                  "page_data_size": 0, "texture_format": 2, "glyph_horizontal_count": COLUMNS,
                  "glyph_vertical_count": rows, "texture_width": ink.width, "texture_height": ink.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": COLUMNS * rows, "packets": packets}],
    }
    return metadata, [grey_sheet(ink)]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    image, table = split_pair(original)
    glyphs, widths = _glyphs(image), _widths(table)
    old_metadata, old_sheets = extract(original, params)
    ink, old_ink = coverage(sheets[0]), coverage(old_sheets[0])
    if ink.size != old_ink.size:
        raise ValueError(f"The sheet is {ink.width}x{ink.height}, the font grid {old_ink.width}x{old_ink.height}")
    packets = metadata["WID1"][0]["packets"]
    known = {char: glyph for char, glyph in char_map(old_metadata).items()}
    wanted = char_map(metadata)
    changed = [char for char, glyph in known.items() if wanted.get(char) != glyph]
    if changed:
        raise ValueError("This font keeps the characters it has; changed or removed: " + " ".join(changed[:10]))
    added = {char: glyph for char, glyph in wanted.items() if char not in known}
    last = max([len(glyphs) - 1, *added.values()])
    if last + 1 > LAST_CODE:
        raise ValueError(f"Glyph {last} would need text code {last + 1:#x}; codes stop at {LAST_CODE:#x}")
    new_glyphs, new_widths = list(glyphs), list(widths)
    for index in range(last + 1):
        box = ((index % COLUMNS) * CELL, (index // COLUMNS) * CELL)
        box = box + (box[0] + CELL, box[1] + CELL)
        cell = ink.crop(box)
        if index >= len(glyphs):
            new_glyphs.append(_encode(cell, index, 3))
        elif cell.tobytes() != old_ink.crop(box).tobytes():
            new_glyphs[index] = _encode(cell, index, glyphs[index][1])
        width = int(packets[index]["width"]) if index < len(packets) else 8
        if not 0 <= width <= 255:
            raise ValueError(f"Glyph {index}: width {width} does not fit a byte")
        if index < len(new_widths):
            new_widths[index] = width
        else:
            new_widths.append(width)
    if new_glyphs == glyphs and new_widths == widths:
        return bytes(original)
    head = 2 + 4 * len(new_glyphs)
    offsets, body = [], bytearray()
    for record in new_glyphs:
        offsets.append(head + len(body))
        body += record
    new_image = struct.pack(f"<H{len(offsets)}I", len(offsets), *offsets) + bytes(body)
    new_image += bytes(-len(new_image) % 16)          # the game's file is padded to 16 bytes
    new_table = struct.pack("<H", len(new_widths)) + bytes(new_widths)
    new_table += bytes(-len(new_table) % 4)
    return join_pair(new_image, new_table)
