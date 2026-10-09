"""GBA / DS character tiles (``tiles``): NCGR sheets, headerless sprite cells, game palettes or grey indices."""
import struct

import pytest

from PIL import Image

from core import texture_formats
from core.texture_formats import pixels, tiles


def _ncgr(tiles_x: int, tiles_y: int, data: bytes, depth: int = 3) -> bytes:
    rahc = struct.pack("<HHIIIII", tiles_y, tiles_x, depth, 0, 0, len(data), 0x18) + data
    rahc = b"RAHC" + struct.pack("<I", 8 + len(rahc)) + rahc
    return b"RGCN" + struct.pack("<HHIHH", 0xFEFF, 0x0101, 16 + len(rahc), 16, 1) + rahc


def test_grey_index_codec_round_trips_every_index():
    for name, top in (("nds:4bpp", 15), ("nds:8bpp", 255)):
        codec = pixels.codec(name)
        raw = bytes(range(codec.size)) if top == 255 else bytes((i * 37) & 0xFF for i in range(codec.size))
        assert codec.encode(codec.decode(raw, 8, 8)) == raw
    assert pixels.codec("nds:4bpp").decode(b"\x10" + bytes(31), 8, 8).getpixel((0, 0)) == (0, 0, 0, 0)
    assert pixels.codec("nds:4bpp").decode(b"\x10" + bytes(31), 8, 8).getpixel((1, 0)) == (17, 17, 17, 255)


def test_ncgr_sheet_takes_its_size_from_the_header_and_writes_only_redrawn_tiles():
    data = _ncgr(4, 2, bytes((i * 7) & 0xFF for i in range(8 * 32)))
    assert texture_formats.detect(data) == "tiles"
    [texture] = texture_formats.read("tiles", data)
    assert texture.image.size == (32, 16) and texture.pixel_format == "4bpp tiles"
    assert texture_formats.write("tiles", data, {0: texture.image}) == data
    image = texture.image.copy()
    image.paste((255, 255, 255, 255), (8, 8, 16, 16))               # tile 5 (second row, second column)
    out = texture_formats.write("tiles", data, {0: image})
    changed = [i for i in range(8) if out[0x30 + 32 * i:0x30 + 32 * i + 32] != data[0x30 + 32 * i:0x30 + 32 * i + 32]]
    assert changed == [5] and out[0x30 + 32 * 5:0x30 + 32 * 6] == b"\xff" * 32


def test_headerless_sprite_cells_are_laid_out_side_by_side():
    data = bytes(range(256)) * 2                                      # 16 tiles of 4bpp
    params = {"cell": [2, 2], "per_row": 4}
    [texture] = tiles.read(data, params)
    assert texture.image.size == (64, 16)
    # cell 0 is tiles 0-3 (2x2), cell 1 starts with tile 4 at x 16; tile 3 is the bottom right of cell 0
    codec = pixels.codec("nds:4bpp")
    assert texture.image.crop((16, 0, 24, 8)).tobytes() == codec.decode(data[128:160], 8, 8).tobytes()
    assert texture.image.crop((8, 8, 16, 16)).tobytes() == codec.decode(data[96:128], 8, 8).tobytes()
    assert tiles.write(data, {0: texture.image}, params) == data
    image = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    blank = tiles.write(data, {0: image}, params)
    assert blank == bytes(512)


def _palette(*colours) -> str:
    return b"".join(struct.pack("<H", r >> 3 | (g >> 3) << 5 | (b >> 3) << 10) for r, g, b in colours).hex()


def test_palette_banks_colour_each_tile_and_import_keeps_indices():
    # bank 0: (unused), red, red again, white; bank 1: (unused), green, blue, white
    palette = _palette((0, 0, 0), (248, 0, 0), (248, 0, 0), (248, 248, 248), *[(0, 0, 0)] * 12,
                       (0, 0, 0), (0, 248, 0), (0, 0, 248), (248, 248, 248), *[(0, 0, 0)] * 12)
    data = bytes([0x21]) + bytes(31) + bytes([0x21]) + bytes(31)      # each tile: pixel 0 index 1, pixel 1 index 2
    params = {"palette": palette, "bank": 0, "banks": ".1"}
    [texture] = tiles.read(data, params)
    image = texture.image
    assert image.getpixel((0, 0)) == (255, 0, 0, 255) and image.getpixel((1, 0)) == (255, 0, 0, 255)
    assert image.getpixel((8, 0)) == (0, 255, 0, 255) and image.getpixel((9, 0)) == (0, 0, 255, 255)
    assert image.getpixel((2, 0)) == (0, 0, 0, 0)                     # index 0 is transparent
    assert tiles.write(data, {0: image}, params) == data              # index 2 stays 2 though it is red like 1
    image = image.copy()
    image.putpixel((2, 0), (250, 240, 235, 255))                      # off the palette: the nearest colour (white)
    image.putpixel((8, 0), (0, 0, 255, 255))                          # blue in bank 1 = index 2
    out = tiles.write(data, {0: image}, params)
    assert out[1] == 0x03 and out[32] == 0x22
    assert tiles.read(out, params)[0].image.getpixel((2, 0)) == (255, 255, 255, 255)


def test_paint_outside_the_tiles_is_refused_not_lost():
    data = bytes(32 * 6)                                              # 6 tiles on rows of 4: the last 2 cells empty
    [texture] = tiles.read(data, {"per_row": 4})
    assert texture.image.size == (32, 16)
    image = texture.image.copy()
    image.putpixel((30, 12), (255, 255, 255, 255))
    with pytest.raises(ValueError):
        tiles.write(data, {0: image}, {"per_row": 4})


def test_saturn_high_nibble_and_one_bit_tiles_read_and_write_back():
    raw = bytes((0x12, 0x30) + (0,) * 30)
    [texture] = texture_formats.read("tiles", raw, {"bpp": 4, "nibble": "high", "per_row": 1})
    image = texture.image
    assert image.getpixel((0, 0))[:3] == (17, 17, 17) and image.getpixel((1, 0))[:3] == (34, 34, 34)
    assert image.getpixel((2, 0))[:3] == (51, 51, 51) and image.getpixel((3, 0))[3] == 0
    assert texture_formats.write("tiles", raw, {0: image}, {"bpp": 4, "nibble": "high", "per_row": 1}) == raw
    glyph = bytes((0x80, 0x01) + (0,) * 14)                        # 8x16 cell = two 1 bpp tiles
    params = {"bpp": 1, "cell": [1, 2], "per_row": 1}
    [texture] = texture_formats.read("tiles", glyph, params)
    assert texture.image.size == (8, 16)
    assert texture.image.getpixel((0, 0))[3] == 255 and texture.image.getpixel((7, 1))[3] == 255
    assert texture.image.getpixel((1, 0))[3] == 0
    edited = texture.image.copy()
    edited.putpixel((3, 9), (255, 255, 255, 255))
    out = texture_formats.write("tiles", glyph, {0: edited}, params)
    assert out[9] == 0x10 and out[:2] == glyph[:2]
