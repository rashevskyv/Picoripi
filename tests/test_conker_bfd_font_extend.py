"""Ukrainian placeholder cells: one per letter, copied from a base glyph, and every record encodes back unchanged.

Synthetic glyphs only (the test builds a small font with made-up pixels)."""
from plugins.conker_bfd import font, font_extend as fe


def _glyph(index, width, height, value):
    pixels = bytes([value & 0xF0]) * (width * height)
    return font.Glyph(index=index, width=width, height=height, meta=b"\x00\x00", pixels=pixels,
                      rle=font.encode_rle(width, height, pixels))


def _font():
    codes = bytes(range(0x20, 0x7F))            # 95 printable ASCII codes, the glyph map
    glyphs = [_glyph(i, 4, 6, (i * 16) & 0xF0) for i in range(len(codes))]
    return glyphs, codes


def test_every_ukrainian_letter_gets_one_placeholder_from_its_base():
    glyphs, codes = _font()
    cells = fe.plan_cells(glyphs, codes)
    assert [c.letter for c in cells] == [letter for letter, _ in fe.UKRAINIAN_CELLS]
    for cell in cells:
        base_index = codes.index(ord(cell.base))
        assert cell.glyph.pixels == glyphs[base_index].pixels
        assert (cell.glyph.width, cell.glyph.height) == (4, 6)


def test_placeholder_records_encode_and_decode_unchanged():
    glyphs, codes = _font()
    cells = fe.plan_cells(glyphs, codes)
    table = fe.encode_cells(cells)
    back = font.parse_table(table + b"", 0, len(table), count=len(cells))
    assert [g.pixels for g in back] == [c.glyph.pixels for c in cells]


def test_a_base_glyph_missing_from_the_map_is_refused():
    glyphs, codes = _font()
    bad_map = codes.replace(b"F", b"#")
    try:
        fe.plan_cells(glyphs, bad_map)
    except ValueError:
        return
    raise AssertionError("a missing base glyph must be refused")
