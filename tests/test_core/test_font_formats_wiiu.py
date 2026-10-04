"""Wii U BFFNT (big endian, GX2-tiled BC4 sheets) through the 3DS/Wii U backend, on synthetic files:
byte-exact round trips, redrawn cells, new characters, blank sheets added for new glyphs."""
import struct

from PIL import Image, ImageDraw

from core import font_formats
from core.font_formats import bcfnt, gx2

SHEET_W, SHEET_H, CELL, COLS, ROWS = 128, 64, 15, 8, 4
SHEET_SIZE = (SHEET_W // 4) * (SHEET_H // 4) * 8
WHITE = (255, 255, 255, 255)


def _sheet(ink: Image.Image, index: int = 0) -> bytes:
    """A BC4 sheet as the game stores it: upside down, 4x4 blocks in GX2 2D_TILED_THIN1 order."""
    flipped = ink.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    white = Image.new("L", flipped.size, 255)
    bc3 = Image.merge("RGBA", (white, white, white, flipped)).tobytes("bcn", 3)
    linear = [bc3[i:i + 8] for i in range(0, len(bc3), 16)]
    out = bytearray(SHEET_SIZE)
    for block, offset in zip(linear, gx2.element_offsets(SHEET_W // 4, SHEET_H // 4, 64, slice_index=index)):
        out[offset:offset + 8] = block
    return bytes(out)


def _font() -> bytes:
    """One sheet of 8x4 cells (15 px + 1 px gap); A B C direct, a table 0x400-0x405 with no glyphs yet."""
    ink = Image.new("L", (SHEET_W, SHEET_H))
    ImageDraw.Draw(ink).rectangle((1 + 4, 1 + 4, 1 + 7, 1 + 11), fill=255)       # glyph 0 'A'
    sheet = _sheet(ink)
    tglp_at, sheet_at = 0x34, 0x80
    cwdh_at = sheet_at + len(sheet)
    cwdh = b"CWDH" + struct.pack(">IHHI", 16 + 12, 0, 2, 0) + bytes([0, 8, 9, 1, 8, 9, 0, 8, 9]) + bytes(3)
    direct_at = cwdh_at + len(cwdh)
    table_at = direct_at + 24
    direct = b"CMAP" + struct.pack(">IHHHHIHH", 24, 0x41, 0x43, 0, 0, table_at + 8, 0, 0)
    table = b"CMAP" + struct.pack(">IHHHHI", 32, 0x400, 0x405, 1, 0, 0) + struct.pack(">6H", *[0xFFFF] * 6)
    finf = b"FINF" + struct.pack(">IBBBBHHbBBBIII", 0x20, 1, 16, 15, 12, 16, 0, 0, 8, 9, 1, tglp_at + 8,
                                 cwdh_at + 8, direct_at + 8)
    tglp = b"TGLP" + struct.pack(">IBBBBIHHHHHHI", cwdh_at - tglp_at, CELL, CELL, 1, CELL, SHEET_SIZE, 12,
                                 bcfnt.CAFE_BC4, COLS, ROWS, SHEET_W, SHEET_H, sheet_at)
    out = bytearray(b"FFNT\xfe\xff" + struct.pack(">HIIHH", 0x14, 0x03000000, 0, 5, 0))
    out += finf + tglp
    out += bytes(sheet_at - len(out))
    out += sheet + cwdh + direct + table
    struct.pack_into(">I", out, 0x0C, len(out))
    return bytes(out)


def _add_char(metadata, char, glyph, width=9):
    pairs = [(font_formats.char_code(c), g) for c, g in font_formats.char_map(metadata).items()]
    metadata["MAP1"] = [font_formats.map_entries(pairs + [(font_formats.char_code(char), glyph)])]
    metadata["WID1"][0]["packets"][glyph] = {"kerning": 0, "width": width}


def test_gx2_tiling_is_a_permutation_that_rotates_per_array_slice():
    first = gx2.element_offsets(32, 16, 64)
    second = gx2.element_offsets(32, 16, 64, slice_index=1)
    assert sorted(first) == list(range(0, 32 * 16 * 8, 8)) == sorted(second)
    assert first != second


def test_wiiu_font_is_detected_read_right_side_up_and_round_trips():
    data = _font()
    assert font_formats.detect(data) == "bffnt_wiiu"
    metadata, sheets = font_formats.extract("bffnt_wiiu", data)
    assert font_formats.char_map(metadata) == {"A": 0, "B": 1, "C": 2}
    assert sheets[0].size == (COLS * CELL, ROWS * CELL)
    ink = font_formats.coverage(sheets[0].crop((0, 0, CELL, CELL)))
    assert ink.getbbox() == (4, 4, 8, 12)                 # the gap row/column is gone, the sheet is not upside down
    assert metadata["WID1"][0]["packets"][1] == {"kerning": -1, "width": 9}
    assert font_formats.pack("bffnt_wiiu", metadata, sheets, data) == data


def test_wiiu_font_takes_a_new_character_in_a_free_cell():
    data = _font()
    metadata, sheets = font_formats.extract("bffnt_wiiu", data)
    ImageDraw.Draw(sheets[0]).rectangle((3 * CELL + 2, 2, 3 * CELL + 9, 12), fill=WHITE)     # free cell 3
    _add_char(metadata, "Є", 3)          # into the table block 0x400-0x405
    _add_char(metadata, "ґ", 3)          # outside every block: a new scan block
    edited = font_formats.pack("bffnt_wiiu", metadata, sheets, data)

    again, again_sheets = font_formats.extract("bffnt_wiiu", edited)
    assert font_formats.char_map(again) == {"A": 0, "B": 1, "C": 2, "Є": 3, "ґ": 3}
    assert font_formats.coverage(again_sheets[0].crop((3 * CELL, 0, 4 * CELL, CELL))).getbbox() == (2, 2, 10, 13)
    assert bcfnt._widths(edited, bcfnt._info(edited))[3] == (0, 10, 9)
    assert struct.unpack_from(">I", edited, 0x0C)[0] == len(edited)
    assert font_formats.pack("bffnt_wiiu", again, again_sheets, edited) == edited


def test_wiiu_font_grows_a_sheet_only_when_a_blank_one_is_used():
    data = _font()
    metadata, sheets = font_formats.extract("bffnt_wiiu", data, {"min_sheets": 2})
    assert len(sheets) == 2
    assert font_formats.pack("bffnt_wiiu", metadata, sheets, data, {"min_sheets": 2}) == data

    ImageDraw.Draw(sheets[1]).rectangle((2, 2, 9, 12), fill=WHITE)
    _add_char(metadata, "Ґ", COLS * ROWS)
    edited = font_formats.pack("bffnt_wiiu", metadata, sheets, data, {"min_sheets": 2})

    assert len(edited) >= len(data) + SHEET_SIZE
    again, again_sheets = font_formats.extract("bffnt_wiiu", edited)
    assert len(again_sheets) == 2 and font_formats.char_map(again)["Ґ"] == COLS * ROWS
    assert font_formats.coverage(again_sheets[1].crop((0, 0, CELL, CELL))).getbbox() == (2, 2, 10, 13)
    assert font_formats.coverage(again_sheets[0].crop((0, 0, CELL, CELL))).getbbox() == (4, 4, 8, 12)
    assert font_formats.char_map(again)["A"] == 0
