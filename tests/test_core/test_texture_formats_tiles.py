"""GBA / DS character tiles (``tiles``): NCGR sheets and headerless sprite cells, shown as grey indices."""
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


def test_paint_outside_the_tiles_is_refused_not_lost():
    data = bytes(32 * 6)                                              # 6 tiles on rows of 4: the last 2 cells empty
    [texture] = tiles.read(data, {"per_row": 4})
    assert texture.image.size == (32, 16)
    image = texture.image.copy()
    image.putpixel((30, 12), (255, 255, 255, 255))
    with pytest.raises(ValueError):
        tiles.write(data, {0: image}, {"per_row": 4})
