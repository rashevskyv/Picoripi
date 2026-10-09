"""Fire Emblem Awakening bfnt fonts, Atlus STEX and CGFX textures: synthetic files, and the real games when on disk."""
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.font_formats import fe13_bfnt
from core.texture_formats import pixels, surface

FE = Path(r"E:\Emulators\RomHacking\Fire Emblem\Awakening\source\romfs")
SMT = Path(r"E:\Emulators\RomHacking\Shin Megami Tensei\IV\source\romfs")


def make_bfnt(glyphs, width=64, height=32):
    """An A4 one-sheet bfnt: ``glyphs`` = (code, x, y, w, h, top, advance); the boxes are filled with ink."""
    sheet = Image.new("RGBA", (width, height))
    table = b""
    for code, x, y, w, h, top, advance in sorted(glyphs):
        sheet.paste((255, 255, 255, 255), (x, y, x + w, y + h))
        table += struct.pack("<4H5B3x", code, 0, x, y, w, h, 0, top, advance)
    codec = pixels.codec("pica:A4")
    raw = bytearray(surface.surface_bytes(codec, width, height))
    surface.write(raw, 0, codec, width, height, sheet, force=True)
    data_at = (0x30 + len(table) + 0x7F) & ~0x7F
    head = struct.pack("<HHHHHHIHHIHHIHHII4x", 0, 0x20, 0xFF, 0, 12, 2, 10, width, height, len(raw), 4, 1, 0,
                       0x30, len(glyphs), data_at, len(raw))
    return head + table + bytes(data_at - 0x30 - len(table)) + bytes(raw)


def test_bfnt_extracts_cells_and_packs_back_the_same_bytes():
    font = make_bfnt([(0x41, 0, 0, 6, 10, 2, 7), (0x42, 8, 0, 6, 10, 2, 7), (0x3042, 16, 0, 8, 8, 2, 9)])
    assert font_formats.detect(font) == "fe13_bfnt"
    metadata, sheets = font_formats.extract("fe13_bfnt", font)
    chars = font_formats.char_map(metadata)
    assert chars["A"] == 0 and chars["あ"] == 2
    assert metadata["WID1"][0]["packets"][0]["width"] == 7
    assert font_formats.pack("fe13_bfnt", metadata, sheets, font) == font


def test_bfnt_new_character_goes_to_a_free_band_or_a_japanese_box():
    font = make_bfnt([(0x41, 0, 0, 6, 10, 2, 7), (0x3042, 16, 0, 8, 8, 2, 9)])
    metadata, sheets = font_formats.extract("fe13_bfnt", font)
    cw = metadata["GLY1"][0]["cell_width"]
    # draw Ґ into cell 2 (the spare row) and map it
    sheets[0].paste((255, 255, 255, 255), (2 * cw, 3, 2 * cw + 5, 3 + 9))
    metadata["MAP1"][0] = font_formats.map_entries([(0x41, 0), (0x3042, 1), (0x490, 2)])
    packed = font_formats.pack("fe13_bfnt", metadata, sheets, font)
    info = fe13_bfnt._info(packed)
    codes = [g[0] for g in info["glyphs"]]
    assert codes == [0x41, 0x490, 0x3042]                      # sorted, the Japanese box kept (a band was free)
    new = next(g for g in info["glyphs"] if g[0] == 0x490)
    assert (new[4], new[5], new[7]) == (5, 9, 3)
    again, _sheets = font_formats.extract("fe13_bfnt", packed)
    assert "Ґ" in font_formats.char_map(again)
    # no free band: the Japanese glyph's box is reused
    full = make_bfnt([(0x41, 0, 0, 6, 10, 2, 7), (0x3042, 16, 0, 8, 8, 2, 9)], height=11)
    metadata, sheets = font_formats.extract("fe13_bfnt", full)
    sheets[0].paste((255, 255, 255, 255), (2 * cw, 3, 2 * cw + 5, 3 + 7))
    metadata["MAP1"][0] = font_formats.map_entries([(0x41, 0), (0x3042, 1), (0x490, 2)])
    info = fe13_bfnt._info(font_formats.pack("fe13_bfnt", metadata, sheets, full))
    assert [g[0] for g in info["glyphs"]] == [0x41, 0x490] and info["glyphs"][1][2:4] == [16, 0]


def make_stex(width=8, height=8, gl=(0x8034, 0x6752), fmt="pica:RGBA4"):
    image = Image.new("RGBA", (width, height))
    for x in range(width):
        image.putpixel((x, 1), (x * 16, 255 - x * 16, 128, 255))
    codec = pixels.codec(fmt)
    raw = bytearray(surface.surface_bytes(codec, width, height))
    surface.write(raw, 0, codec, width, height, image, force=True)
    head = b"STEX" + struct.pack("<8I", 0, 0xDE1, width, height, gl[0], gl[1], len(raw), 0x80)
    return head + b"tex\0" + bytes(0x80 - len(head) - 4) + bytes(raw)


def test_stex_reads_and_writes_in_place():
    data = make_stex()
    assert texture_formats.detect(data) == "stex"
    tex = texture_formats.read("stex", data)
    assert len(tex) == 1 and tex[0].pixel_format == "RGBA4" and tex[0].image.size == (8, 8)
    assert texture_formats.write("stex", data, {0: tex[0].image}) == data
    edited = tex[0].image.copy()
    edited.putpixel((0, 0), (255, 0, 0, 255))
    out = texture_formats.write("stex", data, {0: edited})
    assert out != data and len(out) == len(data)
    assert texture_formats.read("stex", out)[0].image.getpixel((0, 0))[:3] == (255, 0, 0)


@pytest.mark.skipif(not FE.is_dir(), reason="the unpacked game is not on this machine")
def test_real_fe_fonts_and_telops_pack_back_the_same_bytes():
    for path in sorted((FE / "fonts").glob("*.bfnt")):
        raw = path.read_bytes()
        metadata, sheets = font_formats.extract("fe13_bfnt", raw)
        assert font_formats.pack("fe13_bfnt", metadata, sheets, raw) == raw, path.name
    telops = sorted((FE / "telop").glob("*_U.r"))
    assert telops
    for path in telops:
        raw = path.read_bytes()
        tex = texture_formats.read("cgfx", raw)
        assert tex and texture_formats.write("cgfx", raw, {i: t.image for i, t in enumerate(tex)}) == raw, path.name


@pytest.mark.skipif(not SMT.is_dir(), reason="the unpacked game is not on this machine")
def test_real_smt_textures_and_fonts():
    files = sorted(SMT.glob("tex/stex/*/*.stex"))
    assert len(files) > 200
    for path in files:
        raw = path.read_bytes()
        tex = texture_formats.read("stex", raw)
        assert texture_formats.write("stex", raw, {0: tex[0].image}) == raw, path.name
    raw = (SMT / "font" / "rodin_16_16.bcfnt").read_bytes()
    metadata, sheets = font_formats.extract("bcfnt", raw)
    chars = font_formats.char_map(metadata)
    assert "Ａ" in chars and "А" in chars and "Ґ" not in chars     # Shift-JIS keyed: full-width Latin, Cyrillic
    assert font_formats.pack("bcfnt", metadata, sheets, raw) == raw
