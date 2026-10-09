"""TIM2 pictures (PS2 / PSP) on small files made here: 4-bit and 8-bit with CLUT, embedded, edit, round trip."""
import struct

from PIL import Image

from core import texture_formats
from core.font_formats import texture_grid


def _tim2(width, height, bits, clut_type, pixels, colours):
    image = bytes(pixels)
    clut = b"".join(bytes(c) for c in colours)
    head = struct.pack("<IIIHHBBBBHH", 48 + len(image) + len(clut), len(clut), len(image), 48, len(colours), 0, 1,
                       clut_type, 4 if bits == 4 else 5, width, height) + bytes(24)
    return b"TIM2" + bytes([4, 0]) + struct.pack("<H", 1) + bytes(8) + head + image + clut


PAL16 = [(i * 16, 0, 0, 255) for i in range(16)]


def test_4bit_reads_writes_and_keeps_bytes():
    data = _tim2(4, 2, 4, 0x03, [0x10, 0x32, 0x54, 0x76], PAL16)
    tex = texture_formats.read("tim2", data)
    assert len(tex) == 1 and tex[0].image.size == (4, 2) and tex[0].pixel_format == "TIM2 4-bit"
    assert tex[0].image.getpixel((1, 0)) == (16, 0, 0, 255)
    assert texture_formats.write("tim2", data, {0: tex[0].image}) == data
    image = tex[0].image.copy()
    image.putpixel((0, 0), (240, 0, 0, 255))
    out = texture_formats.write("tim2", data, {0: image})
    assert texture_formats.read("tim2", out)[0].image.getpixel((0, 0)) == (240, 0, 0, 255)
    assert out[-64:] == data[-64:] and out[-65:-64] == data[-65:-64]     # the CLUT and other pixels stay


def test_8bit_csm1_clut_order_and_ps2_alpha():
    colours = [(i, i, i, 0x80) for i in range(256)]
    data = _tim2(2, 1, 8, 0x03, [8, 16], colours)           # CSM1: entries 8-15 and 16-23 swap places
    image = texture_formats.read("tim2", data)[0].image
    assert image.getpixel((0, 0)) == (16, 16, 16, 255) and image.getpixel((1, 0)) == (8, 8, 8, 255)
    assert texture_formats.write("tim2", data, {0: image}) == data


def test_tim2_inside_another_file():
    tim = _tim2(4, 2, 4, 0x83, [0] * 4, PAL16)
    data = b"MSTR1.00" + bytes(24) + tim + b"tail" + tim
    assert len(texture_formats.read("tim2", data)) == 2


def test_texture_grid_skips_cells_without_a_character():
    sheet = Image.new("RGBA", (16, 8))
    raw = _tim2(16, 8, 4, 0x03, [0] * 64, PAL16)
    metadata, sheets = texture_grid.extract(raw, {"texture": "tim2", "cell": [8, 8], "chars": "A\0"})
    assert metadata["MAP1"][0]["entries"] == [ord("A"), 0]
    assert sheets[0].size == sheet.size
