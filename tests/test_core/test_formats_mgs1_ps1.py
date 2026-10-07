"""Metal Gear Solid (PlayStation) PCX textures and font.res: read, write back unchanged, write an edit."""
import struct

from PIL import ImageDraw

from core import font_formats, texture_formats
from core.texture_formats import pcx


def _pcx4(width=16, height=4) -> bytes:
    """A 4-bit MGS PCX: palette of 16 greys (index 0 black = transparent), pixel x has colour x % 16."""
    head = bytearray(128)
    head[0:4] = b"\x0a\x05\x01\x01"
    struct.pack_into("<4H", head, 4, 0, 0, width - 1, height - 1)
    for i in range(16):
        head[0x10 + i * 3:0x13 + i * 3] = bytes((i * 16,) * 3)
    head[0x41] = 4
    stride = (width + 7) // 8
    struct.pack_into("<H", head, 0x42, stride)
    struct.pack_into("<7H", head, 0x4A, pcx.STAMP, 0, 0, 0, 0, 0, 16)
    body = bytearray()
    for _y in range(height):
        planes = bytearray(stride * 4)
        for x in range(width):
            for plane in range(4):
                if (x % 16) >> plane & 1:
                    planes[plane * stride + x // 8] |= 0x80 >> (x % 8)
        body += pcx._pack(bytes(planes))
    return bytes(head + body)


def test_pcx_reads_writes_back_and_takes_an_edit():
    data = _pcx4()
    assert texture_formats.detect(data, "x.pcx") == "pcx"
    tex = texture_formats.read("pcx", data)[0]
    assert tex.image.size == (16, 4) and tex.pixel_format == "PCX 4-bit"
    assert tex.image.getpixel((0, 0))[3] == 0 and tex.image.getpixel((5, 0)) == (80, 80, 80, 255)
    assert texture_formats.write("pcx", data, {0: tex.image}) == data
    edited = tex.image.copy()
    ImageDraw.Draw(edited).rectangle((0, 0, 3, 3), fill=(240, 240, 240, 255))
    again = texture_formats.read("pcx", texture_formats.write("pcx", data, {0: edited}))[0].image
    assert again.getpixel((1, 1)) == (240, 240, 240, 255) and again.getpixel((9, 2)) == tex.image.getpixel((9, 2))


def _font() -> bytes:
    """font.res: 96 hankaku glyphs (width 4 each, the 'A' 8), 2 zenkaku glyphs."""
    table, body = bytearray(), bytearray()
    for i in range(96):
        width = 8 if i == ord("A") - 32 else 4
        table += struct.pack(">I", width << 24 | len(body))
        body += bytes((0x55 if i % 2 else 0,) * (width * 3))
    end = 8 + len(table)
    return struct.pack(">II", end, end + len(body)) + table + body + bytes(72)


def test_font_res_round_trip_and_wider_glyph():
    data = _font()
    metadata, sheets = font_formats.extract("mgs1", data)
    assert font_formats.pack("mgs1", metadata, sheets, data) == data
    i = ord("A") - 32
    metadata["WID1"][0]["packets"][i]["width"] = 10
    sheet = sheets[0].copy()
    cx, cy = i % 16 * 12, i // 16 * 16
    ImageDraw.Draw(sheet).rectangle((cx, cy, cx + 9, cy + 11), fill=(255, 255, 255, 255))
    out = font_formats.pack("mgs1", metadata, [sheet], data)
    assert len(out) == len(data) + 6
    again, again_sheets = font_formats.extract("mgs1", out)
    assert again["WID1"][0]["packets"][i]["width"] == 10
    assert again_sheets[0].getpixel((cx + 9, cy + 11))[3] == 255
    assert again_sheets[0].crop((0, 0, 12, 16)).tobytes() == sheets[0].crop((0, 0, 12, 16)).tobytes()
