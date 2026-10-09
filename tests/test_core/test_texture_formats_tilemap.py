"""Tile-map pictures (``tilemap``): a pattern name map over 4/8 bpp cells, read as one picture, written back by
reusing, redrawing in place, taking free cells or growing the bank."""
import struct

import pytest
from PIL import Image

from core import texture_formats

PALETTE = b"".join(struct.pack("<H", (i & 31) | (i >> 1 & 31) << 5 | (i & 31) << 10) for i in range(32)).hex()


def _file(names, cells, cols=4, rows=2):
    return struct.pack(f">{cols * rows}H", *names) + b"".join(cells)


def _params(**extra):
    return {"bpp": 4, "nibble": "high", "cols": 4, "rows": 2, "cells_offset": 16, "unit": 32, "name_mask": "0x3ff",
            "pal_shift": 12, "pal_mask": 15, "hflip_bit": 10, "vflip_bit": 11, "palette": PALETTE, **extra}


def _cell(index):
    return bytes([index << 4 | index] * 32)                   # one colour index over the 8x8 cell


def test_read_places_cells_by_name_with_palette_and_flip():
    cells = [bytes(32), _cell(1), bytes([0x12, 0x34] + [0] * 30)]
    names = [0, 1, 0x1001, 0x0402, 0, 0, 0, 0]                 # cell 1 with palette 0 and 1; cell 2 flipped
    data = _file(names, cells)
    [texture] = texture_formats.read("tilemap", data, _params())
    assert texture.image.size == (32, 16) and texture.pixel_format == "4bpp tile map"
    pixel = texture.image.getpixel
    assert pixel((0, 0)) == (0, 0, 0, 0)                         # name 0 = cell 0, all transparent
    assert pixel((8, 0)) == pixel((15, 7)) == (8, 0, 8, 255)      # cell 1, colour 1 of palette 0
    assert pixel((16, 0)) == (140, 66, 140, 255)                 # the same cell with palette 1
    assert pixel((31, 0)) == (8, 0, 8, 255) and pixel((24, 0)) == (0, 0, 0, 0)   # cell 2 flipped: 1 2 3 4 0... mirrored
    assert texture_formats.write("tilemap", data, {0: texture.image}, _params()) == data


def test_write_reuses_redraws_in_place_takes_a_free_cell_and_grows():
    cells = [bytes(32), _cell(1), _cell(2), _cell(3)]
    names = [2, 1, 1, 0, 0, 0, 0, 0]                           # cell 2 once, cell 1 twice, cell 3 unused
    data = _file(names, cells)
    params = _params(max_tiles=6)
    [texture] = texture_formats.read("tilemap", data, params)
    colour = lambda i: texture_formats.read("tilemap", _file([1] + [0] * 7, [bytes(32), _cell(i)]), params)[0].image.getpixel((0, 0))  # noqa: E731
    image = texture.image.copy()
    image.paste(colour(4), (0, 0, 8, 8))                      # entry 0 (cell 2, used once) -> redrawn in place
    image.paste(colour(5), (8, 0, 16, 8))                     # entry 1 (cell 1, shared) -> the free cell 3
    image.paste(colour(4), (24, 0, 32, 8))                    # entry 3 (blank) -> the same pixels as cell 2 now: reused
    image.paste(colour(6), (0, 8, 8, 16))                     # entry 4 (blank) -> a new cell: the bank grows
    out = texture_formats.write("tilemap", data, {0: image}, params)
    new_names = struct.unpack_from(">8H", out)
    assert new_names[0] & 0x3FF == 2 and out[16 + 2 * 32:16 + 3 * 32] == _cell(4)
    assert new_names[1] & 0x3FF == 3 and out[16 + 3 * 32:16 + 4 * 32] == _cell(5)
    assert new_names[2] == 1 and out[16 + 32:16 + 64] == _cell(1)   # the other user of cell 1 keeps it
    assert new_names[3] & 0x3FF == 2
    assert new_names[4] & 0x3FF == 4 and len(out) == 16 + 5 * 32 and out[-32:] == _cell(6)
    assert texture_formats.read("tilemap", out, params)[0].image.tobytes() == image.tobytes()
    image.paste((0, 0, 0, 0), (0, 0, 8, 8))                   # a transparent block becomes the blank name
    assert struct.unpack_from(">H", texture_formats.write("tilemap", out, {0: image}, params))[0] == 0


def test_write_refuses_when_the_bank_is_full_and_checks_the_size():
    data = _file([1, 1, 0, 0, 0, 0, 0, 0], [bytes(32), _cell(1)])
    [texture] = texture_formats.read("tilemap", data, _params())
    image = texture.image.copy()
    image.paste((255, 255, 255, 255), (0, 0, 8, 8))
    with pytest.raises(ValueError, match="No room"):
        texture_formats.write("tilemap", data, {0: image}, _params())
    with pytest.raises(ValueError, match="32x16"):
        texture_formats.write("tilemap", data, {0: Image.new("RGBA", (8, 8))}, _params())


def test_several_screens_share_one_bank_and_8bpp_names_count_in_32_byte_units():
    cell = bytes(range(64))
    data = struct.pack(">4H", 0, 2, 2, 0) + bytes(64) + cell
    params = {"bpp": 8, "unit": 32, "name_mask": "0xfff", "cells_offset": 8, "cols": 2, "rows": 1,
              "textures": [{"name": "a", "map_offset": 0}, {"name": "b", "map_offset": 4}]}
    first, second = texture_formats.read("tilemap", data, params)
    assert (first.name, second.name) == ("a", "b") and first.image.getpixel((9, 1)) == (9, 9, 9, 255)
    assert second.image.getpixel((0, 0)) == first.image.getpixel((8, 0))
    assert texture_formats.write("tilemap", data, {0: first.image, 1: second.image}, params) == data
