"""The ``cells`` font backend: fixed 4 bpp cells in a byte range, byte-exact round trip, an edit lands in its cell."""
from PIL import ImageDraw

from core import font_formats

PARAMS = {"offset": 4, "count": 4, "cell": [8, 16], "bpp": 4, "columns": 2, "chars": "AB C"}


def make_font() -> bytes:
    cells = bytearray(4 * 64)
    for glyph in range(4):
        for row in range(16):
            cells[glyph * 64 + row * 4] = 0xF0 | glyph   # pixel 0 = glyph index, pixel 1 = 15
    return b"HEAD" + bytes(cells) + b"TAIL"


def test_extract_maps_chars_and_pack_round_trips():
    data = make_font()
    metadata, sheets = font_formats.extract("cells", data, PARAMS)
    assert font_formats.char_map(metadata) == {"A": 0, "B": 1, " ": 2, "C": 3}
    assert sheets[0].size == (16, 32)
    assert sheets[0].getpixel((1, 0)) == (255, 255, 255, 255) and sheets[0].getpixel((8, 0)) == (17, 17, 17, 255)
    assert sheets[0].getpixel((0, 0))[3] == 0                      # value 0 is transparent
    assert font_formats.pack("cells", metadata, sheets, data, PARAMS) == data


def test_an_edit_changes_only_its_cell():
    data = make_font()
    metadata, sheets = font_formats.extract("cells", data, PARAMS)
    ImageDraw.Draw(sheets[0]).rectangle((8, 16, 15, 31), fill=(255, 255, 255, 255))   # glyph 3 (C) filled
    packed = font_formats.pack("cells", metadata, sheets, data, PARAMS)
    assert packed[:4 + 3 * 64] == data[:4 + 3 * 64] and packed[-4:] == b"TAIL"
    assert packed[4 + 3 * 64:4 + 4 * 64] == b"\xff" * 64


def test_tiles_layout_places_the_second_tile_right_of_the_first():
    params = {"offset": 0, "count": 1, "cell": [16, 16], "bpp": 4, "columns": 1, "tiles": True}
    cell = bytearray(128)
    cell[32] = 0x0F              # first pixel of tile 1 (top right) = 15
    _metadata, sheets = font_formats.extract("cells", bytes(cell), params)
    assert sheets[0].getpixel((8, 0)) == (255, 255, 255, 255) and sheets[0].getpixel((0, 2))[3] == 0
    assert font_formats.pack("cells", _metadata, sheets, bytes(cell), params) == bytes(cell)
