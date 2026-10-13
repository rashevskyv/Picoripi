"""Professor Layton DS: pictures (bg, animation atlases, LIMG sheets, GFSP) and fonts (compressed NFTR, GFNT)."""
import romhacking_root
import struct
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from core.containers import layton_ds, level5, lz10

LAYTON = romhacking_root.under('Professor Layton')


def bgr555(r, g, b):
    return r >> 3 | g >> 3 << 5 | b >> 3 << 10


PALETTE = [(0, 0, 0), (248, 0, 0), (0, 248, 0), (0, 0, 248), (248, 248, 248)]


def make_bg(cells_w=2, cells_h=2):
    """A background: 5 colours, 3 distinct 8x8 tiles, a cell table that reuses and flips them."""
    tiles = [bytes([(x + y) % 5 for y in range(8) for x in range(8)]), bytes([1] * 64), bytes([i % 2 * 4 for i in range(64)])]
    cells = [0, 1, 0 | 0x800, 2]
    data = struct.pack("<I", len(PALETTE)) + b"".join(struct.pack("<H", bgr555(*c)) for c in PALETTE)
    data += struct.pack("<I", len(tiles)) + b"".join(tiles)
    data += struct.pack("<HH", cells_w, cells_h) + struct.pack(f"<{len(cells)}H", *cells)
    return data


def test_bg_picture_reads_edits_and_keeps_unchanged_cells():
    raw = b"\x02\x00\x00\x00" + lz10.compress(make_bg())
    texture = texture_formats.read("layton_bg", raw)[0]
    assert texture.image.size == (16, 16)
    assert texture_formats.write("layton_bg", raw, {0: texture.image}) == raw
    edited = texture.image.copy()
    edited.putpixel((12, 12), (255, 255, 255, 255))                     # a pixel in the fourth cell
    new = texture_formats.write("layton_bg", raw, {0: edited})
    again = texture_formats.read("layton_bg", new)[0].image
    assert again.getpixel((12, 12)) == (255, 255, 255, 255)
    assert again.getpixel((0, 0)) == texture.image.getpixel((0, 0))     # the other cells are the same
    plain = layton_ds.decompress(new)[0]
    assert struct.unpack_from("<I", plain, 4 + 2 * 5)[0] == 4            # one new tile was appended


def make_ani(arj=False, bpp_code=3):
    """One frame of 16x8: two 8x8 tiles, 4-bit pixels, 4 colours."""
    colours = [(0, 0, 0), (248, 0, 0), (0, 248, 0), (0, 0, 248)]
    data = struct.pack("<HH", 1, bpp_code)
    if arj:
        data += struct.pack("<I", len(colours))
    data += struct.pack("<HHI", 16, 8, 2)
    for x in (0, 8):
        if arj:
            data += struct.pack("<HH", 0, 0)
        data += struct.pack("<HHHH", x, 0, 0, 0)
        pixels = [(px + py + x) % 4 for py in range(8) for px in range(8)]
        if arj:
            ordered = pixels            # one 8x8 block: raster order
        else:
            ordered = pixels
        data += bytes(ordered[2 * i] | ordered[2 * i + 1] << 4 for i in range(32))
    if not arj:
        data += struct.pack("<I", len(colours))
    data += b"".join(struct.pack("<H", bgr555(*c)) for c in colours)
    return data + b"animation tables stay"


@pytest.mark.parametrize("arj", [False, True])
def test_animation_frames_round_trip_and_a_changed_pixel_is_written(arj):
    raw = lz10.compress(make_ani(arj))
    fmt = "layton_arj" if arj else "layton_ani"
    texture = texture_formats.read(fmt, raw)[0]
    assert texture.image.size == (16, 8)
    assert texture.image.getpixel((0, 0))[3] == 0                         # colour 0 is transparent
    assert texture_formats.write(fmt, raw, {0: texture.image}) == raw
    edited = texture.image.copy()
    edited.putpixel((3, 3), (0, 0, 255, 255))
    new = texture_formats.write(fmt, raw, {0: edited})
    assert texture_formats.read(fmt, new)[0].image.getpixel((3, 3)) == (0, 0, 255, 255)
    assert layton_ds.decompress(new)[0].endswith(b"animation tables stay")


