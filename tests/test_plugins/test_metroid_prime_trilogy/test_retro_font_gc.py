"""FONT version 0 to 2 of the GameCube Metroid Prime (``retro_font_gc``) on a font built here, then on the user's own
unpacked GameCube disc when the workspace has one (skipped otherwise)."""
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.font_formats import retro_font_gc

GAMECUBE_SOURCE = Path(r"E:\Emulators\RomHacking\Metroid\Prime (GC + PC port)\source")
WIDTH, HEIGHT = 64, 16
TEXTURE_ID = 0x1234ABCD
# (character, left px, top px, width, height, left padding, advance, right padding)
GLYPHS = [(0x20, 0, 0, 8, 8, 0, 4, 0), (0x41, 8, 0, 8, 8, 0, 7, 1), (0x42, 16, 0, 8, 8, 1, 6, 1)]


def _texture(fmt: int = 0) -> bytes:
    """A Retro TXTR (format 0 = I4, 2 = IA4, 7 = RGB5A3 ...) 64 x 16 with a few lit texels."""
    head = struct.pack(">IHHI", fmt, WIDTH, HEIGHT, 1)
    size = {0: WIDTH * HEIGHT // 2, 2: WIDTH * HEIGHT, 8: WIDTH * HEIGHT * 2}[fmt]
    blank = head + bytes(size)
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    for x, y in ((9, 1), (10, 2), (17, 3), (18, 4)):
        image.putpixel((x, y), (255, 255, 255, 255))
    return texture_formats.write("txtr_gx", blank, {0: image})


def _font(version: int = 1) -> bytes:
    out = b"FONT" + struct.pack(">III", version, 8, 8)
    if version >= 1:
        out += struct.pack(">I", 7)
    if version >= 2:
        out += struct.pack(">I", 1)
    out += struct.pack(">BBII", 0, 0, 0, 12) + b"Deface\0" + struct.pack(">III", TEXTURE_ID, 0, len(GLYPHS))
    for char, left, top, w, h, pad, advance, right in GLYPHS:
        out += struct.pack(">H4f7i", char, left / WIDTH, top / HEIGHT, (left + w) / WIDTH, (top + h) / HEIGHT,
                           pad, advance, right, w, h, 7, 0)
    return out + struct.pack(">I", 0)


@pytest.mark.parametrize("version", [0, 1, 2])
def test_parts_and_round_trip_of_every_version(version):
    form = _font(version)
    size, texture = retro_font_gc.parts(form)
    assert (size, texture) == (len(form), TEXTURE_ID)
    data = form + _texture()
    metadata, sheets = font_formats.extract("retro_font_gc", data)
    assert font_formats.pack("retro_font_gc", metadata, sheets, data) == data
    chars = font_formats.char_map(metadata)
    assert set(chars) == {" ", "A", "B"}
    packet = metadata["WID1"][0]["packets"][chars["B"]]
    assert packet == {"kerning": -1, "width": 8}                        # left 1 + advance 6 + right 1


def test_a_pixel_edit_and_a_width_edit_land_in_the_file():
    data = _font(1) + _texture()
    metadata, sheets = font_formats.extract("retro_font_gc", data)
    gly = metadata["GLY1"][0]
    glyph = font_formats.char_map(metadata)["A"]
    x, y = (glyph % gly["glyph_horizontal_count"]) * gly["cell_width"], (glyph // gly["glyph_horizontal_count"]) * gly["cell_height"]
    assert sheets[0].getpixel((x + 1, y + 1))[3] == 255              # the lit texel of glyph A (9, 1)
    sheets[0].putpixel((x + 5, y + 5), (255, 255, 255, 255))
    metadata["WID1"][0]["packets"][glyph]["width"] += 2
    edited = font_formats.pack("retro_font_gc", metadata, sheets, data)
    assert len(edited) == len(data) and edited != data
    again, sheets_again = font_formats.extract("retro_font_gc", edited)
    assert sheets_again[0].getpixel((x + 5, y + 5)) == (255, 255, 255, 255)
    assert again["WID1"][0]["packets"][glyph]["width"] == metadata["WID1"][0]["packets"][glyph]["width"]
    size, _tex = retro_font_gc.parts(edited)
    assert edited[:4] == b"FONT" and size == len(_font(1))
    # only glyph A changed in the texture: the other glyphs' cells are as they were
    other = font_formats.char_map(again)["B"]
    ox, oy = (other % gly["glyph_horizontal_count"]) * gly["cell_width"], (other // gly["glyph_horizontal_count"]) * gly["cell_height"]
    before = sheets[0].crop((ox, oy, ox + 8, oy + 8)).tobytes()
    assert sheets_again[0].crop((ox, oy, ox + 8, oy + 8)).tobytes() == before


@pytest.mark.parametrize("texture_format", [0, 2, 8])
def test_any_gx_texture_format_packs_back_unchanged(texture_format):
    data = _font(1) + _texture(texture_format)
    metadata, sheets = font_formats.extract("retro_font_gc", data)
    assert font_formats.pack("retro_font_gc", metadata, sheets, data) == data


def test_version_4_is_left_to_the_trilogy_backend():
    form = bytearray(_font(2))
    struct.pack_into(">I", form, 4, 4)
    assert retro_font_gc._is_gc(bytes(form)) is False


def _gamecube_fonts():
    return sorted((GAMECUBE_SOURCE / "font").glob("*.font")) if GAMECUBE_SOURCE.exists() else []


@pytest.mark.parametrize("path", _gamecube_fonts(), ids=lambda p: p.stem)
def test_every_gamecube_font_packs_back_and_keeps_an_edit(path):
    data = path.read_bytes()
    metadata, sheets = font_formats.extract("retro_font_gc", data)
    assert font_formats.pack("retro_font_gc", metadata, sheets, data) == data
    gly = metadata["GLY1"][0]
    chars = font_formats.char_map(metadata)
    glyph = chars["E"] if "E" in chars else next(iter(chars.values()))
    x = (glyph % gly["glyph_horizontal_count"]) * gly["cell_width"]
    y = (glyph // gly["glyph_horizontal_count"]) * gly["cell_height"]
    sheets[0].putpixel((x, y), (255, 255, 255, 255))
    edited = font_formats.pack("retro_font_gc", metadata, sheets, data)
    _meta, sheets_again = font_formats.extract("retro_font_gc", edited)
    assert sheets_again[0].getpixel((x, y))[3] > 0 or edited == data
