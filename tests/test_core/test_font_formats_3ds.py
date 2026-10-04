"""3DS font backends (BCFNT / 3DS BFFNT, Grezzo QBF and GZF) on synthetic files: byte-exact round trips,
edits written where they belong, new characters added."""
import struct

import pytest
from PIL import Image, ImageDraw

from core import font_formats
from core.font_formats import bcfnt, gzf, qbf

WHITE = (255, 255, 255, 255)


def _cell_box(metadata, glyph):
    gly = metadata["GLY1"][0]
    per_sheet = gly["glyph_horizontal_count"] * gly["glyph_vertical_count"]
    sheet, cell = divmod(glyph, per_sheet)
    x, y = (cell % gly["glyph_horizontal_count"]) * gly["cell_width"], (cell // gly["glyph_horizontal_count"]) * gly["cell_height"]
    return sheet, (x, y, x + gly["cell_width"], y + gly["cell_height"])


def _add_char(metadata, char, glyph, kerning=0, width=5):
    entries = metadata["MAP1"][0]["entries"]
    half = len(entries) // 2
    entries.insert(half, font_formats.char_code(char))
    entries.append(glyph)
    metadata["WID1"][0]["packets"][glyph] = {"kerning": kerning, "width": width}


# -- PICA textures ------------------------------------------------------------------------------


def test_pica_texels_are_morton_tiles_low_nibble_first():
    image = Image.new("RGBA", (8, 8))
    image.putpixel((1, 0), WHITE)        # texel 1 -> high nibble of byte 0
    image.putpixel((0, 1), WHITE)        # texel 2 -> low nibble of byte 1
    raw = bcfnt.encode(image, bcfnt.A4)
    assert raw[:2] == b"\xf0\x0f" and not any(raw[2:])
    assert bcfnt.decode(raw, bcfnt.A4, 8, 8).tobytes() == image.tobytes()


def test_pica_la4_keeps_luminance_and_alpha():
    image = Image.new("RGBA", (8, 8), (255, 255, 255, 0))
    image.putpixel((2, 3), (68, 68, 68, 255))
    raw = bcfnt.encode(image, bcfnt.LA4)
    assert bcfnt.decode(raw, bcfnt.LA4, 8, 8).tobytes() == image.tobytes()
    assert bcfnt.encode(bcfnt.decode(raw, bcfnt.LA4, 8, 8), bcfnt.LA4) == raw


# -- BCFNT / 3DS BFFNT ----------------------------------------------------------------------------


def _ctr_font(magic=b"FFNT", fmt=bcfnt.A4, glyphs=4):
    """A 3DS font: 2x2 cells of 4x4 on one 16x16 sheet; A B C direct, Ё (glyph 3) in a table 0x400-0x405.

    With ``glyphs=3`` the last cell is free: no width entry and no character."""
    texture = Image.new("RGBA", (16, 16))
    draw = ImageDraw.Draw(texture)
    draw.rectangle((1, 1, 3, 4), fill=WHITE)            # glyph 0 'A', inside cell 0 (x 1..4, y 1..4)
    draw.rectangle((6, 1, 7, 2), fill=WHITE)            # glyph 1 'B'
    sheet = bcfnt.encode(texture, fmt)
    tglp_at, sheet_at = 0x34, 0x80
    cwdh_at = sheet_at + len(sheet)
    entries = bytes([0, 3, 4, 1, 2, 3, 0, 0, 4, 0, 4, 5][:3 * glyphs])
    cwdh = b"CWDH" + struct.pack("<IHHI", 16 + len(entries), 0, glyphs - 1, 0) + entries
    cwdh += bytes(-len(cwdh) % 4)
    direct_at = cwdh_at + len(cwdh)
    direct = b"CMAP" + struct.pack("<IHHHHIH", 24, 0x41, 0x43, 0, 0, 0, 0) + bytes(2)
    table_at = direct_at + len(direct)
    table = b"CMAP" + struct.pack("<IHHHHI", 20 + 12, 0x400, 0x405, 1, 0, 0) + struct.pack("<6H", 0xFFFF, 3 if glyphs == 4 else 0xFFFF, *[0xFFFF] * 4)
    direct = direct[:16] + struct.pack("<I", table_at + 8) + direct[20:]
    if magic == b"CFNT":
        finf = b"FINF" + struct.pack("<IBbHbBBBIIIBBBB", 0x20, 1, 6, 0, 0, 4, 5, 1, tglp_at + 8, cwdh_at + 8,
                                     direct_at + 8, 6, 4, 5, 0)
        tglp = b"TGLP" + struct.pack("<IBBbBIHHHHHHI", sheet_at - tglp_at, 4, 4, 5, 4, len(sheet), 1, fmt, 2, 2,
                                     16, 16, sheet_at)
    else:
        finf = b"FINF" + struct.pack("<IBBBBHHbBBBIII", 0x20, 2, 6, 4, 5, 6, 0, 0, 4, 5, 1, tglp_at + 8,
                                     cwdh_at + 8, direct_at + 8)
        tglp = b"TGLP" + struct.pack("<IBBBBIHHHHHHI", sheet_at - tglp_at, 4, 4, 1, 4, len(sheet), 5, fmt, 2, 2,
                                     16, 16, sheet_at)
    out = bytearray(magic + b"\xff\xfe" + struct.pack("<HIIHH", 0x14, 0x04000000 if magic == b"FFNT" else 0x03000000,
                                                       0, 5, 0))
    out += finf + tglp
    out += bytes(sheet_at - len(out))
    out += sheet + cwdh + direct + table
    struct.pack_into("<I", out, 0x0C, len(out))
    return bytes(out)


@pytest.mark.parametrize("magic", [b"FFNT", b"CFNT"])
def test_ctr_font_reads_cells_without_the_gap_and_round_trips(magic):
    data = _ctr_font(magic)
    assert font_formats.detect(data) == "bcfnt"
    metadata, sheets = font_formats.extract("bcfnt", data)
    assert font_formats.char_map(metadata) == {"A": 0, "B": 1, "C": 2, "Ё": 3}
    assert metadata["GLY1"][0]["cell_width"] == 4 and sheets[0].size == (8, 8)
    assert sheets[0].getchannel("A").crop((0, 0, 3, 4)).getextrema() == (255, 255)     # gap row/column gone
    assert metadata["WID1"][0]["packets"][1] == {"kerning": -1, "width": 3}
    assert font_formats.pack("bcfnt", metadata, sheets, data) == data


@pytest.mark.parametrize("magic", [b"FFNT", b"CFNT"])
def test_ctr_font_edits_pixels_widths_and_adds_characters(magic):
    data = _ctr_font(magic)
    metadata, sheets = font_formats.extract("bcfnt", data)
    metadata["WID1"][0]["packets"][0] = {"kerning": 1, "width": 6}
    ImageDraw.Draw(sheets[0]).rectangle((4, 0, 5, 1), fill=WHITE)                     # redraw glyph 1 (B)
    _add_char(metadata, "Є", 1)                     # alias into the table block (in place)
    ImageDraw.Draw(sheets[0]).rectangle((4, 4, 6, 7), fill=WHITE)                     # redraw glyph 3 (Ё)
    _add_char(metadata, "ґ", 3)                     # outside every block -> a new scan block
    edited = font_formats.pack("bcfnt", metadata, sheets, data)

    again, again_sheets = font_formats.extract("bcfnt", edited)
    assert font_formats.char_map(again) == {"A": 0, "B": 1, "C": 2, "Ё": 3, "Є": 1, "ґ": 3}
    assert again["WID1"][0]["packets"][0] == {"kerning": 1, "width": 6}
    assert again_sheets[0].tobytes() == sheets[0].tobytes()
    assert struct.unpack_from("<I", edited, 0x0C)[0] == len(edited)
    widths = bcfnt._widths(edited, bcfnt._info(edited))
    assert widths[1][1] == 2                         # glyph width follows the redrawn ink
    assert font_formats.pack("bcfnt", again, again_sheets, edited) == edited


def test_ctr_font_new_glyph_gets_a_width_block():
    data = _ctr_font(glyphs=3)
    metadata, sheets = font_formats.extract("bcfnt", data)
    ImageDraw.Draw(sheets[0]).rectangle((4, 4, 5, 7), fill=WHITE)                     # free cell 3
    _add_char(metadata, "Ґ", 3, kerning=-1, width=3)
    edited = font_formats.pack("bcfnt", metadata, sheets, data)
    info = bcfnt._info(edited)
    assert len(bcfnt._chain(edited, info["cwdh"], b"CWDH", 12)) == 2
    assert bcfnt._widths(edited, info)[3] == (1, 2, 3)
    assert font_formats.char_map(font_formats.extract("bcfnt", edited)[0])["Ґ"] == 3


def test_ctr_font_refuses_a_changed_character():
    data = _ctr_font()
    metadata, sheets = font_formats.extract("bcfnt", data)
    metadata["MAP1"][0] = font_formats.map_entries([(0x41, 1), (0x42, 1), (0x43, 2), (0x401, 3)])
    with pytest.raises(ValueError, match="U\\+0041"):
        font_formats.pack("bcfnt", metadata, sheets, data)


# -- QBF ------------------------------------------------------------------------------------------


def _qbf(bpp=4):
    cell = 4 * 4 * bpp // 8
    entries = [(0x41, 0, 1, 3, 0), (0x42, 1, 0, 4, 0), (0xFF21, 0, 0, 5, 1)]     # full-width Ａ shares cell 0
    out = bytearray(b"QBF1" + struct.pack("<HHI", len(entries), 3, 42) + bytes([bpp, 4, 4, 2]))
    for entry in entries:
        out += struct.pack("<HHBBH", *entry)
    cells = bytearray(cell * 3)
    cells[0] = 0xF0 if bpp == 4 else 0xFF          # one white pixel at (0, 0) of cell 0
    if bpp == 8:
        cells[cell:cell * 2] = b"\xf0" * cell      # transparent white, as sys8 stores its background
    return bytes(out + cells)


@pytest.mark.parametrize("bpp", [4, 8])
def test_qbf_round_trip_and_shared_cells(bpp):
    data = _qbf(bpp)
    assert font_formats.detect(data) == "qbf"
    metadata, sheets = font_formats.extract("qbf", data)
    assert font_formats.char_map(metadata) == {"A": 0, "B": 1, "Ａ": 0}
    assert metadata["WID1"][0]["packets"][0] == {"kerning": 1, "width": 3}
    assert sheets[0].getpixel((0, 0)) == WHITE
    assert metadata["GLY1"][0]["end_glyph"] + 1 >= 3 + qbf.SPARE_CELLS
    assert font_formats.pack("qbf", metadata, sheets, data) == data


def test_qbf_adds_a_character_in_code_order_and_keeps_shared_metrics():
    data = _qbf()
    metadata, sheets = font_formats.extract("qbf", data)
    metadata["WID1"][0]["packets"][0] = {"kerning": 2, "width": 6}            # A's cell: Ａ keeps its own
    ImageDraw.Draw(sheets[0]).point((13, 1), fill=WHITE)                       # cell 3 (x 12..15)
    _add_char(metadata, "Є", 3, kerning=1, width=4)
    edited = font_formats.pack("qbf", metadata, sheets, data)
    assert struct.unpack_from("<HH", edited, 4) == (4, 4)
    codes = [struct.unpack_from("<HHBBH", edited, 16 + 8 * i) for i in range(4)]
    assert codes == [(0x41, 0, 2, 6, 0), (0x42, 1, 0, 4, 0), (0x404, 3, 1, 4, 0), (0xFF21, 0, 0, 5, 1)]
    again, again_sheets = font_formats.extract("qbf", edited)
    assert again_sheets[0].getpixel((13, 1)) == WHITE
    assert font_formats.pack("qbf", again, again_sheets, edited) == edited


# -- GZF ------------------------------------------------------------------------------------------


def _gzf(records=2, gap=0x20):
    """Two 16x16 A4 sheets (the second 16x8) of 4x4 cells; glyphs A (sheet 0) and B (sheet 1)."""
    table = gzf.HEADER + 8 * 2
    first = table + 12 * records + gap
    first += -first % gzf.ALIGN
    head = bytearray(b"GZFX" + bytes(0x2C))
    struct.pack_into("<II", head, 0x10, 2, records)
    struct.pack_into("<H", head, 0x22, 4)
    struct.pack_into("<I", head, 0x28, 4)
    sheet0 = Image.new("RGBA", (16, 16))
    sheet0.putpixel((1, 1), WHITE)
    sheet1 = Image.new("RGBA", (16, 8))
    raw0, raw1 = bcfnt.encode(sheet0, bcfnt.A4), bcfnt.encode(sheet1, bcfnt.A4)
    head += struct.pack("<IHH", first, 16, 16) + struct.pack("<IHH", first + len(raw0), 16, 8)
    head += struct.pack("<IHHHH", 0x41, 5, 0, 1, 0x0000) + struct.pack("<IHHHH", 0x42, 6, 1, 0, 0x0101)
    head += bytes(first - len(head))
    return bytes(head + raw0 + raw1)


def test_gzf_round_trip_and_cells():
    data = _gzf()
    assert font_formats.detect(data) == "gzf"
    metadata, sheets = font_formats.extract("gzf", data)
    assert font_formats.char_map(metadata) == {"A": 0, "B": 16 + 5}          # sheet 1, row 1, column 1
    assert len(sheets) == 2 and sheets[1].size == (16, 16)
    assert sheets[0].getpixel((1, 1)) == WHITE
    assert metadata["WID1"][0]["packets"][0] == {"kerning": 1, "width": 5}
    assert font_formats.pack("gzf", metadata, sheets, data) == data


def test_gzf_growing_table_moves_the_sheets_and_short_sheet_rows_are_refused():
    data = _gzf(gap=0)
    metadata, sheets = font_formats.extract("gzf", data)
    for char, glyph in zip("ЄІЇҐєіїґ", [1, 2, 3, 16, 17, 18, 19, 20]):     # sheet 1 has rows 0-1 only
        _add_char(metadata, char, glyph)
    ImageDraw.Draw(sheets[1]).point((0, 4), fill=WHITE)
    edited = font_formats.pack("gzf", metadata, sheets, data)
    offsets = [struct.unpack_from("<I", edited, gzf.HEADER + 8 * i)[0] for i in range(2)]
    assert offsets[0] % gzf.ALIGN == 0 and offsets[0] > struct.unpack_from("<I", data, gzf.HEADER)[0]
    again, again_sheets = font_formats.extract("gzf", edited)
    assert font_formats.char_map(again)["ґ"] == font_formats.char_map(metadata)["ґ"]
    assert again_sheets[1].getpixel((0, 4)) == WHITE
    assert font_formats.pack("gzf", again, again_sheets, edited) == edited

    again["MAP1"][0] = font_formats.map_entries(                     # ї moved to row 3: the sheet has 2 rows
        [(font_formats.char_code(c), 16 + 12 if c == "ї" else g) for c, g in font_formats.char_map(again).items()])
    with pytest.raises(ValueError, match="outside the texture"):
        font_formats.pack("gzf", again, again_sheets, edited)
