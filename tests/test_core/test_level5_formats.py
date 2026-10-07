"""Level-5 formats: compression, XPCK packs, IMGC textures and XF fonts (synthetic files; the game's when present)."""
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import font_formats
from core.containers import level5
from core.font_formats import xf
from core.texture_formats import imgc, pixels

WORKSPACE = Path(r"E:\Emulators\RomHacking\Yo-kai Watch\Yo-kai Watch\3DS")


# -- builders ---------------------------------------------------------------------------------


def make_xpck(files: dict) -> bytes:
    names = b"".join(name.encode() + b"\0" for name in files)
    names_blob = level5.compress(names, level5.STORED)
    names_blob += b"\0" * (-len(names_blob) % 4)
    info = 0x14
    names_at = info + 12 * len(files)
    data_at = names_at + len(names_blob)
    body, entries, name_at = bytearray(), bytearray(), 0
    for name, blob in files.items():
        start = len(body)
        body += blob + b"\0" * (-len(blob) % 4 or 4)
        entries += struct.pack("<IHHHBB", zlib.crc32(name.encode()), name_at, (start >> 2) & 0xFFFF, len(blob) & 0xFFFF,
                               start >> 18, len(blob) >> 16)
        name_at += len(name) + 1
    head = b"XPCK" + struct.pack("<BB5HI", len(files) & 0xFF, len(files) >> 8, info >> 2, names_at >> 2, data_at >> 2,
                                 (12 * len(files)) >> 2, len(names_blob) >> 2, len(body) >> 2)
    return head + entries + names_blob + bytes(body)


