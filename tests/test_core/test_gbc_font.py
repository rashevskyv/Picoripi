"""The Game Boy Color Oracles font backend: an unedited model packs back to the same ROM bytes, and an edited
glyph changes only its own 16 bytes. The real ROM check is skipped where the ROM is not on this machine."""

import pytest

import romhacking_root
from PIL import Image

from core.font_formats import gbc_font
from core.font_formats import extract as font_extract, pack as font_pack

OFFSET = 0x4000
PARAMS = {"font_offset": OFFSET}


def _rom(seed=7):
    data = bytearray((i * 31 + seed) & 0xFF for i in range(0x20000))
    return bytes(data)


def test_unedited_model_packs_back_to_the_same_bytes():
    rom = _rom()
    metadata, sheets = font_extract("gbc_font", rom, PARAMS)
    assert metadata["header"]["format"] == "gbc_font"
    assert sheets[0].size == (gbc_font.IMAGE_W, gbc_font.IMAGE_H)
    assert font_pack("gbc_font", metadata, sheets, rom, PARAMS) == rom


def test_edited_glyph_changes_only_its_sixteen_bytes():
    rom = _rom()
    metadata, sheets = font_extract("gbc_font", rom, PARAMS)
    cell = 0x41  # 'A'
    x0, y0 = (cell % gbc_font.COLUMNS) * gbc_font.CELL_W, (cell // gbc_font.COLUMNS) * gbc_font.CELL_H
    image = sheets[0].copy()
    pixels = image.load()
    for y in range(y0, y0 + gbc_font.CELL_H):
        for x in range(x0, x0 + gbc_font.CELL_W):
            pixels[x, y] = (0, 0, 0, 0)  # clear: no ink
    packed = font_pack("gbc_font", metadata, [image], rom, PARAMS)
    changed = [i for i in range(len(rom)) if rom[i] != packed[i]]
    assert changed and all(OFFSET + cell * 16 <= i < OFFSET + cell * 16 + 16 for i in changed)
    assert packed[OFFSET + cell * 16:OFFSET + cell * 16 + 16] == bytes(16)  # no ink: every bit 0


def test_glyph_bits_read_as_ink_per_pixel():
    rom = bytearray(_rom(seed=0))
    rom[OFFSET:OFFSET + 16] = bytes([0x80] + [0] * 7 + [0x01] + [0] * 7)
    metadata, sheets = font_extract("gbc_font", bytes(rom), PARAMS)
    pixels = sheets[0].convert("RGBA").load()
    assert pixels[0, 0][0] >= 128       # bit 7 of row 0 is the left pixel of cell 0
    assert pixels[7, 8][0] >= 128       # bit 0 of row 8 is the right pixel of the bottom tile
    assert pixels[1, 0][0] < 128


def test_missing_offset_is_refused():
    with pytest.raises(ValueError):
        font_extract("gbc_font", _rom(), {})


def test_real_usa_rom_round_trips_when_present():
    path = romhacking_root.under("Zelda/Oracles/Ages/ISO/Legend of Zelda,The-Oracle of Ages.gbc")
    if not path.is_file():
        pytest.skip("the USA Oracle of Ages ROM is not on this machine")
    rom = path.read_bytes()
    params = {"font_offset": 0x70720}
    metadata, sheets = font_extract("gbc_font", rom, params)
    assert font_pack("gbc_font", metadata, sheets, rom, params) == rom
    assert isinstance(sheets[0], Image.Image)
