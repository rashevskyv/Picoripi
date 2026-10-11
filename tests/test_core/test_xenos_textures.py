"""Xbox 360 (Xenos) tiled pictures: synthetic files, no game data needed."""
import random
import struct

import pytest
from PIL import Image

from core.texture_formats import read, write
from core.texture_formats import xenos


def _tiled_file(width: int, height: int, bpt: int, body: bytes, flag: int, palette: bytes = b"") -> bytes:
    size = xenos._align(xenos._align(width, 32) * xenos._align(height, 32) * bpt, 4096)
    head = struct.pack(">4I", width, height, flag, size) + bytes(0x20 - 16)
    data = bytearray(head + palette)
    data += bytes(body[:size]).ljust(size, b"\0")
    return bytes(data)


def test_tiled_offsets_are_unique_and_fill_the_surface():
    for bpt in (1, 4):
        width = height = 64
        offsets = [xenos.tiled_offset(x, y, 64, bpt) for y in range(height) for x in range(width)]
        assert len(set(offsets)) == width * height
        assert max(offsets) < width * height * bpt


def test_palette_picture_unchanged_writes_same_bytes():
    rng = random.Random(1)
    palette = bytes(rng.randrange(256) for _ in range(4 * 256))
    body = bytes(rng.randrange(256) for _ in range(4096))
    data = _tiled_file(40, 20, 1, body, 0x400, palette)
    image = read("xenos", data, {"name": "t"})[0].image
    assert image.size == (40, 20)
    assert write("xenos", data, {0: image}) == data


def test_argb_picture_unchanged_writes_same_bytes():
    rng = random.Random(2)
    body = bytes(rng.randrange(256) for _ in range(32 * 32 * 4))
    data = _tiled_file(20, 10, 4, body, 0)
    image = read("xenos", data, {})[0].image
    assert write("xenos", data, {0: image}) == data


def test_palette_index_zero_is_transparent():
    palette = bytes(b for _ in range(256) for b in (0xFF, 0x10, 0x20, 0x30))
    data = _tiled_file(8, 8, 1, bytes(64), 0x400, palette)
    image = read("xenos", data, {})[0].image
    assert image.getpixel((0, 0))[3] == 0


def test_one_edited_palette_texel_changes_one_byte():
    rng = random.Random(3)
    palette = bytes([0xFF, 0, 0, 0]) + bytes(rng.randrange(256) for _ in range(4 * 255))
    body = bytes(rng.randrange(6, 256) for _ in range(4096))      # no index 0..5 anywhere
    data = _tiled_file(40, 20, 1, body, 0x400, palette)
    image = read("xenos", data, {})[0].image.copy()
    a, r, g, b = palette[4 * 5:4 * 5 + 4]
    image.putpixel((13, 9), (r, g, b, a))
    out = write("xenos", data, {0: image})
    at = xenos.PALETTE_DATA + xenos.tiled_offset(13, 9, 64, 1)
    assert out[at] == 5
    changed = [i for i in range(len(data)) if data[i] != out[i]]
    assert changed == [at]


def test_argb_edited_texel_changes_four_bytes():
    body = bytes([1]) * 4096
    data = _tiled_file(16, 16, 4, body, 0)
    image = read("xenos", data, {})[0].image.copy()
    image.putpixel((3, 5), (10, 20, 30, 40))
    out = write("xenos", data, {0: image})
    base = xenos.HEADER + xenos.tiled_offset(3, 5, 32, 4)
    assert out[base:base + 4] == bytes((40, 10, 20, 30))
    changed = [i for i in range(len(data)) if data[i] != out[i]]
    assert changed and all(base <= i < base + 4 for i in changed)


def test_bad_headers_are_refused():
    with pytest.raises(ValueError):
        read("xenos", b"\0" * 8, {})
    bad = struct.pack(">4I", 16, 16, 0x123, 4096) + bytes(0x10)
    with pytest.raises(ValueError):
        read("xenos", bad + bytes(4096), {})
    wrong_size = struct.pack(">4I", 16, 16, 0, 8192) + bytes(0x10)
    with pytest.raises(ValueError):
        read("xenos", wrong_size + bytes(8192), {})


def test_image_is_rgba_of_header_size():
    data = _tiled_file(7, 3, 4, bytes(4096), 0)
    image = read("xenos", data, {})[0].image
    assert image.size == (7, 3) and image.mode == "RGBA"
    assert isinstance(image, Image.Image)
