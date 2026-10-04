"""Wii GX font sheets (BRFNT, ``core.font_formats.bcfnt``): I4 / I8 / IA4 / IA8 tiles decode and encode back."""
import random

import pytest

from core.font_formats import bcfnt


@pytest.mark.parametrize("fmt, bits", [(bcfnt.RVL_I4, 4), (bcfnt.RVL_I8, 8), (bcfnt.RVL_IA4, 8), (bcfnt.RVL_IA8, 16)])
def test_gx_sheets_encode_back_to_the_same_bytes(fmt, bits):
    rng = random.Random(fmt)
    raw = bytes(rng.randrange(256) for _ in range(32 * 16 * bits // 8))
    image = bcfnt.gx_decode(raw, fmt, 32, 16)
    assert bcfnt.gx_encode(image, fmt) == raw


def test_i4_tiles_are_8x8_high_nibble_first():
    raw = bytearray(32 * 8 // 2)
    raw[0] = 0xF0                      # texel (0, 0) full, (1, 0) empty
    raw[4] = 0x0F                      # second row of the first tile: (1, 1) full
    image = bcfnt.gx_decode(bytes(raw), bcfnt.RVL_I4, 32, 8)
    assert image.getpixel((0, 0))[3] == 255 and image.getpixel((1, 0))[3] == 0 and image.getpixel((1, 1))[3] == 255


def _letter(top, bottom, size=(20, 30)):
    from PIL import Image
    cell = Image.new("RGBA", size)
    cell.paste((255, 255, 255, 255), (4, top, 12, bottom))
    return cell


def test_new_letters_line_up_with_the_fonts_latin_letters():
    from core import font_formats
    cells = {"H": _letter(5, 22), "x": _letter(11, 22), "p": _letter(11, 27)}
    metrics = font_formats.latin_metrics(cells.get)
    assert metrics == {"baseline": 22, "cap_top": 5, "x_top": 11, "descender": 27}
    def box(cell):
        return font_formats.coverage(cell).getbbox()
    assert box(font_formats.align_to_latin(_letter(4, 19), "Б", metrics))[3] == 22        # rests on the baseline
    assert box(font_formats.align_to_latin(_letter(9, 25), "р", metrics))[3] == 27        # hangs like p
    assert box(font_formats.align_to_latin(_letter(13, 26), "д", metrics))[1] == 11       # short tail: by its top
    assert box(font_formats.align_to_latin(_letter(3, 19), "Щ", metrics))[1] == 5
