"""NFTR fonts of the DS Zelda games: 3-bit glyphs, LZ10 wrapper, widths that follow a redrawn glyph, Ukrainian cells.

The real-data tests read the clean USA ROMs in the scratch folder (never copied into the repository) and skip when
it is missing.
"""
import copy
import os
from pathlib import Path

import pytest

from core.font_formats import lz10_nftr, nftr
from plugins.zelda_ds.rom import nitro_files

SCRATCH = Path(os.environ.get("PICORIPI_SCRATCH", "scratch"), r"zelda_ds\rom_clean")
PH = SCRATCH / "ph_usa.nds"
ST = SCRATCH / "st_usa.nds"
PARAMS = {"columns": 16, "spare": 32}


def _font(rom_path, name):
    return nitro_files(rom_path.read_bytes())[name]


@pytest.mark.skipif(not PH.is_file(), reason="clean Phantom Hourglass ROM not in the scratch folder")
def test_three_bit_fonts_round_trip_byte_exact():
    for name in ("Font/zeldaDS_endL.nftr", "Font/zeldaDS_endS.nftr"):
        data = _font(PH, name)
        font = nftr.Font(data)
        assert font.bpp == 3
        assert font.build() == data
        assert all(font.encode(font.decode(glyph)) == glyph for glyph in font.glyphs)


@pytest.mark.skipif(not ST.is_file(), reason="clean Spirit Tracks ROM not in the scratch folder")
def test_lz10_fonts_round_trip_and_unchanged_pack_is_the_original_bytes():
    for name in ("Font/DSZ2_msg.nftr", "Font/DSZ2_endL.nftr", "Font/LC_Font_s_Name.nftr", "Font/DSZ2_endS.nftr"):
        data = _font(ST, name)
        assert lz10_nftr.is_font(data)
        metadata, sheets = lz10_nftr.extract(data, PARAMS)
        assert lz10_nftr.pack(metadata, sheets, data, PARAMS) == data


@pytest.mark.skipif(not PH.is_file(), reason="clean Phantom Hourglass ROM not in the scratch folder")
def test_redrawn_narrow_glyph_moves_its_width_and_advance_and_keeps_the_gap():
    data = _font(PH, "Font/zeldaDS_endL.nftr")
    metadata, sheets = nftr.extract(data, PARAMS)
    font = nftr.Font(data)
    cw, ch = font.cell_width, font.cell_height
    spare = len(font.glyphs) + 1
    sheet = sheets[0].copy()
    background = sheet.getpixel(((spare % 16) * cw, (spare // 16) * ch))
    for y in range(ch):
        for x in range(3, cw):
            sheet.putpixel((cw + x, y), background)          # glyph 1 keeps 3 columns of its ink
    out = nftr.pack(metadata, [sheet], data, PARAMS)
    after, _ = nftr.extract(out, PARAMS)
    was, now = metadata["WID1"][0], after["WID1"][0]
    assert now["glyph_widths"][1] < was["glyph_widths"][1]
    gap = was["packets"][1]["width"] - (-was["packets"][1]["kerning"]) - was["glyph_widths"][1]
    assert now["packets"][1]["width"] == -now["packets"][1]["kerning"] + now["glyph_widths"][1] + gap
    assert now["glyph_widths"][0] == was["glyph_widths"][0]


@pytest.mark.skipif(not PH.is_file(), reason="clean Phantom Hourglass ROM not in the scratch folder")
def test_a_width_typed_by_hand_is_kept():
    data = _font(PH, "Font/zeldaDS_endL.nftr")
    metadata, sheets = nftr.extract(data, PARAMS)
    edited = copy.deepcopy(metadata)
    edited["WID1"][0]["packets"][1]["width"] = 9
    out = nftr.pack(edited, sheets, data, PARAMS)
    after, _ = nftr.extract(out, PARAMS)
    assert after["WID1"][0]["packets"][1]["width"] == 9


@pytest.mark.skipif(not PH.is_file(), reason="clean Phantom Hourglass ROM not in the scratch folder")
def test_ukrainian_letters_missing_are_listed_not_drawn():
    font = nftr.Font(_font(PH, "Font/zeldaDS_endL.nftr"))
    report = nftr.ukrainian_coverage(font)
    assert report["missing_count"] == len(nftr.UKRAINIAN) == 66
    assert "Ї" in report["missing_ukrainian"]  # deslop: ignore[poor-substring-tests] single non-ASCII glyph marker: the Ukrainian letter is reported as missing
    assert report["bpp"] == 3
