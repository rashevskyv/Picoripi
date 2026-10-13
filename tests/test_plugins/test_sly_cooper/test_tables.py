"""Sly Cooper level prefix: CLUT, BMP, SHD and font tables are read and written back byte for byte.

The synthetic test builds a tiny world prefix by hand. The real-data test reads Paris.brx when the Sly data folder is
on this machine (environment variable SLY1_WORLDS, or the default folder); it skips otherwise.
"""
import os
import struct
from pathlib import Path

import pytest

from plugins.sly_cooper import tables

DEFAULT_WORLDS = Path("sly_cooper_switch/switch/ProjectCane/Worlds")
WORLDS = Path(os.environ.get("SLY1_WORLDS", str(DEFAULT_WORLDS)))
PARIS = WORLDS / "Paris" / "Paris.brx"
real = pytest.mark.skipif(not PARIS.exists(), reason="Sly data folder not on this machine")


class _Builder:
    """Appends raw parts and returns the offset where each part starts."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def add(self, raw: bytes) -> int:
        at = len(self.buf)
        self.buf += raw
        return at


def _synthetic_level() -> tuple:
    b = _Builder()
    b.add(b"\0" * 8)  # two S32 read by transition.cpp
    b.add(b"\x00")  # debug flag
    b.add(struct.pack("<h", 1))  # sound bank
    b.add(struct.pack("<I", 0))  # name table
    b.add(struct.pack("<III", 1, 0, 0))  # splice map: one splice, no symids, no extra options
    b.add(b"\x94" + struct.pack("<i", 7) + b"\xff")  # pair chain: S32 with next, then null
    b.add(struct.pack("<hh", 0, 2))  # option eopid 0 (OTYP_Cid), 2 bytes
    b.add(struct.pack("<hB", 1, 5))  # option eopid 1 (OTYP_Bool), 1 byte
    b.add(struct.pack("<h", -1))  # end of options
    b.add(b"\0" * 32)  # commentary descriptor
    b.add(struct.pack("<H", 4) + b"Hi!!")  # commentary speakers
    b.add(b"\0" * 32)  # music descriptor
    clut_count = b.add(struct.pack("<H", 1))
    clut = b.add(struct.pack("<IHHI", 0x11, 16, 1, 0))
    b.add(struct.pack("<H", 1))  # BMP count
    bmp = b.add(struct.pack("<HHIbbHII", 4, 4, 0, 20, 0, 0, 8, 0))  # 4x4 at 4 bpp is 8 bytes
    b.add(struct.pack("<H", 1))  # SHD count
    b.add(struct.pack("<H", 1))  # g_cpsaa
    shd = b.add(struct.pack("<BBhBBBBBBBBIHBB", 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1))  # ctex = 1
    b.add(struct.pack("<H", 1))  # saak Loop: known, so oid, fInstanced and a 24-byte body follow
    b.add(struct.pack("<hH", 5, 0) + b"\0" * 24)
    b.add(struct.pack("<HhBB", 7, 0, 1, 1) + struct.pack("<HH", 0, 0))  # TEX: one BMP, one CLUT
    shd_end = len(b.buf)
    font_count = b.add(struct.pack("<H", 1))
    font = b.add(struct.pack("<HhBBBBfI", 0, 0, 6, 3, 8, 0, 1.0, 2))
    b.add(struct.pack("<hhhh", 65, 0, 0, 5) + struct.pack("<hhhh", 66, 2, 1, 6))
    return bytes(b.buf), dict(clut=clut, clut_count=clut_count, bmp=bmp, shd=shd, shd_end=shd_end,
                              font_count=font_count, font=font)


def test_synthetic_level_decodes_every_table():
    data, at = _synthetic_level()
    w = tables.read_tables(data)
    assert w.ibnk == 1
    assert w.option_count == 2

    assert len(w.cluts) == 1
    clut = w.cluts[0]
    assert (clut.offset, clut.grfzon, clut.num_colors, clut.color_size, clut.base_offset) == (at["clut"], 0x11, 16, 1, 0)

    assert len(w.bmps) == 1
    bmp = w.bmps[0]
    assert (bmp.offset, bmp.width, bmp.height, bmp.psm, bmp.cb_pixels) == (at["bmp"], 4, 4, 20, 8)

    assert len(w.shaders) == 1
    assert (w.shaders[0].offset, w.shaders[0].end, w.shaders[0].ctex) == (at["shd"], at["shd_end"], 1)
    assert w.shader_end == len(data)  # the font table is the last part of the shader section

    assert len(w.fonts) == 1
    font = w.fonts[0]
    assert (font.offset, font.ibmp, font.iclut, font.dx_char, font.dx_space, font.dy, font.fontk) == (
        at["font"], 0, 0, 6, 3, 8, 0)
    assert font.rx_scale == 1.0
    assert font.glyph_offset == at["font"] + 16
    assert font.glyphs == (tables.Glyph(65, 0, 0, 5), tables.Glyph(66, 2, 1, 6))
    assert font.end == len(data)


def test_synthetic_level_round_trips_byte_exact():
    data, at = _synthetic_level()
    w = tables.read_tables(data)
    assert tables.write_clut_entry(w.cluts[0]) == data[at["clut"]:at["clut"] + 12]
    assert tables.write_bmp_entry(w.bmps[0]) == data[at["bmp"]:at["bmp"] + 20]
    assert tables.write_font(w.fonts[0]) == data[w.fonts[0].offset:w.fonts[0].end]
    assert tables.write_font_header(w.fonts[0]) == data[at["font"]:at["font"] + 16]


def test_truncated_level_is_refused():
    data, _ = _synthetic_level()
    with pytest.raises(tables.TablesError):
        tables.read_tables(data[:-1])


@real
def test_paris_font_table_and_round_trip():
    data = PARIS.read_bytes()
    w = tables.read_tables(data)
    font = next(f for f in w.fonts if f.offset == 0xF6C4)
    # Header bytes at 0xf6c4 read in CFontBrx::LoadFromBrx order (font.cpp): U16 ibmp = 0, S16 iclut = 855,
    # dxChar 25, dxSpace 10, dy 41, fontk 0, F32 rxScale 1.0, U32 cglyff 133. Glyphs run 0xf6d4..0xfafc.
    assert len(font.glyphs) == 133
    assert (font.ibmp, font.iclut, font.dy, font.fontk, font.rx_scale) == (0, 855, 41, 0, 1.0)
    assert (font.glyph_offset, font.end) == (0xF6D4, 0xFAFC)
    assert font.ibmp < len(w.bmps) and font.iclut < len(w.cluts)
    for c in w.cluts:
        assert tables.write_clut_entry(c) == data[c.offset:c.offset + 12]
    for bmp in w.bmps:
        assert tables.write_bmp_entry(bmp) == data[bmp.offset:bmp.offset + 20]
    for f in w.fonts:
        assert tables.write_font(f) == data[f.offset:f.end]
