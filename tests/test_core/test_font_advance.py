"""Advance widths from the drawn pixels (core/font_formats/advance.py): a synthetic font, and the real HD message font.

The synthetic font has a 4x2 grid of 10x10 cells on one sheet: Latin letters with a right bearing of -1, and two
Cyrillic glyphs with a flat advance of 35, as the Wind Waker HD font has. The real test works on a copy.
"""
import shutil
from pathlib import Path

import pytest
from PIL import Image

from core.font_formats import advance, char_map, map_entries

REAL = Path("E:/Emulators/RomHacking/Zelda/Wind Waker/HD - Wii U/source/Font/CKingMsg.bffnt")  # the game's own copy: flat 35


def _synthetic():
    """Glyph 0 'A', 1 'B' (ink 6 wide, left bearing 0, advance 5 = ink - 1), glyph 2 'П' ink 6, kerning -2, advance 35."""
    sheet = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    for glyph, width in ((0, 6), (1, 6), (2, 6)):
        x0, y0 = glyph * 10, 0
        for x in range(width):
            for y in range(5):
                sheet.putpixel((x0 + x, y0 + y), (255, 255, 255, 255))
    metadata = {
        "GLY1": [{"cell_width": 10, "cell_height": 10, "glyph_horizontal_count": 4, "glyph_vertical_count": 2}],
        "MAP1": [map_entries([(ord("A"), 0), (ord("B"), 1), (ord("П"), 2)])],
        "WID1": [{"packets": [{"kerning": 0, "width": 5}, {"kerning": 0, "width": 5},
                              {"kerning": -2, "width": 35}], "glyph_widths": [6, 6, 6]}],
    }
    return metadata, [sheet]


def test_ink_width_is_the_inked_columns_of_the_cell():
    metadata, sheets = _synthetic()
    assert [advance.ink_width(metadata, sheets, g) for g in (0, 1, 2)] == [6, 6, 6]
    assert advance.ink_width(metadata, sheets, 5) is None      # an empty cell


def test_the_right_bearing_comes_from_the_latin_glyphs():
    metadata, sheets = _synthetic()
    assert advance.latin_right_bearing(metadata, sheets) == -1  # A and B: advance 5 - ink 6


def test_the_cyrillic_advance_follows_the_ink_and_the_left_bearing():
    metadata, sheets = _synthetic()
    changes = advance.remeasure(metadata, sheets, advance.cyrillic_glyphs(metadata))
    # left bearing = -kerning = +2, ink 6, right bearing -1: advance = 6 - (-2) - 1 = 7
    assert changes == [(2, 35, 7)]
    assert metadata["WID1"][0]["packets"][2]["kerning"] == -2     # kerning untouched
    assert metadata["WID1"][0]["packets"][0]["width"] == 5        # Latin untouched


def test_a_glyph_shared_with_a_latin_code_keeps_its_width():
    metadata, _ = _synthetic()
    metadata["MAP1"] = [map_entries([(ord("A"), 0), (ord("B"), 1), (ord("П"), 2), (0x0406, 1)])]
    assert advance.cyrillic_glyphs(metadata) == [2]


def test_a_remeasure_is_stable_on_a_second_pass():
    metadata, sheets = _synthetic()
    advance.remeasure(metadata, sheets, advance.cyrillic_glyphs(metadata))
    assert advance.remeasure(metadata, sheets, advance.cyrillic_glyphs(metadata)) == []


@pytest.mark.skipif(not REAL.is_file(), reason="the unpacked Wind Waker HD font is not on this machine")
def test_real_message_font_round_trip(tmp_path):
    from core import font_formats

    copy = tmp_path / "CKingMsg.bffnt"
    shutil.copyfile(REAL, copy)
    before_meta, before_sheets = font_formats.extract(font_formats.detect(copy.read_bytes()), copy.read_bytes(), {})
    changes = advance.fix_file(copy)
    assert len(changes) > 50
    data = copy.read_bytes()
    after_meta, after_sheets = font_formats.extract(font_formats.detect(data), data, {})
    # pixels and kerning are unchanged; the advance of every changed glyph is the rule's value
    assert [img.tobytes() for img in after_sheets] == [img.tobytes() for img in before_sheets]
    before_p = before_meta["WID1"][0]["packets"]
    after_p = after_meta["WID1"][0]["packets"]
    assert [p["kerning"] for p in after_p] == [p["kerning"] for p in before_p]
    assert {g: new for g, _old, new in changes} == {g: after_p[g]["width"] for g, _o, _n in changes}
    assert advance.fix_file(copy) == []                              # a second pass changes nothing
    letters = char_map(after_meta)
    assert after_p[letters["П"]]["width"] < 35                       # the flat Cyrillic advance is gone


def test_only_a_flat_cyrillic_block_is_remeasured():
    metadata, _sheets = _synthetic()
    assert advance.flat_block(metadata) is True                       # one Cyrillic glyph, one advance
    metadata["MAP1"] = [map_entries([(ord("A"), 0), (ord("B"), 1), (ord("П"), 2), (ord("Р"), 3)])]
    metadata["WID1"][0]["packets"].append({"kerning": 0, "width": 35})
    metadata["WID1"][0]["glyph_widths"].append(6)
    assert advance.flat_block(metadata) is True                       # two glyphs, both 35 - still flat
    metadata["WID1"][0]["packets"][3]["width"] = 20
    assert advance.flat_block(metadata) is False                      # measured values: left alone
