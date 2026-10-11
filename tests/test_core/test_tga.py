"""Uncompressed TGA reader/writer (core/texture_formats/tga.py): round trip keeps bytes, both row origins."""

from core.texture_formats import tga


def _tga(width, height, depth, top_left, pixels: bytes) -> bytes:
    header = bytearray(18)
    header[2] = 2
    header[12:16] = bytes([width & 0xFF, width >> 8, height & 0xFF, height >> 8])
    header[16] = depth
    header[17] = 0x20 if top_left else 0x00
    return bytes(header) + pixels


def test_unchanged_32bit_round_trip_is_byte_identical():
    width, height = 3, 2
    data = _tga(width, height, 32, True, bytes(range(width * height * 4)))
    image = tga.read(data, {})[0].image
    assert tga.write(data, {0: image}, {}) == data


def test_bottom_left_origin_is_flipped_on_read_and_back_on_write():
    width, height = 1, 2
    # bottom-left file: first stored row is the image bottom (blue row), second stored row is the top (red row)
    data = _tga(width, height, 24, False, bytes([255, 0, 0, 0, 0, 255]))
    image = tga.read(data, {})[0].image
    assert image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert image.getpixel((0, 1)) == (0, 0, 255, 255)
    assert tga.write(data, {0: image}, {}) == data


def test_one_edited_pixel_changes_only_its_bytes():
    width, height = 2, 2
    data = _tga(width, height, 32, True, bytes(width * height * 4))
    image = tga.read(data, {})[0].image.copy()
    image.putpixel((1, 0), (10, 20, 30, 255))
    new = tga.write(data, {0: image}, {})
    changed = [i for i in range(len(data)) if data[i] != new[i]]
    offset = 18 + (0 * width + 1) * 4
    assert changed == [offset, offset + 1, offset + 2, offset + 3]
