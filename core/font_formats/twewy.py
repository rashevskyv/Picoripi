"""The World Ends with You (DS) fonts: ``Apl_Fuk/Grp_Font.bin``, a ``pack`` of four bitmap fonts.

``Grp_Font.bin`` (``core.containers.twewy_pack``) holds, per font, a pack of glyph pages and a pack of width
tables (members ``#1``..``#n`` of each, one per page). A page is a 256 x 256 image of 4-bit pixels stored as
8 x 8 tiles (32 bytes a tile, rows of 4 bytes, low nibble first); glyph ``i`` of a page is cell ``i`` of a grid
of ``cell`` pixels, ``columns`` to a row, from the top left. A width table has one byte (the advance) per glyph.

The game's fonts (params ``pages``, ``widths``, ``cell``, ``columns``, ``chars``):

- the text font: pages ``#6`` (4), widths ``#2``, 10 x 10 cells, 25 a row, glyph = text code (``CHARACTERS``);
- a 10 x 12 font: pages ``#9`` (2), widths ``#8``, the same codes;
- two 16 x 16 fonts: pages ``#5`` (3) / ``#7`` (2), widths ``#1`` / ``#3``, 16 a row, digits and letters first
  (``BIG_CHARACTERS``).

Pixels: the nibble ``n`` is shown as grey ``17 * n`` with the same alpha (0 transparent), so an unedited font
packs back to the same bytes; a drawn pixel takes the nearest nibble.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from PIL import Image

from core.containers.twewy_pack import TwewyPack
from core.font_formats import Metadata, Sheets, char_code, coverage, grey_sheet, map_entries

PAGE = 256
PAGE_BYTES = PAGE * PAGE // 2

# Text code -> character (the text codec of plugins.twewy uses the same table). Codes 0x00-0x5E are ASCII
# 0x20-0x7E; the square brackets are shown full width so they never read as a tag. Accented Latin follows the
# Latin-1 order from 0x16D (Þ and þ are left out). Glyphs not named here are written as [g:XXX] tags.
CHARACTERS: Dict[int, str] = {code: chr(code + 0x20) for code in range(0x5F)}
CHARACTERS[0x3B], CHARACTERS[0x3D] = "［", "］"
_LATIN = "¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüý"
for _i, _c in enumerate(_LATIN):
    if _c not in "×÷":                      # those cells are empty in the font; 0x136 / 0x137 draw them
        CHARACTERS[0x16D + _i] = _c
CHARACTERS.update({
    0x11C: "—", 0x122: "…", 0x127: "（", 0x128: "）", 0x136: "×", 0x137: "÷", 0x139: "∞", 0x13F: "☆", 0x140: "★",
    0x141: "○", 0x142: "●", 0x143: "◎", 0x144: "◇", 0x145: "◆", 0x146: "□", 0x147: "■", 0x148: "△", 0x149: "▲",
    0x14A: "▽", 0x14B: "▼", 0x14C: "※", 0x14E: "→", 0x14F: "←", 0x150: "↑", 0x151: "↓", 0x152: "♯", 0x153: "♭",
    0x154: "♪", 0x155: "€", 0x15A: "Œ", 0x160: "™", 0x163: "¡", 0x164: "¢", 0x165: "£", 0x1C9: "　",
})
# The 16 x 16 fonts: a blank cell, the digits, the capitals, the small letters.
BIG_CHARACTERS: Dict[int, str] = {0: " ", **{1 + i: chr(48 + i) for i in range(10)},
                                  **{11 + i: chr(65 + i) for i in range(26)}, **{37 + i: chr(97 + i) for i in range(26)}}
TABLES = {"main": CHARACTERS, "big": BIG_CHARACTERS}


def _int(value: Any) -> int:
    return int(value, 0) if isinstance(value, str) else int(value)


def _layout(params: Dict[str, Any]) -> Tuple[str, str, int, int, int]:
    """``(pages member, widths member, cell width, cell height, columns)``."""
    cell = params.get("cell", (10, 10))
    return (f"#{_int(params['pages'])}", f"#{_int(params['widths'])}", _int(cell[0]), _int(cell[1]),
            _int(params.get("columns", PAGE // _int(cell[0]))))


def _members(pack: TwewyPack) -> List[str]:
    """The data members of a sub-pack: the descriptor (first) and the end block (last) left out."""
    return pack.list_files()[1:-1]


def decode_page(raw: bytes) -> Image.Image:
    """A page's nibbles as one grey channel (``17 * n``)."""
    ink = bytearray(PAGE * PAGE)
    for tile in range(len(raw) // 32):
        x0, y0 = (tile % 32) * 8, (tile // 32) * 8
        for y in range(8):
            for x in range(8):
                byte = raw[tile * 32 + y * 4 + (x >> 1)]
                ink[(y0 + y) * PAGE + x0 + x] = ((byte >> 4) if x & 1 else (byte & 15)) * 17
    return Image.frombytes("L", (PAGE, PAGE), bytes(ink))


def encode_page(ink: Image.Image) -> bytes:
    pixels = ink.tobytes()
    out = bytearray(PAGE_BYTES)
    for tile in range(PAGE_BYTES // 32):
        x0, y0 = (tile % 32) * 8, (tile // 32) * 8
        for y in range(8):
            for x in range(0, 8, 2):
                at = (y0 + y) * PAGE + x0 + x
                low, high = (min(15, (pixels[at + k] + 8) // 17) for k in (0, 1))
                out[tile * 32 + y * 4 + (x >> 1)] = high << 4 | low
    return bytes(out)


def _read(data: bytes, params: Dict[str, Any]):
    pages_name, widths_name, cell_w, cell_h, columns = _layout(params)
    outer = TwewyPack(data)
    pages, widths = TwewyPack(outer.read_file(pages_name)), TwewyPack(outer.read_file(widths_name))
    page_names, width_names = _members(pages), _members(widths)
    if len(page_names) != len(width_names) or any(len(pages.read_file(n)) != PAGE_BYTES for n in page_names):
        raise ValueError("Grp_Font.bin: pages and width tables do not match")
    return outer, pages, widths, page_names, width_names, cell_w, cell_h, columns


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    _outer, pages, widths, page_names, width_names, cell_w, cell_h, columns = _read(data, params)
    per_page = len(widths.read_file(width_names[0]))
    rows = per_page // columns
    sheets = [grey_sheet(decode_page(pages.read_file(name))) for name in page_names]
    advances = b"".join(widths.read_file(name) for name in width_names)
    count = len(advances)
    table = TABLES[str(params.get("chars", "main"))]
    pairs = [(char_code(char), code) for code, char in table.items() if code < count]
    metadata = {
        "header": {"signature": "pack", "num_chunks": 4},
        "INF1": [{"encoding": 1, "ascent": cell_h - 2, "descent": 2, "width": cell_w, "leading": cell_h,
                  "fallback_code": char_code("?"), "unk1": 0}],
        "GLY1": [{"start_glyph": 0, "end_glyph": count - 1, "cell_width": cell_w, "cell_height": cell_h,
                  "page_data_size": PAGE_BYTES, "texture_format": 0, "glyph_horizontal_count": columns,
                  "glyph_vertical_count": rows, "texture_width": PAGE, "texture_height": PAGE}],
        "MAP1": [map_entries(pairs)],
        "WID1": [{"first_code_included": 0, "last_code_included": count,
                  "packets": [{"kerning": 0, "width": int(value)} for value in advances]}],
    }
    return metadata, sheets


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    outer, pages, widths, page_names, width_names, _w, _h, _c = _read(original, params)
    pages_name, widths_name = _layout(params)[:2]
    if len(sheets) != len(page_names):
        raise ValueError(f"The font has {len(page_names)} pages, the edited one {len(sheets)}")
    for name, sheet in zip(page_names, sheets):
        if sheet.size != (PAGE, PAGE):
            raise ValueError(f"A page must be {PAGE}x{PAGE} pixels, not {sheet.width}x{sheet.height}")
        pages.write_file(name, encode_page(coverage(sheet)))
    packets = (metadata.get("WID1") or [{}])[0].get("packets", [])
    at = 0
    for name in width_names:
        old = widths.read_file(name)
        new = bytearray(old)
        for i in range(len(old)):
            if at + i < len(packets):
                value = int(packets[at + i].get("width", old[i]))
                if not 0 <= value <= 255:
                    raise ValueError(f"Glyph {at + i}: width {value} does not fit a byte")
                new[i] = value
        widths.write_file(name, bytes(new))
        at += len(old)
    outer.write_file(pages_name, pages.pack())
    outer.write_file(widths_name, widths.pack())
    return outer.pack()