def make_imgc(image: Image.Image, fmt: int = 0x02) -> bytes:
    codec = pixels.codec("pica:" + imgc.FORMATS[fmt])
    width, height = image.size
    pw, ph = (width + 7) & ~7, (height + 7) & ~7
    padded = Image.new("RGBA", (pw, ph))
    padded.paste(image, (0, 0))
    tiles = [codec.encode(padded.crop((x, y, x + 8, y + 8)).transpose(Image.Transpose.TRANSPOSE))
             for y in range(0, ph, 8) for x in range(0, pw, 8)]
    table = level5.compress(struct.pack(f"<{len(tiles)}h", *range(len(tiles))), level5.STORED)
    store = level5.compress(b"".join(tiles), level5.STORED)
    bpp = len(tiles[0]) * 8 // 64
    head = bytearray(0x48)
    head[:4] = b"IMGC"
    head[0x0A], head[0x0C], head[0x0D] = fmt, 1, bpp
    struct.pack_into("<HHHI", head, 0x0E, 64 * bpp // 8, width, height, 0)
    struct.pack_into("<I", head, 0x1C, 0x48)
    struct.pack_into("<III", head, 0x34, len(table), (len(table) + 3) & ~3, len(store))
    return bytes(head) + table + b"\0" * (-len(table) % 4) + store


def make_xf(atlas: Image.Image, chars) -> bytes:
    """``chars``: [(code, advance, (ox, oy, w, h), (x, y, channel))], sorted by code."""
    sizes = []
    records = []
    for code, advance, size, (x, y, channel) in chars:
        if size not in sizes:
            sizes.append(size)
        records.append(struct.pack("<HHI", code, advance << 10 | sizes.index(size), y << 18 | x << 4 | channel))
    sizes_blob = level5.compress(b"".join(struct.pack("<bbBB", *s) for s in sizes), level5.LZ10)
    sizes_blob += b"\0" * (-len(sizes_blob) % 4)
    large = level5.compress(b"".join(records), level5.LZ10)
    large += b"\0" * (-len(large) % 4)
    small = level5.compress(b"", level5.STORED)
    size_off, large_off = 0x28, 0x28 + len(sizes_blob)
    small_off = large_off + len(large)
    head = b"FNTC01\0\0" + struct.pack("<ihhhhq6h", 1, 12, 0, 0, -1, 0, size_off >> 2, len(sizes), large_off >> 2,
                                      len(records), small_off >> 2, 0)
    return make_xpck({"000.xi": make_imgc(atlas), "FNT.bin": head + sizes_blob + large + small})


def _font():
    """A 32x16 atlas: 'H' (a box) in red, 'x' (a cross) in green, '!' in blue."""
    atlas = Image.new("RGBA", (32, 16), (0, 0, 0, 255))
    draw = ImageDraw.Draw(atlas)
    draw.rectangle((1, 1, 6, 10), outline=(255, 0, 0, 255))
    draw.line((10, 4, 15, 10), fill=(0, 255, 0, 255))
    draw.line((10, 10, 15, 4), fill=(0, 255, 0, 255))
    draw.line((20, 1, 20, 10), fill=(0, 0, 255, 255))
    chars = [(ord("!"), 3, (0, 1, 1, 10), (20, 1, 2)), (ord("H"), 8, (0, 1, 6, 10), (1, 1, 0)),
             (ord("x"), 7, (0, 4, 6, 7), (10, 4, 1))]
    return make_xf(atlas, chars)


# -- compression -------------------------------------------------------------------------------


def test_lz10_round_trip_and_header():
    data = bytes(range(200)) * 30 + b"abcabcabcabc" * 50 + bytes(7)
    packed = level5.compress(data)
    assert level5.method_of(packed) == level5.LZ10 and level5.size_of(packed) == len(data)
    assert len(packed) < len(data) // 2
    assert level5.decompress(packed) == data
    assert level5.decompress(level5.compress(b"")) == b""


def test_stored_zlib_and_rle():
    data = b"Yo-kai" * 40
    assert level5.decompress(level5.compress(data, level5.STORED)) == data
    assert level5.decompress(level5.compress(data, level5.ZLIB)) == data
    rle = struct.pack("<I", 8 << 3 | level5.RLE) + bytes([0x82, 0x41, 0x02]) + b"xyz"
    assert level5.decompress(rle) == b"AAAAAxyz"


def test_recompress_keeps_the_original_bytes_when_the_data_is_the_same():
    data = b"Whisper" * 30
    original = level5.compress(data, level5.STORED)
    assert level5.recompress(original, data) == original
    assert level5.decompress(level5.recompress(original, data + b"!")) == data + b"!"


# -- XPCK ----------------------------------------------------------------------------------------


def test_xpck_reads_builds_and_works_as_a_container():
    raw = make_xpck({"000.xi": b"A" * 10, "FNT.bin": b"B" * 6})
    pack = level5.Xpck(raw)
    assert pack.files == {"000.xi": b"A" * 10, "FNT.bin": b"B" * 6}
    assert pack.build() == raw
    container = level5.XpckContainer(raw)
    assert container.list_files() == ["000.xi", "FNT.bin"]
    container.write_file("000.xi", b"C" * 25)
    again = level5.Xpck(container.pack())
    assert again.files == {"000.xi": b"C" * 25, "FNT.bin": b"B" * 6}
    with pytest.raises(KeyError):
        container.write_file("missing", b"")


# -- IMGC ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", [0x00, 0x01, 0x02, 0x1C])
def test_imgc_decodes_what_was_encoded_and_writes_back_unchanged(fmt):
    image = Image.new("RGBA", (20, 12), (0, 0, 0, 255))
    ImageDraw.Draw(image).rectangle((2, 1, 9, 10), fill=(255, 255, 255, 255))
    data = make_imgc(image, fmt)
    decoded = imgc.decode(data)
    assert decoded.size == (20, 12)
    if fmt != 0x1C:                        # ETC1 is lossy
        assert decoded.tobytes() == image.tobytes()
    assert imgc.encode(data, decoded) == data
    assert imgc.read(data, {})[0].pixel_format == imgc.FORMATS[fmt]


def test_imgc_edit_changes_only_that_tile_and_can_grow_taller():
    image = Image.new("RGBA", (16, 16), (0, 0, 0, 255))
    data = make_imgc(image)
    edited = image.copy()
    edited.putpixel((9, 3), (255, 0, 0, 255))
    out = imgc.encode(data, edited)
    assert imgc.decode(out).tobytes() == edited.tobytes()
    taller = Image.new("RGBA", (16, 24), (0, 0, 0, 255))
    taller.putpixel((1, 20), (0, 0, 255, 255))
    grown = imgc.encode(data, taller, taller=True)
    assert imgc.decode(grown).size == (16, 24) and imgc.decode(grown).getpixel((1, 20)) == (0, 0, 255, 255)
    with pytest.raises(ValueError):
        imgc.encode(data, taller)


# -- XF fonts ------------------------------------------------------------------------------------


def test_xf_is_detected_and_an_unedited_model_packs_to_the_same_bytes():
    data = _font()
    assert font_formats.detect(data) == "xf" and font_formats.adds_glyphs("xf")
    metadata, sheets = font_formats.extract("xf", data)
    assert set(font_formats.char_map(metadata)) == {"!", "H", "x"}
    assert font_formats.font_map(metadata)["H"] == {"width": 8}
    assert font_formats.pack("xf", metadata, sheets, data) == data


def _cell(metadata, sheets, char):
    gly = metadata["GLY1"][0]
    index = font_formats.char_map(metadata)[char]
    x, y = (index % gly["glyph_horizontal_count"]) * gly["cell_width"], (index // gly["glyph_horizontal_count"]) * gly["cell_height"]
    return sheets[0].crop((x, y, x + gly["cell_width"], y + gly["cell_height"])), (x, y)


def test_xf_new_letter_in_a_spare_cell_becomes_a_real_character():
    data = _font()
    metadata, sheets = font_formats.extract("xf", data)
    h_cell, _ = _cell(metadata, sheets, "H")
    spare = max(font_formats.char_map(metadata).values()) + 1
    gly = metadata["GLY1"][0]
    sheets[0].paste(h_cell.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
                    ((spare % gly["glyph_horizontal_count"]) * gly["cell_width"], 0))
    metadata["MAP1"].append(font_formats.map_entries([(ord("Є"), spare)]))
    metadata["WID1"][0]["packets"][spare] = {"kerning": xf.PAD, "width": 9}
    out = font_formats.pack("xf", metadata, sheets, data)
    again, again_sheets = font_formats.extract("xf", out)
    assert font_formats.char_map(again)["Є"] is not None and font_formats.font_map(again)["Є"] == {"width": 9}
    new_cell, _ = _cell(again, again_sheets, "Є")
    assert font_formats.coverage(new_cell).getbbox() is not None
    for char in "!Hx":
        old, new = (font_formats.coverage(_cell(m, s, char)[0]) for m, s in ((metadata, sheets), (again, again_sheets)))
        assert new.crop(new.getbbox()).tobytes() == old.crop(old.getbbox()).tobytes()


def test_xf_width_edit_and_full_texture_grows_to_the_power_of_two():
    data = _font()
    metadata, sheets = font_formats.extract("xf", data)
    index = font_formats.char_map(metadata)["x"]
    metadata["WID1"][0]["packets"][index]["width"] = 11
    out = font_formats.pack("xf", metadata, sheets, data)
    assert font_formats.font_map(font_formats.extract("xf", out)[0])["x"] == {"width": 11}
    room = xf._Atlas((8, 6), [(0, 0, 8, 6, c) for c in range(3)])     # full; the GPU pads 6 rows to 8
    planes = [Image.new("L", (8, 6)) for _ in range(4)]
    assert xf._place(room, planes, 2, 2)[1] == 6 and room.height == 8 and planes[0].height == 8
    with pytest.raises(ValueError):
        xf._place(room, planes, 2, 3)


# -- the game's files ------------------------------------------------------------------------------


@pytest.mark.skipif(not (WORKSPACE / "source/fnt/ft_nrm.xf").is_file(), reason="needs the Yo-kai Watch workspace")
def test_real_fonts_and_textures_write_back_byte_for_byte():
    for name in ("ft_nrm", "ft_sml"):
        data = (WORKSPACE / f"source/fnt/{name}.xf").read_bytes()
        metadata, sheets = font_formats.extract("xf", data)
        assert len(font_formats.char_map(metadata)) == 8000
        assert font_formats.pack("xf", metadata, sheets, data) == data
    title = level5.Xpck((WORKSPACE / "source/data/menu/title_u00_en.xa").read_bytes())
    for blob in title.files.values():
        if blob[:4] == b"IMGC":
            assert imgc.encode(blob, imgc.decode(blob)) == blob
    translated = WORKSPACE / "translation/fnt/ft_nrm.xf"
    if translated.is_file():
        assert set("ЄєІіЇїҐґ’") <= set(font_formats.char_map(font_formats.extract("xf", translated.read_bytes())[0]))
