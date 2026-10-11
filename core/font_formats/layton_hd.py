"""Professor Layton HD ports (Android builds of the DS games, run on Switch homebrew loaders): ``font.dat``.

One file holds the game's whole font: u32 glyph count, u16 glyph height (30), u16 padding (4), u16 atlas width and
height (1024 x 512), ``count`` entries of u16 character code (Unicode, ascending) and u16 advance width, then the
atlas: 8 bits of coverage per pixel. Glyph ``i`` is the square cell ``i`` of the atlas, row by row, ``height + 2 *
padding`` (38) pixels a side, ``atlas width // cell`` (26) cells a row. The engine reads the text as UTF-8, so a
Ukrainian letter needs only an entry here.

The editor shows the 26 x 13 cells (spare ones after the glyphs for new letters). Packing an unedited model gives
the original bytes. Redrawn cells and changed advance widths are written in place. A character typed into a spare
cell gets an entry: the entries stay sorted by code (a cell is the entry's position, so the cells after a new
entry move one place on and are written again). Changing or removing a code the file has is refused.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, grey_sheet, map_entries

ADDS_GLYPHS = True
HEADER = 12


def _parse(data: bytes) -> Tuple[int, int, int, int, int, List[Tuple[int, int]]]:
    if len(data) < HEADER:
        raise ValueError("not a Layton HD font.dat")
    count, height, pad, width, rows_px = struct.unpack_from("<IHHHH", data, 0)
    if not 0 < count < 0x4000 or HEADER + 4 * count + width * rows_px != len(data) or not 0 < height + 2 * pad <= width:
        raise ValueError("not a Layton HD font.dat")
    entries = [struct.unpack_from("<HH", data, HEADER + 4 * i) for i in range(count)]
    return count, height, pad, width, rows_px, entries


def is_font(data: bytes) -> bool:
    try:
        _parse(bytes(data))
        return True
    except (ValueError, struct.error):
        return False


def _grid(height: int, pad: int, width: int, rows_px: int) -> Tuple[int, int, int]:
    cell = height + 2 * pad
    return cell, width // cell, rows_px // cell


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    count, height, pad, width, rows_px, entries = _parse(bytes(data))
    cell, columns, rows = _grid(height, pad, width, rows_px)
    atlas = Image.frombytes("L", (width, rows_px), bytes(data[HEADER + 4 * count:]))
    sheet = grey_sheet(atlas.crop((0, 0, columns * cell, rows * cell)))
    first: Dict[int, int] = {}
    for glyph, (code, _advance) in enumerate(entries):
        first.setdefault(char_code(chr(code)), glyph)
    metadata = {
        "header": {"signature": "Layton HD font.dat", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": height - 4, "descent": 4, "width": entries[0][1] if entries else 10,
                  "leading": height, "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": cell, "cell_height": cell,
                  "page_data_size": 0, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": columns * cell, "texture_height": rows * cell}],
        "MAP1": [map_entries(sorted(first.items()))],
        "WID1": [{"first_code_included": 0, "last_code_included": count,
                  "packets": [{"kerning": 0, "width": advance} for _code, advance in entries]}],
    }
    return metadata, [sheet]


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    original = bytes(original)
    count, height, pad, width, rows_px, entries = _parse(original)
    cell, columns, rows = _grid(height, pad, width, rows_px)
    ink = coverage(sheets[0])
    if ink.size != (columns * cell, rows * cell):
        raise ValueError(f"The sheet is {ink.width}x{ink.height}, the font grid {columns * cell}x{rows * cell}")
    old_atlas = Image.frombytes("L", (width, rows_px), original[HEADER + 4 * count:])
    packets = metadata["WID1"][0]["packets"]

    existing = {code: glyph for glyph, (code, _w) in enumerate(entries)}
    wanted: Dict[int, int] = {}
    for char, glyph in char_map(metadata).items():
        wanted[ord(char) if len(char) == 1 else 0] = glyph
    changed = [code for code, glyph in existing.items() if code in wanted and wanted[code] != glyph]
    changed += [code for code in existing if code not in wanted and code != 65279]
    if changed:
        raise ValueError("This font keeps the characters it has; changed or removed: "
                         + " ".join(f"U+{code:04X}" for code in sorted(changed)[:10]))
    new = {code: glyph for code, glyph in wanted.items() if code not in existing and code}
    if new and max(new) > 0xFFFF:
        raise ValueError("The font maps 16-bit character codes only")
    if new and min(new.values()) < count:
        raise ValueError(f"A new character must stand in a spare cell (glyph {count} on)")
    capacity = columns * rows
    if count + len(new) > capacity:
        raise ValueError(f"The font has room for {capacity} glyphs")

    def cell_box(index: int) -> Tuple[int, int, int, int]:
        x, y = (index % columns) * cell, (index // columns) * cell
        return (x, y, x + cell, y + cell)

    def advance(index: int, default: int) -> int:
        return max(0, min(0xFFFF, int(packets[index]["width"]))) if index < len(packets) else default

    items: List[Tuple[int, int, Image.Image]] = []
    for glyph, (code, old_advance) in enumerate(entries):
        items.append((code, advance(glyph, old_advance), ink.crop(cell_box(glyph))))
    for code, glyph in new.items():
        items.append((code, advance(glyph, entries[0][1]), ink.crop(cell_box(glyph))))
    if new:
        items.sort(key=lambda item: item[0])
    atlas = old_atlas.copy()
    for position, (_code, _advance, bitmap) in enumerate(items):
        atlas.paste(bitmap, cell_box(position)[:2])
    if new:
        blank = Image.new("L", (cell, cell), 0)
        for position in range(len(items), capacity):
            atlas.paste(blank, cell_box(position)[:2])
    head = struct.pack("<IHHHH", len(items), height, pad, width, rows_px)
    table = b"".join(struct.pack("<HH", code, adv) for code, adv, _bitmap in items)
    out = head + table + atlas.tobytes()
    return original if out == original else out
