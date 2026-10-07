"""PSP GIM pictures and FCHN packs of them (core/texture_formats/gim.py), on files made here."""
import struct

from PIL import Image

from core import texture_formats
from core.texture_formats import gim


def _swizzle(plane: bytes, pitch: int, rows: int) -> bytes:
    out = bytearray()
    for by in range(rows // 8):
        for bx in range(pitch // 16):
            for y in range(8):
                at = (by * 8 + y) * pitch + bx * 16
                out += plane[at:at + 16]
    return bytes(out)


def _block(kind: int, fmt: int, order: int, width: int, height: int, bpp: int, pixels: bytes) -> bytes:
    head = struct.pack("<HHHHHHHHHHHHIIIIHHHH", 0x30, 0, fmt, order, width, height, bpp, 16, 8 if order else 1, 2,
                       0, 0, 0x30, 0x40, 0x40 + len(pixels), 0, 1, 1, 3, 1)
    data = head + struct.pack("<I", 0x40).ljust(0x10, b"\0") + pixels
    return struct.pack("<HHIII", kind, 0, 16 + len(data), 16 + len(data), 16) + data


def _gim(fmt: int, order: int, width: int, height: int, plane: bytes, palette: bytes = b"") -> bytes:
    bpp = {0: 16, 1: 16, 2: 16, 3: 32, 4: 4, 5: 8}[fmt]
    pitch = -(-width * bpp // 8 // 16) * 16
    rows = -(-height // 8) * 8 if order else height
    pixels = _swizzle(plane, pitch, rows) if order else plane
    blocks = _block(4, fmt, order, width, height, bpp, pixels)
    if palette:
        blocks += _block(5, 3, 0, len(palette) // 4, 1, 32, palette)
    picture = struct.pack("<HHIII", 3, 0, 16 + len(blocks), 16, 16) + blocks
    root = struct.pack("<HHIII", 2, 0, 16 + len(picture), 16, 16) + picture
    return gim.MAGIC + b"\0" * 4 + root


def _index8(width=20, height=10):
    plane = bytearray(32 * 16)
    for y in range(height):
        for x in range(width):
            plane[y * 32 + x] = (x + y) % 3
    palette = bytes([255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 128]) + bytes(4 * 253)
    return _gim(5, 1, width, height, bytes(plane), palette)


def test_index8_swizzled_reads_and_writes_back():
    data = _index8()
    assert texture_formats.detect(data) == "gim"
    [texture] = texture_formats.read("gim", data)
    assert texture.image.size == (20, 10) and texture.pixel_format == "I8"
    assert texture.image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert texture.image.getpixel((1, 0)) == (0, 255, 0, 255)
    assert texture.image.getpixel((2, 9)) == (0, 0, 255, 128)      # index (2 + 9) % 3 == 2
    assert texture_formats.write("gim", data, {0: texture.image}) == data


def test_index8_edit_with_palette_colour_changes_only_those_pixels():
    data = _index8()
    image = texture_formats.read("gim", data)[0].image.copy()
    image.putpixel((5, 5), (0, 0, 255, 128))
    new = texture_formats.write("gim", data, {0: image})
    assert len(new) == len(data) and sum(a != b for a, b in zip(new, data)) == 1
    assert texture_formats.read("gim", new)[0].image.getpixel((5, 5)) == (0, 0, 255, 128)


def test_index8_new_colour_makes_a_new_palette():
    data = _index8()
    image = texture_formats.read("gim", data)[0].image.copy()
    image.putpixel((0, 0), (10, 20, 30, 255))
    back = texture_formats.read("gim", texture_formats.write("gim", data, {0: image}))[0].image
    assert back.getpixel((0, 0)) == (10, 20, 30, 255)
    assert back.getpixel((1, 0)) == (0, 255, 0, 255)


def test_index4_low_nibble_first():
    plane = bytes([0x10, 0x32]) + bytes(14)
    data = _gim(4, 0, 4, 1, plane, bytes([0, 0, 0, 0, 255, 255, 255, 255, 255, 0, 0, 255, 0, 255, 0, 255]) + bytes(48))
    image = texture_formats.read("gim", data)[0].image
    assert [image.getpixel((x, 0)) for x in range(4)] == [(0, 0, 0, 0), (255, 255, 255, 255), (255, 0, 0, 255),
                                                          (0, 255, 0, 255)]
    edited = image.copy()
    edited.putpixel((0, 0), (0, 255, 0, 255))
    new = texture_formats.write("gim", data, {0: edited})
    assert bytes([0x13, 0x32]) in new
    assert texture_formats.read("gim", new)[0].image.getpixel((0, 0)) == (0, 255, 0, 255)


def test_direct_formats_round_trip():
    rgba = bytes(range(64))                     # 4x4 RGBA8888
    data = _gim(3, 1, 4, 4, rgba + bytes(64))   # 16-byte pitch, 8 rows
    image = texture_formats.read("gim", data)[0].image
    assert image.getpixel((0, 0)) == (0, 1, 2, 3)
    assert texture_formats.write("gim", data, {0: image}) == data
    value = 0x1F | (1 << 15)                    # RGBA5551: red, opaque
    data = _gim(1, 0, 8, 1, struct.pack("<8H", *[value] * 8))
    image = texture_formats.read("gim", data)[0].image
    assert image.getpixel((7, 0)) == (255, 0, 0, 255)
    image.putpixel((0, 0), (0, 0, 255, 0))
    back = texture_formats.read("gim", texture_formats.write("gim", data, {0: image}))[0].image
    assert back.getpixel((0, 0)) == (0, 0, 255, 0) and back.getpixel((1, 0)) == (255, 0, 0, 255)


def test_fchn_pack_lists_its_pictures():
    first, second = _index8(), _index8(8, 8)
    count = 3
    start = 8 + 8 * count
    entries = [(len(first), 0), (0, len(first)), (len(second), len(first))]
    pack = b"FCHN" + struct.pack("<HH", start, count) + b"".join(struct.pack("<II", *e) for e in entries)
    pack += first + second
    textures = texture_formats.read("gim", pack)
    assert [t.name for t in textures] == ["0", "2"] and textures[1].image.size == (8, 8)
    edited = textures[1].image.copy()
    edited.putpixel((0, 0), (0, 0, 255, 128))
    new = texture_formats.write("gim", pack, {1: edited})
    assert new[:start + len(first)] == pack[:start + len(first)]
    assert texture_formats.read("gim", new)[1].image.getpixel((0, 0)) == (0, 0, 255, 128)
    assert Image.Image.tobytes(texture_formats.read("gim", new)[0].image) == textures[0].image.tobytes()
