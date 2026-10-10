"""Spike Chunsoft 3DS bitmap fonts (Pokémon Mystery Dungeon: Gates to Infinity, Super Mystery Dungeon): ``.dic`` + ``.img``.

``font/<name>.dic`` (``KAND``, u32 0, u32 glyph count, u32 0, then 20-byte entries sorted by character code: u16 code,
u16 x, u16 y, u16 width, u16 height, i16 x offset, i16 y offset, u16 advance, u32 extra) places each glyph in the atlas
``font/<name>.img`` (``core.texture_formats.pmd_img``: one 8-bit alpha channel, or RGBA8 in Gates to Infinity). The
font source names the ``.dic`` as ``path`` and the ``.img`` as ``companion``; the format gets both as one
``join_pair`` blob.

The model puts glyph ``i`` in cell ``i`` of one sheet, cells of the largest glyph box, ``params``: ``columns``
(default 16) and ``spare`` empty cells after the glyphs (default 160). A character typed into a spare cell adds a
glyph: a new box is laid out in the free part of the atlas below the game's own glyphs (the rows and gaps the game
uses: box width + 4, box height + 6), its entry is inserted in code order with the typical offsets of the font and
the advance from the width table. The width table writes the advance and the x offset (``-kerning``) of every glyph.
"""
from __future__ import annotations

import struct
from collections import Counter
from typing import Any, Dict, List, Tuple

from PIL import Image

from core.font_formats import Metadata, Sheets, char_code, char_map, coverage, grey_sheet, map_entries
from core.font_formats.sources import join_pair, split_pair
from core.texture_formats import pmd_img

ADDS_GLYPHS = True
MAGIC = b"KAND"
ENTRY = struct.Struct("<HHHHHhhHI")
GAP_X, GAP_Y, MARGIN = 4, 6, 2
PRIVATE = 0xF700


class Font:
    """The glyph entries of a ``.dic`` and the atlas of its ``.img``."""

    def __init__(self, data: bytes):
        dic, img = split_pair(data)
        if dic[:4] != MAGIC:
            raise ValueError("Not a Mystery Dungeon .dic font")
        count = struct.unpack_from("<I", dic, 8)[0]
        self.head = dic[:16]
        self.entries: List[List[int]] = [list(ENTRY.unpack_from(dic, 16 + i * ENTRY.size)) for i in range(count)]
        self.img = img
        self.atlas = pmd_img.read(img, {})[0].image
        self.alpha_only = pmd_img.read(img, {})[0].pixel_format == "A8"

    def box(self) -> Tuple[int, int]:
        return max(e[3] for e in self.entries), max(e[4] for e in self.entries)

    def pack_dic(self) -> bytes:
        self.entries.sort(key=lambda e: e[0])
        head = bytearray(self.head)
        struct.pack_into("<I", head, 8, len(self.entries))
        return bytes(head) + b"".join(ENTRY.pack(*e) for e in self.entries)


def _model_code(code: int) -> int:
    """The model code of a game character code. The fonts hold U+0080..U+009F (dashes and marks of the game's own
    choosing) beside U+2013 and the like, which the model would give the same cp1252 code: those go to U+F780.."""
    return PRIVATE + code if 0x80 <= code < 0xA0 else char_code(chr(code))


def _game_code(char: str) -> int:
    code = ord(char) if len(char) == 1 else -1
    return code - PRIVATE if PRIVATE + 0x80 <= code < PRIVATE + 0xA0 else code


