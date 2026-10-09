"""EA Wii formats of Spore Hero: SHPG textures (core.texture_formats.shpg), FntG fonts (core.font_formats.fntg), and the
LZ11 compression of the texture sources."""
import struct

from PIL import Image, ImageDraw

from core import font_formats, texture_formats
from core.containers import nitro
from core.texture_formats import pixels, sources, surface


def _record(code: int, width: int, height: int, data: bytes, last: bool = False, mips: int = 0) -> bytes:
    size = 16 + len(data)
    return (bytes([code]) + (0 if last else size).to_bytes(3, "big") + struct.pack(">HHHHHH", width, height, 0, 0, 0x2000,
                                                                                   mips << 12) + data)


def _rgba8_palette(colours) -> bytes:
    """Entries as two planes: the A,R pairs of every entry, then the G,B pairs (each plane padded to 16 entries)."""
    plane = -(-len(colours) // 16) * 32
    ar = b"".join(bytes((a, r)) for r, _g, _b, a in colours).ljust(plane, b"\0")
    gb = b"".join(bytes((g, b)) for _r, g, b, _a in colours).ljust(plane, b"\0")
    return ar + gb


def _shpg(*images) -> bytes:
    """An SHPG: header, one directory entry per image, then each image's record chain."""
    head = 0x10 + 8 * len(images)
    head += -head % 16
    body, entries = b"", b""
    for name, chain in images:
        entries += name.ljust(4, b"\0")[:4] + struct.pack(">I", head + len(body))
        body += chain
    out = b"SHPG" + struct.pack("<I", 0) + struct.pack(">I", len(images)) + b"G359" + entries
    out = out.ljust(head, b"\0") + body
    return out[:4] + struct.pack("<I", len(out)) + out[8:]


def _c8_image(width=16, height=8):
    colours = [(i * 40 % 256, 255 - i * 40 % 256, i * 9 % 256, 255) for i in range(6)] + [(0, 0, 0, 0)] * 10
    picture = Image.new("RGBA", (width, height))
    picture.putdata([colours[(x // 4 + y) % 6] for y in range(height) for x in range(width)])
    codec = pixels.palette_codec("gx:C8", 8, colours, tile=(8, 4))
    data = bytearray(surface.surface_bytes(codec, width, height))
    surface.write(data, 0, codec, width, height, picture, force=True)
    chain = (_record(0x19, width, height, bytes(data) + bytes(16)) + _record(0x33, len(colours), 1, _rgba8_palette(colours))
             + _record(0x70, 0, 0, b"logo\0\0\0\0", last=True))
    return picture, chain


def test_shpg_c8_with_a_planar_rgba8_palette_reads_and_writes_back():
    picture, chain = _c8_image()
    data = _shpg((b"logo", chain))
    assert texture_formats.detect(data) == "shpg"
    [texture] = texture_formats.read("shpg", data)
    assert texture.name == "logo" and texture.pixel_format == "C8"
    assert texture.image.tobytes() == picture.tobytes()
    assert texture_formats.write("shpg", data, {0: texture.image}) == data
    edited = texture.image.copy()
    ImageDraw.Draw(edited).rectangle((0, 0, 3, 3), fill=(255, 0, 0, 255))        # a colour not in the palette
    out = texture_formats.write("shpg", data, {0: edited})
    assert len(out) == len(data) and texture_formats.read("shpg", out)[0].image.getpixel((1, 1)) == (255, 0, 0, 255)


def test_shpg_rgb5a3_with_mip_levels_and_cmpr():
    image = Image.new("RGBA", (8, 8), (0, 0, 255, 255))
    codec = pixels.codec("gx:RGB5A3")
    levels = surface.mip_levels(image, 2)
    texels = b"".join(codec.encode(level.resize((max(4, level.width), max(4, level.height))))
                      for level in levels)
    cmpr = pixels.codec("gx:CMPR").encode(Image.new("RGBA", (8, 8), (0, 255, 0, 255)))
    data = _shpg((b"a", _record(0x15, 8, 8, texels, last=True, mips=1)), (b"b", _record(0x1E, 8, 8, cmpr, last=True)))
    textures = texture_formats.read("shpg", data)
    assert [(t.pixel_format, t.mipmaps) for t in textures] == [("RGB5A3", 2), ("CMPR", 1)]
    assert textures[0].image.getpixel((3, 3)) == (0, 0, 255, 255)
    assert texture_formats.write("shpg", data, {i: t.image for i, t in enumerate(textures)}) == data


def test_lz11_compressed_texture_files_open_and_write_back(tmp_path):
    _picture, chain = _c8_image()
    data = _shpg((b"logo", chain))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.lsi").write_bytes(nitro.lz11_compress(data))
    found = sources.resolve([{"label": "x", "format": "shpg", "path": "a.lsi", "params": {"compression": "lz11"}}],
                            {"source_path": str(tmp_path / "src"), "translation_path": str(tmp_path / "tr")})
    image = found[0].read_original().image.copy()
    assert not found[0].write(image)
    ImageDraw.Draw(image).point((0, 0), fill=(255, 0, 0, 255))
    assert found[0].write(image)
    written = (tmp_path / "tr" / "a.lsi").read_bytes()
    assert written[0] == 0x11
    assert texture_formats.read("shpg", nitro.lz11_decompress(written)[0])[0].image.getpixel((0, 0)) == (255, 0, 0, 255)


def _fntg() -> bytes:
    """A FntG with glyphs ' ', 'A', 'B' on a 16x8 C4 page (IA8 palette: white at sixteen alpha levels)."""
    glyphs = [(0x20, 0, 0, 0, 0, 0, 0, 0, 0, 4), (0x41, 4, 6, 0, 0, 0, 0, 1, 0, 5), (0x42, 4, 6, 8, 0, 0, 1, 2, 0, 6)]
    table = b"".join(struct.pack(">HBBHHBbbBI", *g) for g in glyphs)
    page = Image.new("RGBA", (16, 8), (255, 255, 255, 0))
    ImageDraw.Draw(page).rectangle((0, 0, 3, 5), fill=(255, 255, 255, 255))
    ImageDraw.Draw(page).rectangle((8, 0, 9, 5), fill=(255, 255, 255, 0x88))
    colours = [(255, 255, 255, i * 17) for i in range(16)]
    codec = pixels.palette_codec("gx:C4", 4, colours, tile=(8, 8))
    texels = bytearray(surface.surface_bytes(codec, 16, 8))
    surface.write(texels, 0, codec, 16, 8, page, force=True)
    palette = b"".join(struct.pack(">BB", a, 255) for *_rgb, a in colours)
    chain = _record(0x18, 16, 8, bytes(texels)) + _record(0x30, 16, 1, palette, last=True)
    head = bytearray(0x80)
    head[:4] = b"FntG"
    struct.pack_into(">H", head, 10, len(glyphs))
    struct.pack_into(">I", head, 0x14, 0x80)
    struct.pack_into(">I", head, 0x1C, 0x80 + len(table))
    struct.pack_into(">I", head, 0x24, 7)
    out = bytearray(head + table + chain)
    struct.pack_into("<I", out, 4, len(out))
    return bytes(out)


def test_fntg_round_trip_edit_metrics_and_a_new_character_for_an_old_glyph():
    data = _fntg()
    assert font_formats.detect(data) == "fntg"
    metadata, sheets = font_formats.extract("fntg", data)
    assert font_formats.pack("fntg", metadata, sheets, data) == data
    assert font_formats.char_map(metadata) == {" ": 0, "A": 1, "B": 2}
    grid = metadata["GLY1"][0]
    x, y = (2 % 16) * grid["cell_width"], 0
    ImageDraw.Draw(sheets[0]).rectangle((x, y, x + grid["cell_width"] - 1, y + grid["cell_height"] - 1),
                                        fill=(255, 255, 255, 255))
    metadata["WID1"][0]["packets"][1]["width"] = 9
    metadata["MAP1"] = [font_formats.map_entries([(0x20, 0), (font_formats.char_code("Б"), 2),
                                                  (font_formats.char_code("A"), 1)])]
    out = font_formats.pack("fntg", metadata, sheets, data)
    assert len(out) == len(data)
    again, sheets2 = font_formats.extract("fntg", out)
    chars = font_formats.char_map(again)
    assert set(chars) == {" ", "A", "Б"}
    assert again["WID1"][0]["packets"][chars["A"]]["width"] == 9
    cell = chars["Б"]
    box = sheets2[0].crop(((cell % 16) * grid["cell_width"], 0, (cell % 16) * grid["cell_width"] + 4,
                           grid["cell_height"])).getchannel("A")
    assert min(box.crop((0, 2, 4, 8)).getdata()) == 255          # the glyph stands 2 rows down (its top offset)
    codes = [struct.unpack_from(">H", out, 0x80 + 16 * i)[0] for i in range(3)]
    assert codes == sorted(codes)
