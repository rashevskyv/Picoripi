"""The Shift-JIS menu lines of Symphony of the Night: glyph lookup, expansion and the ink advance (synthetic BIOS)."""
from plugins.castlevania_sotn import menu_text


def _bios_with(codes_to_glyphs) -> bytes:
    """A fake BIOS image: each code's glyph placed at its table index. No game data."""
    size = menu_text.BIOS_KROM_OFFSET + 0x200 * menu_text.GLYPH_BYTES
    image = bytearray(size)
    for code, glyph in codes_to_glyphs.items():
        start = menu_text.BIOS_KROM_OFFSET + menu_text.glyph_index(code) * menu_text.GLYPH_BYTES
        image[start:start + menu_text.GLYPH_BYTES] = glyph
    return bytes(image)


def test_the_table_index_follows_the_range_bases():
    assert menu_text.glyph_index(0x8140) == 0            # the space code
    assert menu_text.glyph_index(0x8260) == 0x9D         # full-width capital A
    assert menu_text.glyph_index(0x8281) == 0xB7         # full-width small a
    assert menu_text.glyph_index(0x8540) is None         # outside the ported range (0x8140-0x84BF)


def test_a_glyph_is_read_from_its_table_slot():
    marker = bytes(range(1, 31))
    bios = _bios_with({0x8260: marker})
    assert menu_text.glyph_at(bios, 0x8260) == marker
    assert menu_text.glyph_at(bios, 0x8540) is None


def test_expansion_gives_a_12_by_16_bitmap_and_blank_stays_blank():
    expanded = menu_text.expand(bytes(menu_text.GLYPH_BYTES))
    assert len(expanded) == menu_text.ROW_BYTES * menu_text.ROWS
    assert expanded == bytes(len(expanded))


def test_a_space_advances_three_bytes_which_is_six_pixels():
    strip, used, missing = menu_text.draw_line(b" ", lambda code: bytes(menu_text.GLYPH_BYTES))
    assert (used, missing) == (3, 0)
    assert menu_text.width_px(b" ", lambda code: bytes(menu_text.GLYPH_BYTES)) == 6


def test_a_blank_glyph_still_moves_one_byte_and_is_counted_when_missing():
    strip, used, missing = menu_text.draw_line(b"\x85\x40", lambda code: None)   # a code, not the double space
    assert (used, missing) == (1, 1)


def test_a_full_ink_glyph_is_six_bytes_because_its_last_column_has_high_nibble_ink():
    # All ink: the expanded nibbles are non-zero everywhere, so nothing is trimmed and the high-nibble rule adds one.
    full = b"\xff" * menu_text.GLYPH_BYTES
    strip, used, missing = menu_text.draw_line(b"Ab", lambda code: full)
    assert missing == 0
    assert used == 12
    rows = menu_text.ink_rows(strip, used)
    assert len(rows) == menu_text.ROWS
    assert all(len(row) == 2 * used for row in rows)


def test_the_menu_line_image_is_16_rows_and_the_laid_out_width():
    from plugins.castlevania_sotn.text_preview import menu_line_image

    bios = _bios_with({0x8260: b"\xff" * menu_text.GLYPH_BYTES})
    image, missing = menu_line_image(bios, b"A")
    assert missing == 0
    assert image.size == (312, 32)                               # the info-bar band of the menu panel
