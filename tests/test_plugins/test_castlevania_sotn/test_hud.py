"""The Richter hearts digits of the prologue preview: the cmpgfx codec, the CLUT and the digit placement.

Synthetic streams and sheets only: the disc files are never part of the tests.
"""
import struct

import pytest
from PIL import Image

from plugins.castlevania_sotn import hud


def _stream(nibbles):
    """A cmpgfx stream: 8 dictionary bytes, then the nibbles (first nibble of each byte is the high half)."""
    if len(nibbles) % 2:
        nibbles = nibbles + [0]
    body = bytes((nibbles[i] << 4) | nibbles[i + 1] for i in range(0, len(nibbles), 2))
    return bytes(8) + body


def test_a_literal_and_a_double_nibble_and_the_end_opcode_decode_low_nibble_first():
    # op 1 writes 5; op 2 writes 7 twice: bytes 0x75 (5 low, 7 high) and 0x07; 15 ends the stream
    assert hud.inflate(_stream([1, 5, 2, 7, 15])) == b"\x75\x07"


def test_a_zero_run_writes_its_count_plus_three_zero_nibbles():
    # op 6 with 1 writes 4 zero nibbles, which is two zero bytes
    assert hud.inflate(_stream([6, 1, 15])) == b"\x00\x00"


def test_a_stream_that_ends_before_its_end_opcode_is_rejected():
    with pytest.raises(ValueError):
        hud.inflate(_stream([1, 5]))


def test_a_clut_entry_zero_is_transparent_and_5_bit_colours_expand_to_8_bit():
    data = bytearray(32)
    struct.pack_into("<H", data, 2, 0x7FFF)        # index 1: white
    struct.pack_into("<H", data, 0, 0x7FFF)        # index 0 is transparent whatever its value
    colours = hud.clut_rgba(bytes(data), 0)
    assert colours[0][3] == 0
    assert colours[1] == (255, 255, 255, 255)
    assert colours[2] == (0, 0, 0, 255)


def _synthetic_sheet_bytes() -> bytes:
    """A stream that decodes to a 128 x 128 4bpp sheet of index 0 (16384 zero nibbles, 0x2000 bytes)."""
    nibbles = []
    remaining = 128 * 128
    while remaining > 0:
        count = min(remaining, 0x112)            # op 0: amount = (n1 << 4) + n2 + 0x13, up to 0x112
        amount = count - 0x13
        nibbles += [0, amount >> 4, amount & 15]
        remaining -= count
    return _stream(nibbles + [15])


def test_the_sheet_is_read_at_the_stage_offset_with_the_palette_of_the_bank():
    st0 = bytes(hud.RICHTER_HUD_OFFSET) + _synthetic_sheet_bytes()
    game2 = bytearray(hud.HUD_CLUT_OFFSET + 32)
    struct.pack_into("<H", game2, hud.HUD_CLUT_OFFSET + 2 * 15, 0x7FFF)
    sheet = hud.richter_hud_sheet(st0, bytes(game2))
    assert sheet.size == (128, 128)
    assert sheet.getpixel((0, 0))[3] == 0
    assert sheet.getpixel((127, 127))[3] == 0


def _digit_sheet() -> Image.Image:
    """Cell d (digit d, row 96) filled with the colour (20 d + 1, 0, 0)."""
    sheet = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    for digit in range(10):
        sheet.paste((20 * digit + 1, 0, 0, 255), (digit * 8, 96, digit * 8 + 8, 104))
    return sheet


def test_the_hearts_digits_are_drawn_at_the_fitted_cells_tens_first():
    frame = hud.draw_hearts(Image.new("RGBA", (256, 240), (0, 0, 0, 0)), _digit_sheet(), 30)
    assert frame.getpixel((14, 8)) == (61, 0, 0, 255)      # tens digit 3
    assert frame.getpixel((22, 8)) == (1, 0, 0, 255)       # ones digit 0
    assert frame.getpixel((40, 8)) == (0, 0, 0, 0)         # nothing else is drawn


def test_the_hearts_value_is_clamped_to_two_digits():
    frame = hud.draw_hearts(Image.new("RGBA", (256, 240), (0, 0, 0, 0)), _digit_sheet(), 250)
    assert frame.getpixel((14, 8)) == (181, 0, 0, 255)     # tens digit 9
    assert frame.getpixel((22, 8)) == (181, 0, 0, 255)


def test_a_missing_stage_file_gives_no_sheet(tmp_path):
    assert hud.read_richter_hud(str(tmp_path / "ST0.BIN"), str(tmp_path / "F_GAME2.BIN.pic")) is None