def make_limg(colours=16, w=16, h=8):
    palette = b"".join(struct.pack("<H", bgr555(i * 15 % 256, i * 7 % 256, i * 3 % 256)) for i in range(colours))
    cells = [0, 1]
    tile_size = 32 if colours <= 16 else 64
    tiles = [bytes((i * 3) % 16 | ((i * 5) % 16) << 4 for i in range(32)), bytes([0x11] * 32)]
    if tile_size == 64:
        tiles = [bytes((i * 3) % colours for i in range(64)), bytes([1] * 64)]
    sub_at = 48 + len(palette)
    param_at = sub_at + 8
    table_at = param_at + 12
    tiles_at = table_at + 2 * len(cells)
    head = b"LIMG" + struct.pack("<I12H", 48, sub_at, 1, param_at, 12, table_at, len(cells), tiles_at, len(tiles), 1, colours, w, h)
    head += bytes(48 - len(head))
    body = palette + bytes(8) + bytes(12) + struct.pack("<2H", *cells) + b"".join(tiles)
    return head + body


@pytest.mark.parametrize("colours", [16, 32])
def test_limg_sheet_and_cani_pack(colours):
    raw = lz10.compress(make_limg(colours))
    texture = texture_formats.read("layton_limg", raw)[0]
    assert texture.image.size == (16, 8)
    assert texture_formats.write("layton_limg", raw, {0: texture.image}) == raw
    edited = texture.image.copy()
    target = texture.image.getpixel((12, 3))
    colour = next(c for c in texture.image.getdata() if c[3] == 255 and c != target)   # a colour of the palette
    edited.putpixel((12, 3), colour)
    new = texture_formats.write("layton_limg", raw, {0: edited})
    assert new != raw
    assert texture_formats.read("layton_limg", new)[0].image.getpixel((12, 3)) == colour
    pack = layton_ds.Pack(layton_ds.LPC2, [layton_ds.Member("ani.lbin", b"LSCR" + bytes(28)),
                                           layton_ds.Member("sheet.limg", make_limg(colours))])
    cani = lz10.compress(pack.build())
    textures = texture_formats.read("layton_cani", cani)
    assert [t.name for t in textures] == ["sheet.limg"]
    assert texture_formats.write("layton_cani", cani, {0: textures[0].image}) == cani


