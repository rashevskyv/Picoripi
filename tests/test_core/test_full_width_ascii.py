"""A font that holds Latin only in full width draws ASCII with those glyphs (JUTResFont halftofull)."""
from core import font_formats
from core.bfn_core import char_glyphs


def _metadata(pairs):
    return {"MAP1": [font_formats.map_entries(pairs)],
            "WID1": [{"first_code_included": 0, "packets": [{"kerning": 0, "width": 10 + g} for g in range(4)]}],
            "INF1": [{"width": 32, "encoding": 1}]}


FULL_WIDTH = [(0xFF24, 0), (0xFF41, 1), (0x3000, 2), (0x2019, 3)]   # Ｄ ａ ideographic space ’


def test_ascii_takes_the_full_width_glyph_when_the_font_has_no_ascii_letters():
    glyphs = char_glyphs(_metadata(FULL_WIDTH)["MAP1"], 1)
    assert (glyphs["D"], glyphs["a"], glyphs[" "], glyphs["'"]) == (0, 1, 2, 3)


def test_the_width_map_measures_ascii_with_the_full_width_advance():
    widths = font_formats.font_map(_metadata(FULL_WIDTH))
    assert widths["D"] == {"width": 10}
    assert widths["a"] == {"width": 11}


def test_a_font_with_its_own_ascii_letters_gets_no_aliases():
    glyphs = char_glyphs(_metadata([(0x41, 0), (0xFF24, 1)])["MAP1"], 1)
    assert "D" not in glyphs
    assert glyphs["A"] == 0
