"""Formats of Raving Rabbids: Party Collection (Wii): Jade textures (raw + palette, TGA, DDS) and FONTDESC fonts,
Wii archived fonts (RFNA, CX Huffman), the Rabbids 2 disc error font. Synthetic files round-trip byte-exact and
edits land; the real files are checked when the workspace is unpacked here."""
import random
import struct
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import font_formats, texture_formats
from core.font_formats import brfna, rrr_errfont
from core.font_formats.sources import join_pair
from core.texture_formats import jade

SOURCE = Path(r"E:\Emulators\RomHacking\Raving Rabbids Party Collection\source")
real = pytest.mark.skipif(not (SOURCE / "rrr1.bf").is_dir(), reason="Raving Rabbids Party Collection not unpacked here")
CODES = bytes.fromhex("3412d0caff00ff00dec0dec0")


def tex_header(kind: int, fmt: int, width: int, height: int, flags: int = 2, desc: int = 0) -> bytes:
    return struct.pack("<iHBBHHII", -1, flags, kind, fmt, width, height, 0, desc) + CODES


def raw4(width=16, height=8):
    """A 4-bit texture item (rows bottom first, high nibble first) and its 16-colour RGBA palette item."""
    pixels = bytes(((x // 4) << 4) | ((x // 4) + 1) for _y in range(height) for x in range(0, width, 2))
    palette = b"".join(bytes((i * 16, 255 - i * 16, i * 8, 255)) for i in range(16))
    return tex_header(6, 0x50, width, height) + pixels, palette


def test_a_raw_texture_round_trips_and_an_edit_maps_to_the_palette():
    item, palette = raw4()
    data = jade.join([item, palette])
    assert texture_formats.detect(data, "x.jtex") == "jade"
    tex = texture_formats.read("jade", data, {})[0]
    assert tex.image.size == (16, 8) and tex.pixel_format == "C4"
    assert texture_formats.write("jade", data, {0: tex.image}, {}) == data
    image = tex.image.copy()
    image.putpixel((0, 0), (16 * 15, 255 - 16 * 15, 8 * 15, 255))       # palette colour 15
    out = jade.split(texture_formats.write("jade", data, {0: image}, {}))
    assert out[1] == palette and len(out[0]) == len(item)
    assert out[0][32 + 7 * 8] >> 4 == 15                                  # top-left pixel: the last stored row


def test_a_tga_texture_is_bottom_row_first_rgba():
    width, height = 4, 2
    rows = [bytes((10, 20, 30, 40)) * width, bytes((50, 60, 70, 80)) * width]       # stored bottom row first
    tga = bytes(2) + b"\x02" + bytes(9) + struct.pack("<HH", width, height) + b"\x20\x08"
    item = tex_header(1, 0x10, width, height) + tga + rows[0] + rows[1]
    image = jade.decode(item)
    assert image.getpixel((0, 1)) == (10, 20, 30, 40) and image.getpixel((0, 0)) == (50, 60, 70, 80)
    assert jade.encode(item, image) == item


def test_a_dds_texture_writes_its_mip_levels_again():
    width = height = 8
    head = b"DDS " + struct.pack("<7I", 124, 0x21007, height, width, 32, 0, 2) + bytes(44) + \
        struct.pack("<II4s", 32, 4, b"DXT1") + bytes(40)
    item = tex_header(11, 0x20, width, height) + head + bytes(32 + 8)
    image = jade.decode(item)
    assert image.size == (8, 8)
    red = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    out = jade.encode(item, red)
    assert len(out) == len(item) and jade.decode(out).getpixel((3, 3))[0] > 200


def fontdesc(glyphs):
    body = b"FONTDESC" + struct.pack("<I", 0xE0)
    for code, box in glyphs:
        body += struct.pack("<i4f", code, *box)
    return body + struct.pack("<i", -1)


def test_a_jade_font_extracts_glyph_cells_and_packs_an_edit_back():
    item, palette = raw4(16, 8)
    desc = fontdesc([(0x41, (0.0, 0.0, 0.25, 1.0)), (0x29, (0.5, 0.0, 0.25, 1.0))])      # ')' = '(' mirrored
    data = jade.join([desc, item, palette])
    assert font_formats.detect(data) == "jade"
    meta, sheets = font_formats.extract("jade", data, {})
    assert font_formats.char_map(meta) == {"A": 0, ")": 1}
    assert meta["WID1"][0]["packets"][0]["width"] == 4
    assert font_formats.pack("jade", meta, sheets, data, {}) == data
    sheet = sheets[0].copy()
    ImageDraw.Draw(sheet).rectangle((0, 0, 3, 7), fill=(16 * 15, 255 - 16 * 15, 8 * 15, 255))
    out = jade.split(font_formats.pack("jade", meta, [sheet], data, {}))
    assert out[0] == desc and out[2] == palette and out[1] != item
    assert font_formats.extract("jade", jade.join(out), {})[1][0].getpixel((1, 1)) == (240, 15, 120, 255)


def test_cx_huffman_round_trips_bytes_and_nibbles():
    rng = random.Random(7)
    for data in (bytes(rng.choice(b"\x00\x11\xff\xf0") for _ in range(3000)), bytes(range(256)) * 20, b"\x05" * 64):
        packed = brfna.huffman_encode(data)
        assert packed[0] in (0x28, 0x24) and brfna.huffman_decode(packed) == data


def test_the_disc_error_font_round_trips_and_writes_ink_and_widths():
    records = b"".join(struct.pack(">2sHHBB3B5x", b"\x00" + c.encode(), x, 0, 4, 6, 0x80, 0x84, 0x81)
                       for c, x in (("A", 0), ("B", 4)))
    fnt = records + struct.pack("<H", 2)
    tex = struct.pack("<HH", 8, 6) + bytes(range(48))
    data = join_pair(fnt, tex)
    meta, sheets = rrr_errfont.extract(data, {})
    assert font_formats.char_map(meta) == {"A": 0, "B": 1} and meta["WID1"][0]["packets"][1]["width"] == 5
    assert rrr_errfont.pack(meta, sheets, data, {}) == data
    sheet = sheets[0].copy()
    sheet.putpixel((0, 0), (255, 255, 255, 255))
    meta["WID1"][0]["packets"][0]["width"] = 7
    out_fnt, out_tex = font_formats.sources.split_pair(rrr_errfont.pack(meta, [sheet], data, {}))
    assert out_tex[4] == 255 and out_fnt[9] == 0x80 + 6 and out_fnt[16:] == fnt[16:]


@real
def test_every_real_jade_font_and_texture_round_trips_and_an_edit_lands():
    fonts = sorted(SOURCE.rglob("*.jfnt"))
    textures = sorted(SOURCE.rglob("*.jtex"))
    assert len(fonts) >= 17 and len(textures) >= 1000
    for path in fonts:
        data = path.read_bytes()
        meta, sheets = font_formats.extract("jade", data, {})
        assert font_formats.pack("jade", meta, sheets, data, {}) == data, path
    kinds = set()
    for path in textures:
        data = path.read_bytes()
        tex = texture_formats.read("jade", data, {})[0]
        kinds.add(tex.pixel_format)
        assert texture_formats.write("jade", data, {0: tex.image}, {}) == data, path
    assert {"C4", "C8", "RGBA8 (TGA)", "DXT (DDS)"} <= kinds
    logo = SOURCE / "rrr1.bf" / "textures" / "_main_logo" / "20009efe.jtex"
    data = logo.read_bytes()
    image = texture_formats.read("jade", data, {})[0].image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 40, 40), fill=(0, 0, 0, 255))
    out = texture_formats.write("jade", data, {0: image}, {})
    assert len(out) == len(data) and out != data


@real
def test_the_real_menu_fonts_open_and_an_edited_sheet_packs_and_reads_back():
    data = (SOURCE / "files" / "fonts" / "wbf2.brfna").read_bytes()
    assert font_formats.detect(data) == "brfna"
    meta, sheets = font_formats.extract("brfna", data, {})
    assert font_formats.pack("brfna", meta, sheets, data, {}) == data
    glyph = font_formats.char_map(meta)["e"]
    g = meta["GLY1"][0]
    per = g["glyph_horizontal_count"] * g["glyph_vertical_count"]
    sheet = sheets[glyph // per].copy()
    cell = glyph % per
    x, y = (cell % g["glyph_horizontal_count"]) * g["cell_width"], (cell // g["glyph_horizontal_count"]) * g["cell_height"]
    ImageDraw.Draw(sheet).rectangle((x, y, x + 4, y + 4), fill=(255, 255, 255, 255))
    edited = list(sheets)
    edited[glyph // per] = sheet
    out = font_formats.pack("brfna", meta, edited, data, {})
    assert out[:4] == b"RFNA" and struct.unpack_from(">I", out, 8)[0] == len(out)
    again = font_formats.extract("brfna", out, {})[1]
    assert again[glyph // per].crop((x, y, x + 5, y + 5)).tobytes() != sheets[glyph // per].crop((x, y, x + 5, y + 5)).tobytes()
    meta2, _ = font_formats.extract("brfna", out, {})
    with pytest.raises(ValueError):                                 # no new characters in an archived font
        font_formats.pack("brfna", {**meta2, "MAP1": meta2["MAP1"] + [font_formats.map_entries([(0x0490, 0)])]},
                          again, out, {})


# -- TV Party: JTX textures and Flash vector fonts ---------------------------------------------------------


def jtx_item(fmt: int, width: int, height: int, data: bytes, palette_key: int = 0) -> bytes:
    head = struct.pack("<I", 0x3B0025AE) + tex_header(10, 0x10, width, height)
    jtx = struct.pack("<5If", 3, fmt, width, height, 0, 0.0) + (struct.pack("<I", palette_key) if fmt in (1, 2) else b"")
    return head + jtx + data + bytes(4)


def test_a_jtx_texture_round_trips_and_writes_dxt1_with_alpha_and_palettes():
    from core.texture_formats import jade_jtx
    dxt = jade_jtx.join([(1, jtx_item(12, 8, 8, bytes(range(32)) * 2))])
    assert texture_formats.detect(dxt, "x.jtx") == "jade_jtx"
    tex = texture_formats.read("jade_jtx", dxt, {})[0]
    assert tex.pixel_format == "DXT1 + alpha" and texture_formats.write("jade_jtx", dxt, {0: tex.image}, {}) == dxt
    red = Image.new("RGBA", (8, 8), (255, 0, 0, 128))
    back = texture_formats.read("jade_jtx", texture_formats.write("jade_jtx", dxt, {0: red}, {}), {})[0].image
    assert back.getpixel((2, 2))[0] > 200 and 100 < back.getpixel((2, 2))[3] < 160
    palette = struct.pack("<I", 7) + b"".join(bytes((i, 0, 0, 255)) for i in range(256))
    c8 = jade_jtx.join([(1, jtx_item(1, 4, 4, bytes(range(16)), 7)), (7, palette)])
    image = texture_formats.read("jade_jtx", c8, {})[0].image
    assert image.getpixel((3, 0)) == (3, 0, 0, 255)
    assert texture_formats.write("jade_jtx", c8, {0: image}, {}) == c8


def test_a_flash_font_draws_its_glyphs_and_packs_an_edited_cell_as_rectangles():
    from core.font_formats import swf_font
    square = swf_font._rectangles_shape([(1000, -15000, 9000, 0)])
    name = b"Test\0"
    body = struct.pack("<HBBB", 1, 0x8C, 1, len(name)) + name + struct.pack("<H", 1)
    body += struct.pack("<II", 8, 8 + len(square)) + square + struct.pack("<H", 0x41)
    body += struct.pack("<HHh", 16000, 4000, 0) + struct.pack("<h", 10000) + swf_font._rect_bytes(1000, 9000, -15000, 0)
    body += struct.pack("<H", 0)
    tags = struct.pack("<HI", (75 << 6) | 0x3F, len(body)) + body + struct.pack("<H", 0)
    movie_body = swf_font._rect_bytes(0, 100, 0, 100) + struct.pack("<HH", 30 << 8, 1) + tags
    movie = b"GFX\x08" + struct.pack("<I", len(movie_body) + 8) + movie_body
    assert swf_font.fonts(movie) == [{"id": 1, "name": "Test", "glyphs": 1}]
    meta, sheets = swf_font.extract(movie, {})
    assert font_formats.char_map(meta) == {"A": 0}
    assert sheets[0].getpixel((10, 30))[3] == 255 and sheets[0].getpixel((1, 30))[3] == 0
    assert swf_font.pack(meta, sheets, movie, {}) == movie
    sheet = sheets[0].copy()
    ImageDraw.Draw(sheet).rectangle((0, 0, 3, 3), fill=(255, 255, 255, 255))
    out = swf_font.pack(meta, [sheet], movie, {})
    assert struct.unpack_from("<I", out, 4)[0] == len(out)
    again = swf_font.extract(out, {})[1][0]
    assert again.getpixel((1, 1))[3] == 255 and again.getpixel((10, 30))[3] == 255


@real
def test_the_real_tv_party_fonts_and_textures_round_trip():
    from core.font_formats import swf_font
    movies = sorted((SOURCE / "rrr3_bin_wii.bf" / "flash").glob("*.gfx"))
    assert len(movies) >= 4
    for path in movies:
        data = path.read_bytes()
        for font in swf_font.fonts(data):
            if font["glyphs"] >= 10 and font["glyphs"] < 2000:
                meta, sheets = swf_font.extract(data, {"font": font["name"]})
                assert swf_font.pack(meta, sheets, data, {"font": font["name"]}) == data, (path, font)
    for path in sorted((SOURCE / "rrr3_bin_wii.bf" / "textures").rglob("*.jtx")):
        data = path.read_bytes()
        tex = texture_formats.read("jade_jtx", data, {})[0]
        assert texture_formats.write("jade_jtx", data, {0: tex.image}, {}) == data, path