def make_gfsp(cells, tiles, width=16, height=8, fmt=2, tail=b"", count=None):
    """A GFSP with one palette (5 colours) and one 4-bit texture; two size entries, then the names, then the chunks."""
    palette = b"GPLT" + struct.pack("<HH", 5, 8) + b"".join(struct.pack("<H", 0x8000 | bgr555(*c)) for c in PALETTE)
    palette += bytes(-len(palette) % 4)
    table = 0x34
    d_off = table + 2 * len(cells)
    texture = bytearray(b"GTXT" + bytes([fmt, 0, 0, 0]) + bytes(4) + struct.pack("<HH", width, height))
    texture += struct.pack("<HHHHHHI", 0x24, 1, 0x2C, 1, table, len(cells), d_off)
    texture += struct.pack("<HH", len(tiles) if count is None else count, 0)
    texture += bytes(table - len(texture)) + struct.pack(f"<{len(cells)}H", *cells)
    texture += bytes(d_off - len(texture)) + b"".join(tiles) + tail
    names = b"IMG.lp\0IMG.lt\0\0\0"
    head = b"GFSP" + struct.pack("<I", 0x00051002) + bytes(8)
    head += struct.pack("<I", (len(palette) + len(texture)) // 4) + bytes(4)
    head += struct.pack("<II", 0x10000 | len(palette), 0x80BF) + struct.pack("<II", 0x70000 | len(texture), 0x7AC69B)
    return head + names + palette + bytes(texture)


def test_gfsp_picture_edit_adds_a_tile_and_updates_the_header():
    t0 = bytes((i % 5) | ((i + 1) % 5) << 4 for i in range(32))
    t1 = bytes([0x22] * 32)
    raw = make_gfsp([0, 1], [t0, t1])
    texture = texture_formats.read("layton_gfsp", raw)
    assert texture[0].image.size == (16, 8)
    assert texture_formats.write("layton_gfsp", raw, {0: texture[0].image}) == raw
    edited = texture[0].image.copy()
    edited.putpixel((1, 1), (255, 255, 255, 255))
    new = texture_formats.write("layton_gfsp", raw, {0: edited})
    assert new != raw and new[:4] == b"GFSP"
    assert texture_formats.read("layton_gfsp", new)[0].image.getpixel((1, 1)) == (255, 255, 255, 255)
    # the cell that changed has its own tile now; level-5 compression is applied the same way as in the archive
    packed = level5.compress(raw)
    assert texture_formats.read("layton_gfsp", packed)[0].image.size == (16, 8)
    assert texture_formats.write("layton_gfsp", packed, {0: texture[0].image}) == packed


def test_font_wrappers_open_compressed_nftr_and_gfnt():
    # a GFNT font: glyph 'A' 5 wide, glyph '!' 1 wide, data offsets 0 and 8
    entries = struct.pack("<HBBH", 0x41, 97, 5, 0) + struct.pack("<HBBH", 0x21, 99, 1, 8)
    head = b"GFNT" + struct.pack("<5I", 2, 0x18, 0x18 + len(entries), 0x18 + len(entries) + 24, 16)
    data = head + entries + bytes(24) + bytes([0b00100100, 0x10, 0xA5, 0x94, 0xFA, 0x31, 0x02, 0, 0xFF, 0x02, 0, 0, 0, 0, 0, 0])
    compressed = level5.compress(data)
    meta, sheets = font_formats.extract("layton_gfnt", compressed, {})
    assert meta["GLY1"][0]["end_glyph"] == 1 and sheets[0].size[0] == 64 * 12
    assert font_formats.pack("layton_gfnt", meta, sheets, compressed, {}) == compressed
    edited = sheets[0].copy()
    edited.putpixel((0, 0), (255, 255, 255, 255))
    new = font_formats.pack("layton_gfnt", meta, [edited], compressed, {})
    assert new != compressed and level5.decompress(new)[:4] == b"GFNT"
    again, _ = font_formats.extract("layton_gfnt", new, {})
    assert again["GLY1"][0]["end_glyph"] == 1


# -- the game's own files ---------------------------------------------------------------------------------

def _first(root: Path, pattern: str, count: int = 3):
    return sorted(root.glob(pattern))[:count]


@pytest.mark.parametrize("game,platform,pattern,fmt", [
    ("Curious Village", "DS", "data/bg/en/*.arc", "layton_bg"),
    ("Curious Village", "DS", "data/ani/en/*.arc", "layton_ani"),
    ("Curious Village", "DS", "data/ani/en/*.arj", "layton_arj"),
    ("Pandora's Box", "DS", "data_lt2/bg/title/*.arc", "layton_bg"),
    ("Lost Future", "DS", "lt3/menu/*.cimg", "layton_limg"),
    ("Lost Future", "DS", "lt3/menu/uk/*.cani", "layton_cani"),
    ("Spectre's Call", "", "menu/uk/*.ca", "layton_gfsp"),
    ("Spectre's Call", "", "img/uk/*.ci", "layton_gfsp"),
])
def test_real_pictures_round_trip_byte_exact(game, platform, pattern, fmt):
    root = LAYTON / game / platform / "source"
    files = _first(root, pattern) if root.is_dir() else []
    if not files:
        pytest.skip(f"{root} has no {pattern}")
    for path in files:
        raw = path.read_bytes()
        textures = texture_formats.read(fmt, raw)
        assert textures
        assert texture_formats.write(fmt, raw, {i: t.image for i, t in enumerate(textures)}) == raw, path


@pytest.mark.parametrize("game,platform,path,fmt", [
    ("Curious Village", "DS", "data/font/fontevent.NFTR", "nftr"),
    ("Lost Future", "DS", "lt3/fnt/font_en1.cfnt", "layton_nftr"),
    ("Spectre's Call", "", "fnt/font_en2.cf", "layton_gfnt"),
    ("Spectre's Call", "", "fnt/color.cp", "layton_gfnt"),
])
def test_real_fonts_round_trip_byte_exact(game, platform, path, fmt):
    file = LAYTON / game / platform / "source" / path
    if not file.is_file():
        pytest.skip(f"{file} is missing")
    raw = file.read_bytes()
    meta, sheets = font_formats.extract(fmt, raw, {})
    assert font_formats.pack(fmt, meta, sheets, raw, {}) == raw


def test_gfsp_keeps_the_bytes_after_the_last_tile_and_the_game_tile_count():
    t1 = bytes([0x22] * 32)
    raw = make_gfsp([0, 1], [t1, bytes([0x31] * 32)], tail=b"", count=1)
    textures = texture_formats.read("layton_gfsp", raw)
    assert texture_formats.write("layton_gfsp", raw, {0: textures[0].image}) == raw        # nothing changed: same bytes
    edited = textures[0].image.copy()
    edited.putpixel((9, 1), (255, 255, 255, 255))
    new = texture_formats.write("layton_gfsp", raw, {0: edited})
    assert new[-4:] == b""
    assert texture_formats.read("layton_gfsp", new)[0].image.getpixel((9, 1)) == (255, 255, 255, 255)