def _grid(font: Font, params: Dict[str, Any]) -> Tuple[int, int]:
    columns = max(1, int(params.get("columns", 16)))
    cells = len(font.entries) + max(0, int(params.get("spare", 160)))
    return columns, (cells + columns - 1) // columns


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    font = Font(data)
    columns, rows = _grid(font, params)
    cell_w, cell_h = font.box()
    sheet = Image.new("RGBA", (columns * cell_w, rows * cell_h))
    packets = []
    for index, (code, x, y, w, h, xoff, _yoff, adv, _extra) in enumerate(font.entries):
        sheet.paste(font.atlas.crop((x, y, x + w, y + h)), ((index % columns) * cell_w, (index // columns) * cell_h))
        packets.append({"kerning": -xoff, "width": adv})
    typical = Counter(e[7] for e in font.entries).most_common(1)[0][0]
    for _ in range(len(font.entries), columns * rows):
        packets.append({"kerning": 0, "width": typical})
    if font.alpha_only:
        sheet = grey_sheet(sheet.split()[3])
    pairs = [(_model_code(e[0]), i) for i, e in enumerate(font.entries)]
    metadata = {
        "header": {"signature": "KAND", "num_chunks": 4, "texture_format": "A8" if font.alpha_only else "RGBA8"},
        "INF1": [{"encoding": 1, "ascent": cell_h, "descent": 0, "width": typical, "leading": cell_h + GAP_Y,
                  "fallback_code": 0x3F, "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": columns * rows - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "page_data_size": cell_w * cell_h, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": sheet.width, "texture_height": sheet.height}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": columns * rows, "packets": packets}],
    }
    return metadata, [sheet]


def _free_boxes(font: Font, cell_w: int, cell_h: int, count: int) -> List[Tuple[int, int]]:
    """``count`` box positions below the game's glyphs, in rows; raises when the atlas is full."""
    width, height = font.atlas.size
    y = max(e[2] + e[4] for e in font.entries) + MARGIN
    x, found = MARGIN, []
    while len(found) < count:
        if x + cell_w > width:
            x, y = MARGIN, y + cell_h + GAP_Y
        if y + cell_h > height:
            raise ValueError(f"The atlas ({width}x{height}) has room for {len(found)} new glyphs, not {count}")
        found.append((x, y))
        x += cell_w + GAP_X
    return found


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    font = Font(original)
    columns, rows = _grid(font, params)
    cell_w, cell_h = font.box()
    sheet = sheets[0].convert("RGBA")
    if sheet.size != (columns * cell_w, rows * cell_h):
        raise ValueError(f"The sheet is {sheet.width}x{sheet.height}, the font grid {columns * cell_w}x{rows * cell_h}")
    if font.alpha_only:
        sheet = grey_sheet(coverage(sheet))
    packets = metadata["WID1"][0]["packets"]
    count = len(font.entries)
    existing = {e[0]: i for i, e in enumerate(font.entries)}
    wanted = {_game_code(char): glyph for char, glyph in char_map(metadata).items()}
    changed = [code for code, glyph in existing.items() if wanted.get(code) != glyph]
    if changed:
        raise ValueError("This font keeps the characters it has; changed or removed: "
                         + " ".join(f"U+{code:04X}" for code in sorted(changed)[:10]))
    new = sorted((code, glyph) for code, glyph in wanted.items() if code not in existing)
    if new and (max(glyph for _c, glyph in new) >= columns * rows or max(code for code, _g in new) > 0xFFFF):
        raise ValueError("A new character is beyond the sheet's cells or above U+FFFF")
    xoff_typical = Counter(e[5] for e in font.entries).most_common(1)[0][0]
    yoff_typical = Counter(e[6] for e in font.entries).most_common(1)[0][0]
    extra_typical = Counter(e[8] for e in font.entries).most_common(1)[0][0]
    glyph_of = list(range(count))                     # entry index -> cell of the sheet
    for (code, glyph), (x, y) in zip(new, _free_boxes(font, cell_w, cell_h, len(new))):
        packet = packets[glyph] if glyph < len(packets) else {"kerning": -xoff_typical, "width": cell_w}
        font.entries.append([code, x, y, cell_w, cell_h, _clamp(-int(packet["kerning"]), -32768, 32767), yoff_typical,
                             _clamp(packet["width"], 0, 65535), extra_typical])
        glyph_of.append(glyph)
    atlas = font.atlas.copy()
    for index, entry in enumerate(font.entries):
        glyph = glyph_of[index]
        code, x, y, w, h, _xoff, _yoff, _adv, _extra = entry
        cell = sheet.crop(((glyph % columns) * cell_w, (glyph // columns) * cell_h,
                           (glyph % columns) * cell_w + w, (glyph // columns) * cell_h + h))
        if index < count:
            packet = packets[index]
            entry[5] = _clamp(-int(packet["kerning"]), -32768, 32767)
            entry[7] = _clamp(packet["width"], 0, 65535)
        atlas.paste(cell, (x, y))
    img = pmd_img.write(font.img, {0: atlas}, {})
    return join_pair(font.pack_dic(), img)
