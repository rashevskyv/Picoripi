"""zelda_bmg's layout-preview decoders use the shared GX codecs: 4x4 tiles for 16-bit formats, C14X2,
and the BTI palette format read from the byte at 0x09."""
import struct

from PIL import Image

from core.texture_formats import pixels
from plugins.zelda_bmg.bti_image import bti_to_qimage
from plugins.zelda_bmg.gx_texture import decode_gx


def _colour(image, x, y):
    c = image.pixelColor(x, y)
    return c.red(), c.green(), c.blue(), c.alpha()


def _quadrants(width=8, height=8):
    """Four colours, one per 4x4 tile: a decoder with the wrong tile size scrambles them."""
    image = Image.new("RGBA", (width, height))
    for (x, y), colour in zip(((0, 0), (4, 0), (0, 4), (4, 4)),
                              ((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 255, 255))):
        image.paste(colour, (x, y, x + 4, y + 4))
    return image


def test_16_bit_formats_use_4x4_tiles():
    for fmt, name in ((3, "gx:IA8"), (4, "gx:RGB565"), (5, "gx:RGB5A3")):
        source = _quadrants()
        expected = pixels.codec(name).decode(pixels.codec(name).encode(source), 8, 8)
        image = decode_gx(pixels.codec(name).encode(source), 8, 8, fmt)
        for x, y in ((1, 1), (5, 1), (1, 5), (6, 6)):
            assert _colour(image, x, y) == expected.getpixel((x, y)), (name, x, y)


def test_c14x2_reads_its_palette():
    palette = struct.pack(">3H", 0x8000, 0xFC00, 0x83E0)          # RGB5A3: black, red, green
    indices = struct.pack(">16H", *([1] * 8 + [2] * 8))
    image = decode_gx(indices, 4, 4, 10, palette, 2)
    assert _colour(image, 0, 0) == (255, 0, 0, 255) and _colour(image, 0, 3) == (0, 255, 0, 255)


def test_bti_palette_format_is_the_byte_at_0x09():
    palette = struct.pack(">2H", 0xFF80, 0x8000)                    # IA8 entry (A=0xFF, I=0x80) would be wrong here
    head = struct.pack(">BBHHBBBBHI", 9, 0, 8, 4, 0, 0, 1, 2, 2, 0x20) + bytes(8) + bytes([1, 0, 0, 0])
    head += struct.pack(">I", 0x24)
    data = head + palette + bytes(32)                               # every texel uses entry 0
    image = bti_to_qimage(data)
    assert _colour(image, 0, 0) == pixels.gx_palette_format(2)[0](0xFF80)


def test_cut_short_data_decodes_as_transparent():
    image = decode_gx(bytes([0x80] * 8), 8, 4, 1)
    assert _colour(image, 0, 0)[3] == 128 and _colour(image, 7, 3)[3] == 0
