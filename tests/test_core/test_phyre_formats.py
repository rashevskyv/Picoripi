"""PhyreEngine files of Dragon Quest Builders 1: the single-texture ``phyre`` format (ARGB8 / ARGB4444 / DXT5,
bottom-up rows, mip levels) and the ``phyre_bmf`` bitmap font (45-byte character records, rotated glyphs,
8-bit atlas)."""
import struct

from core import font_formats
from core.font_formats import phyre_bmf
from core.texture_formats import phyre

SECTION = 2459


def _cluster(body: bytes, section: int = SECTION) -> bytes:
    """``RYHP`` header (84 bytes), ``section`` bytes of class table, then ``body``."""
    head = b"RYHP" + struct.pack("<II", 84, section) + b"LGXN" + bytes(84 - 16)
    return head + bytes(section) + body


def _texture(name: str, width: int, height: int, pixels: bytes, mip: int = 0) -> bytes:
    record = b"\x03" + struct.pack("<6I", mip, 6, 2, width, height, 1) + b"\x00"
    body = b"ui/test/pic.en.nx.dds\x00" + bytes(3) + record + b"PTexture2D\x00" + name.encode() + b"\x00" + bytes(40)
    return _cluster(body) .replace(bytes(SECTION), b"PTexture2D\x00" + bytes(SECTION - 11), 1) + pixels


def test_argb8_texture_reads_flipped_and_writes_back_the_same_bytes():
    # bottom-up rows: the first stored row is the bottom row; bytes B, G, R, A
    stored = bytes([0, 0, 255, 255, 0, 255, 0, 255]) + bytes([255, 0, 0, 255, 255, 255, 255, 128])
    data = _texture("ARGB8", 2, 2, stored)
    assert phyre.detect(data)
    texture = phyre.read(data, {})[0]
    assert texture.pixel_format == "ARGB8" and texture.image.size == (2, 2)
    assert texture.image.getpixel((0, 1)) == (255, 0, 0, 255) and texture.image.getpixel((1, 0)) == (255, 255, 255, 128)
    assert phyre.write(data, {0: texture.image}, {}) == data
    edited = texture.image.copy()
    edited.putpixel((0, 0), (1, 2, 3, 4))
    out = phyre.write(data, {0: edited}, {})
    assert out[-8:-4] == bytes([3, 2, 1, 4]) and out[:-8] == data[:-8] and len(out) == len(data)   # top-left = last row


def test_argb4444_texture_round_trips():
    values = struct.pack("<4H", 0xF00F, 0xFF00, 0x0FF0, 0x8421)
    data = _texture("ARGB4444", 2, 2, values)
    texture = phyre.read(data, {})[0]
    assert texture.pixel_format == "ARGB4444"
    assert phyre.write(data, {0: texture.image}, {}) == data


def test_a_dxt5_texture_with_mips_regenerates_them_only_when_redrawn():
    stored = bytes(range(16)) * (4 + 1 + 1 + 1)
    data = _texture("DXT5", 8, 8, stored, mip=3)
    assert phyre.detect(data)
    texture = phyre.read(data, {})[0]
    assert texture.mipmaps == 4 and texture.image.size == (8, 8)
    assert phyre.write(data, {0: texture.image}, {}) == data


def test_a_pack_of_many_textures_is_not_read():
    record = b"\x03" + struct.pack("<6I", 0, 6, 2, 4, 4, 1) + b"\x00"
    body = b"a.nx.dds\x00b.nx.dds\x00" + record + record + b"PTexture2D\x00ARGB8\x00" + bytes(40)
    data = _cluster(body) + bytes(64)
    assert not phyre.detect(data)


def _font(rotated_first: bool = True, glyphs: int = 10) -> bytes:
    """A Phyre bitmap font: ``glyphs`` records (codes 0x41...), a 64x32 8-bit atlas."""
    records = b""
    for n in range(glyphs):
        rot = 1 if rotated_first and n == 0 else 0
        records += struct.pack("<I10fB", 0x41 + n, 0.0, 0.0, 2.0 + 10 * n, 4.0, 6.0, 8.0, 0.0, 7.0, 7.5, 0.0, rot)[:44] + bytes([rot])
    texture = b"\x00" + struct.pack("<6I", 0, 6, 2, 64, 32, 1) + b"\x00"
    atlas = bytes(range(256)) * 8
    body = b"font/test.fgen#BitmapFont\x00" + bytes(2) + records + bytes(4) + texture + b"PBitmapFont\x00" + bytes(40)
    cluster = _cluster(body)
    return cluster.replace(bytes(11), b"PBitmapFont", 1)[:len(cluster)] + atlas[:64 * 32]


def test_bitmap_font_cells_round_trip_and_an_edit_lands_in_the_atlas():
    data = _font()
    assert phyre_bmf.detect(data)
    metadata, sheets = font_formats.extract("phyre_bmf", data, {})
    assert font_formats.pack("phyre_bmf", metadata, sheets, data, {}) == data
    cell_w, cell_h = metadata["GLY1"][0]["cell_width"], metadata["GLY1"][0]["cell_height"]
    assert (cell_w, cell_h) == (6, 8)
    sheet = sheets[0].copy()
    for y in range(cell_h):
        for x in range(cell_w):
            sheet.putpixel((cell_w * 3 + x, y), (255, 255, 255, 255))          # the fourth glyph (not rotated)
    out = font_formats.pack("phyre_bmf", metadata, [sheet], data, {})
    assert len(out) == len(data) and out != data
    assert out[len(out) - 64 * 32 + 4 * 64 + 32] == 255                       # glyph 3: x 32, y 4


def test_rotated_glyph_is_stored_on_its_side():
    data = _font()
    metadata, sheets = font_formats.extract("phyre_bmf", data, {})
    sheet = sheets[0].copy()
    sheet.putpixel((0, 0), (255, 255, 255, 255))                              # top-left of the upright glyph
    out = font_formats.pack("phyre_bmf", metadata, [sheet], data, {})
    changed = [i for i in range(len(data)) if data[i] != out[i]]
    assert changed
    atlas_at = len(data) - 64 * 32
    # upright (0, 0) of a glyph stored with ROTATE_90 + flip lands in the bottom-left of its 8x6 stored box
    assert changed[0] >= atlas_at
