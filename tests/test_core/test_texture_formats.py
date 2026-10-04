"""Texture codecs and file formats (core.texture_formats): synthetic files, every codec, the sources layer."""
import json
import random
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import texture_formats
from core.containers import yaz0
from core.texture_formats import bc7, bntx, bti, ctpk, etc1, flim, g1t, gx2, pixels, raw, sources, surface, tegra

ROOT = Path(__file__).resolve().parents[2]
LOSSLESS = [name for name in pixels.names()
            if not name.startswith(("BC", "pica:ETC")) and name != "gx:CMPR"]
LOSSY = ["BC1", "BC2", "BC3", "BC4", "BC4L", "BC4A", "BC5", "BC5LA", "BC7", "gx:CMPR", "pica:ETC1", "pica:ETC1A4"]


def sarc(files: dict) -> bytes:
    """A little-endian SARC of ``{name: bytes}`` (nodes in name-hash order, 8-byte aligned data)."""
    def name_hash(name):
        value = 0
        for char in name.encode():
            value = (value * 0x65 + char) & 0xFFFFFFFF
        return value
    names = sorted(files, key=name_hash)
    name_table, name_offsets, data, ranges = b"", {}, b"", {}
    for name in names:
        name_offsets[name] = len(name_table)
        entry = name.encode() + b"\0"
        name_table += entry + bytes(-len(entry) % 4)
        data += bytes(-len(data) % 8)
        ranges[name] = (len(data), len(data) + len(files[name]))
        data += files[name]
    nodes = b"".join(struct.pack("<IIII", name_hash(n), 0x01000000 | name_offsets[n] // 4, *ranges[n]) for n in names)
    head_size = 0x14 + 0x0C + len(nodes) + 8 + len(name_table)
    data_offset = head_size + (-head_size % 0x100)
    head = b"SARC" + struct.pack("<HHIIHH", 0x14, 0xFEFF, data_offset + len(data), data_offset, 0x100, 0)
    head += b"SFAT" + struct.pack("<HHI", 0x0C, len(names), 0x65) + nodes + b"SFNT" + struct.pack("<HH", 8, 0) + name_table
    return head + bytes(data_offset - len(head)) + data


def picture(width, height, seed=1):
    """Lettering on a gradient with transparent corners: what a title card looks like."""
    rng = random.Random(seed)
    image = Image.new("RGBA", (width, height))
    for y in range(height):
        for x in range(width):
            image.putpixel((x, y), (x * 255 // max(1, width - 1), y * 255 // max(1, height - 1), 90, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width // 4, height // 4), fill=(0, 0, 0, 0))
    for _ in range(6):
        x, y = rng.randrange(width), rng.randrange(height)
        draw.rectangle((x, y, x + 5, y + 3), fill=(255, 255, 255, rng.choice((255, 128))))
    return image


def size_for(codec, width=32, height=16):
    bw, bh = codec.block
    return -(-width // bw) * bw, -(-height // bh) * bh


def mean_error(a, b):
    return sum(abs(x - y) for x, y in zip(a.tobytes(), b.tobytes())) / len(a.tobytes())


# -- codecs ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", LOSSLESS)
def test_a_lossless_codec_keeps_what_it_decoded(name):
    codec = pixels.codec(name)
    width, height = size_for(codec)
    once = codec.decode(codec.encode(picture(width, height)), width, height)
    stored = codec.encode(once)
    assert len(stored) == width // codec.block[0] * (height // codec.block[1]) * codec.size
    assert codec.decode(stored, width, height).tobytes() == once.tobytes()
    assert codec.encode(codec.decode(stored, width, height)) == stored


@pytest.mark.parametrize("name", LOSSY)
def test_a_block_codec_stays_close_to_the_picture_and_is_stable(name):
    codec = pixels.codec(name)
    width, height = size_for(codec)
    image = picture(width, height)
    decoded = codec.decode(codec.encode(image), width, height)
    assert mean_error(codec.decode(codec.encode(decoded), width, height), decoded) < 5, name
    if name in ("BC1", "BC2", "BC3", "BC7", "gx:CMPR", "pica:ETC1A4"):
        assert mean_error(decoded, image) < 12, name


def test_etc1_decodes_a_known_block_and_encodes_flat_colour_exactly():
    # differential mode, base (16, 8, 4) -> (132, 66, 33), table 0, all indices 0 (+2)
    value = (16 << 59) | (8 << 51) | (4 << 43) | (1 << 33)
    assert set(etc1.decode_block(value)) == {(134, 68, 35)}
    flat = [(200, 100, 50)] * 16
    assert max(abs(a - b) for t in etc1.decode_block(etc1.encode_block(flat)) for a, b in zip(t, flat[0])) <= 6


def test_bc7_blocks_decode_with_pillow():
    image = Image.new("RGBA", (32, 16))
    ImageDraw.Draw(image).text((1, 2), "Title", fill=(250, 200, 60, 255))
    decoded = Image.frombytes("RGBA", image.size, bc7.encode(image), "bcn", 7)
    black = Image.new("RGBA", image.size, (0, 0, 0, 255))
    assert mean_error(Image.alpha_composite(black, decoded), Image.alpha_composite(black, image)) < 3


def test_gx_i4_is_grey_with_alpha_and_ia8_keeps_both():
    i4 = pixels.codec("gx:I4")
    assert i4.decode(bytes([0xF0] * 32), 8, 8).getpixel((0, 0)) == (255, 255, 255, 255)
    assert i4.decode(bytes([0xF0] * 32), 8, 8).getpixel((1, 0)) == (0, 0, 0, 0)
    ia8 = pixels.codec("gx:IA8")
    assert ia8.decode(bytes([0x80, 0xFF] * 16), 4, 4).getpixel((3, 3)) == (255, 255, 255, 128)


def test_cmpr_tiles_hold_four_dxt1_blocks_in_z_order():
    codec = pixels.codec("gx:CMPR")
    image = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    image.paste((0, 0, 255, 255), (4, 0, 8, 4))       # top right block blue
    decoded = codec.decode(codec.encode(image), 8, 8)
    assert decoded.getpixel((5, 1))[2] > 200 and decoded.getpixel((1, 5))[0] > 200


def test_unknown_pixel_format_is_refused():
    with pytest.raises(ValueError):
        pixels.codec("gx:NOPE")


# -- surfaces and tilings -----------------------------------------------------------------------------


def test_an_edit_rewrites_only_the_elements_it_touches():
    codec = pixels.codec("BC3")
    data = bytearray(codec.encode(picture(32, 16)))
    image = codec.decode(bytes(data), 32, 16)
    before = bytes(data)
    assert surface.write(data, 0, codec, 32, 16, image) == 0 and bytes(data) == before
    edited = image.copy()
    edited.putpixel((5, 5), (1, 2, 3, 4))
    assert surface.write(data, 0, codec, 32, 16, edited) == 1
    changed = [i for i in range(0, len(data), 16) if data[i:i + 16] != before[i:i + 16]]
    assert changed == [(1 * 8 + 1) * 16]      # block (1, 1) of an 8-block-wide surface


def test_odd_sizes_pad_to_whole_elements():
    codec = pixels.codec("gx:I4")
    image = picture(13, 5)
    data = bytearray(surface.surface_bytes(codec, 13, 5))
    surface.write(data, 0, codec, 13, 5, image)
    assert surface.read(bytes(data), 0, codec, 13, 5).size == (13, 5)
    with pytest.raises(ValueError):
        surface.write(data, 0, codec, 13, 5, picture(12, 5))


@pytest.mark.parametrize("tile_mode,bpp", [(gx2.TILE_2D_THIN1, 8), (gx2.TILE_2D_THIN1, 32), (gx2.TILE_2D_THIN1, 128),
                                           (gx2.TILE_1D_THIN1, 16), (gx2.TILE_LINEAR_ALIGNED, 32)])
def test_gx2_offsets_are_distinct_and_element_aligned(tile_mode, bpp):
    offsets = gx2.element_offsets(40, 24, bpp, tile_mode)
    assert len(set(offsets)) == len(offsets) and all(o % (bpp // 8) == 0 for o in offsets)


def test_tegra_block_linear_offsets_are_distinct():
    offsets = tegra.block_addresses(20, 40, 16, 2)
    assert len(set(offsets)) == len(offsets) == 800


def test_mip_levels_halve_down_to_one_pixel():
    assert [m.size for m in surface.mip_levels(picture(8, 2), 4)] == [(8, 2), (4, 1), (2, 1), (1, 1)]


# -- synthetic files --------------------------------------------------------------------------------


def make_bti(fmt_id, width, height, image, mips=1, pal_format=2, palette=None):
    name = f"gx:{bti.FORMATS[fmt_id]}"
    codec = pixels.palette_codec(name, bti._PALETTE[fmt_id][0], palette, tile=bti._PALETTE[fmt_id][1]) \
        if palette else pixels.codec(name)
    levels = surface.mip_levels(image, mips)
    pixels_data = b"".join(codec.encode(_padded(m, codec)) for m in levels)
    pal = b""
    if palette:
        _dec, enc = pixels.gx_palette_format(pal_format)
        pal = struct.pack(f">{len(palette)}H", *(enc(*c) for c in palette))
    head = struct.pack(">BBHHBBBBHI", fmt_id, 0, width, height, 0, 0, 1 if palette else 0, pal_format,
                       len(palette or ()), 0x20 if palette else 0)
    head += bytes(8) + bytes([mips, 0, 0, 0]) + struct.pack(">I", 0x20 + len(pal))
    return head + pal + pixels_data


def _padded(image, codec):
    bw, bh = codec.block
    out = Image.new("RGBA", (-(-image.width // bw) * bw, -(-image.height // bh) * bh))
    out.paste(image, (0, 0))
    return out


@pytest.mark.parametrize("fmt_id", [0, 2, 3, 5, 6, 14])
def test_bti_round_trip_and_edit(fmt_id):
    image = picture(24, 12)
    data = make_bti(fmt_id, 24, 12, image, mips=3)
    texture = bti.read(data, {})[0]
    assert texture.image.size == (24, 12) and texture.mipmaps == 3
    assert bti.write(data, {0: texture.image}, {}) == data
    edited = texture.image.copy()
    ImageDraw.Draw(edited).rectangle((0, 0, 7, 7), fill=(255, 255, 255, 255))
    new = bti.write(data, {0: edited}, {})
    assert len(new) == len(data) and new != data
    assert bti.read(new, {})[0].image.getpixel((2, 2))[3] == 255


def test_bti_palette_is_kept_or_made_again():
    palette = [(0, 0, 0, 0), (255, 255, 255, 255), (255, 0, 0, 255)] + [(0, 0, 0, 255)] * 13
    image = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
    data = make_bti(8, 8, 8, image, palette=palette)
    texture = bti.read(data, {})[0]
    assert texture.pixel_format == "C4" and texture.image.getpixel((0, 0)) == (255, 255, 255, 255)
    red = image.copy()
    red.putpixel((0, 0), (255, 0, 0, 255))
    kept = bti.write(data, {0: red}, {})
    assert kept[0x20:0x40] == data[0x20:0x40]                 # same palette
    green = image.copy()
    green.putpixel((0, 0), (0, 255, 0, 255))
    remade = bti.write(data, {0: green}, {})
    assert remade[0x20:0x40] != data[0x20:0x40]
    assert bti.read(remade, {})[0].image.getpixel((0, 0)) == (0, 255, 0, 255)


def make_flim_3ds(fmt_name, width, height, image, flags=0):
    fmt = {v: k for k, v in flim.PICA_FLIM.items()}[fmt_name]
    codec = pixels.codec("pica:" + fmt_name)
    stored_w, stored_h = flim._pow2(width), flim._pow2(height)
    if flags in (4, 8):
        stored_w, stored_h = stored_h, stored_w
    full = Image.new("RGBA", (stored_h, stored_w) if flags in (4, 8) else (stored_w, stored_h))
    full.paste(image, (0, 0))
    data = codec.encode(flim._to_stored(full, flags))
    footer = b"FLIM" + struct.pack("<HHIIHH", 0xFEFF, 0x14, 0x07020000, len(data) + 0x28, 1, 0)
    footer += b"imag" + struct.pack("<IHHHBBI", 0x10, width, height, 0x80, fmt, flags, len(data))
    return data + footer


@pytest.mark.parametrize("fmt_name,flags", [("ETC1A4", 0), ("A4", 4), ("LA8", 8), ("RGBA8", 0)])
def test_3ds_bflim_round_trip_and_turned_images(fmt_name, flags):
    image = picture(40, 20)
    data = make_flim_3ds(fmt_name, 40, 20, image, flags)
    assert flim.detect(data) and texture_formats.detect(data) == "bflim"
    texture = flim.read(data, {})[0]
    assert texture.image.size == (40, 20)
    assert flim.write(data, {0: texture.image}, {}) == data
    edited = texture.image.copy()
    edited.paste((255, 255, 255, 255), (30, 10, 40, 20))
    again = flim.read(flim.write(data, {0: edited}, {}), {})[0].image
    assert again.getpixel((35, 15))[3] == 255
    assert mean_error(again.crop((0, 0, 20, 10)), texture.image.crop((0, 0, 20, 10))) == 0


def make_flim_wiiu(fmt_id, width, height, image, tile_mode=4):
    codec = pixels.codec(flim.CAFE_FLIM[fmt_id])
    bw, bh = codec.block
    wide, high = -(-width // bw), -(-height // bh)
    offsets = gx2.element_offsets(wide, high, codec.size * 8, tile_mode, 0)
    data = bytearray(max(offsets) + codec.size)
    surface.write(data, 0, codec, width, height, image, offsets)
    footer = b"FLIM" + struct.pack(">HHIIHH", 0xFEFF, 0x14, 0x02020000, len(data) + 0x28, 1, 0)
    footer += b"imag" + struct.pack(">IHHHBBI", 0x10, width, height, 0x200, fmt_id, tile_mode, len(data))
    return bytes(data) + footer


@pytest.mark.parametrize("fmt_id", [9, 14, 16, 17])
def test_wiiu_bflim_round_trip(fmt_id):
    image = picture(48, 24)
    data = make_flim_wiiu(fmt_id, 48, 24, image)
    texture = flim.read(data, {})[0]
    assert flim.write(data, {0: texture.image}, {}) == data
    if fmt_id == 9:
        assert texture.image.tobytes() == image.tobytes()


def make_ctpk(entries):
    """``[(name, fmt id, image)]`` -> a CTPK."""
    header_end = 0x20 + 0x20 * len(entries)
    names = b"".join(name.encode() + b"\0" for name, _f, _i in entries)
    data_base = (header_end + len(names) + 0x7F) & ~0x7F
    blobs, table, offset, name_at = [], b"", 0, header_end
    for name, fmt, image in entries:
        blob = pixels.codec("pica:" + ctpk.PICA[fmt]).encode(image)
        table += struct.pack("<IIIIHHBBBBII", name_at, len(blob), offset, fmt, image.width, image.height, 1, 0, 0, 0, 0, 0)
        name_at += len(name) + 1
        blobs.append(blob)
        offset += len(blob)
    head = b"CTPK" + struct.pack("<HHIIII", 1, len(entries), data_base, offset, 0, 0) + bytes(8)
    body = head + table + names
    return body + bytes(data_base - len(body)) + b"".join(blobs)


def test_ctpk_lists_its_textures_and_writes_one():
    data = make_ctpk([("a.tga", 13, picture(16, 8)), ("b.tga", 5, picture(8, 8, 2))])
    textures = ctpk.read(data, {})
    assert [(t.name, t.pixel_format, t.image.size) for t in textures] == [
        ("a.tga", "ETC1A4", (16, 8)), ("b.tga", "LA8", (8, 8))]
    assert ctpk.write(data, {0: textures[0].image, 1: textures[1].image}, {}) == data
    new = ctpk.write(data, {1: Image.new("RGBA", (8, 8), (255, 255, 255, 255))}, {})
    assert ctpk.read(new, {})[0].image.tobytes() == textures[0].image.tobytes()
    assert ctpk.read(new, {})[1].image.getpixel((3, 3)) == (255, 255, 255, 255)


def make_bntx(textures):
    """``[(name, format byte, image)]`` -> a BNTX of single-level textures, block height 1."""
    out = bytearray(0x40)
    out[:4] = b"BNTX"
    table_at = len(out)
    out += bytes(8 * len(textures))
    struct.pack_into("<IQ", out, 0x24, len(textures), table_at)
    for index, (name, fmt, image) in enumerate(textures):
        codec = pixels.codec(bntx.FORMATS[fmt])
        bw, bh = codec.block
        wide, high = -(-image.width // bw), -(-image.height // bh)
        offsets = tegra.block_addresses(wide, high, codec.size, 1)
        pixels_data = bytearray(max(offsets) + codec.size)
        surface.write(pixels_data, 0, codec, image.width, image.height, image, offsets)
        name_at = len(out)
        out += struct.pack("<H", len(name)) + name.encode() + b"\0"
        out += bytes(-len(out) % 8)
        mips_at = len(out)
        out += bytes(8)
        data_at = (len(out) + 0x1FF) & ~0x1FF
        out += bytes(data_at - len(out)) + pixels_data
        out += bytes(-len(out) % 8)
        brti = len(out)
        out += bytes(0x80)
        out[brti:brti + 4] = b"BRTI"
        struct.pack_into("<H", out, brti + 0x16, 1)
        struct.pack_into("<I", out, brti + 0x1C, fmt << 8 | 1)
        struct.pack_into("<iiiii", out, brti + 0x24, image.width, image.height, 1, 1, 0)
        struct.pack_into("<I", out, brti + 0x50, len(pixels_data))
        struct.pack_into("<Q", out, brti + 0x60, name_at)
        struct.pack_into("<Q", out, brti + 0x70, mips_at)
        struct.pack_into("<Q", out, mips_at, data_at)
        struct.pack_into("<Q", out, table_at + 8 * index, brti)
    return bytes(out)


def test_bntx_textures_by_name_and_unsupported_formats_listed():
    data = make_bntx([("Logo", 0x0B, picture(40, 20)), ("Mask", 0x1D, picture(32, 16))])
    astc = bytearray(make_bntx([("Astc", 0x0B, picture(8, 8))]))
    struct.pack_into("<I", astc, struct.unpack_from("<Q", astc, struct.unpack_from("<Q", astc, 0x28)[0])[0] + 0x1C,
                     0x2D << 8 | 1)
    assert "not supported" in bntx.read(bytes(astc), {})[0].pixel_format
    with pytest.raises(ValueError):
        bntx.write(bytes(astc), {0: picture(8, 8)}, {})
    textures = bntx.read(data, {})
    assert [t.name for t in textures] == ["Logo", "Mask"]
    assert textures[0].image.tobytes() == picture(40, 20).tobytes()
    assert bntx.write(data, {0: textures[0].image, 1: textures[1].image}, {}) == data
    new = bntx.write(data, {0: Image.new("RGBA", (40, 20), (1, 2, 3, 4))}, {})
    assert bntx.read(new, {})[0].image.getpixel((39, 19)) == (1, 2, 3, 4)


def make_g1t(textures):
    """``[(format byte, image)]`` (power-of-two sizes) -> a G1T with one level each."""
    table = 0x20
    body, offsets = b"", []
    for fmt, image in textures:
        offsets.append(4 * len(textures) + len(body))
        dims = (image.width.bit_length() - 1) | (image.height.bit_length() - 1) << 4
        body += bytes([0x10, fmt, dims, 0, 0, 0, 0, 0]) + pixels.codec(g1t.FORMATS[fmt]).encode(image)
    head = b"GT1G0600" + struct.pack("<IIIII", 0, table, len(textures), 0x10, 0) + bytes(4)
    return head + struct.pack(f"<{len(offsets)}I", *offsets) + body


def test_g1t_textures_read_and_write():
    data = make_g1t([(0x5F, picture(16, 8)), (0x01, picture(8, 8)), (0x5B, picture(8, 4))])
    textures = g1t.read(data, {})
    assert [(t.pixel_format, t.image.size) for t in textures] == [("BC7", (16, 8)), ("RGBA8", (8, 8)), ("BC3", (8, 4))]
    assert g1t.write(data, {0: textures[0].image, 2: textures[2].image}, {}) == data
    new = g1t.write(data, {1: Image.new("RGBA", (8, 8), (9, 8, 7, 6))}, {})
    assert g1t.read(new, {})[1].image.getpixel((0, 0)) == (9, 8, 7, 6)


def test_raw_textures_at_offsets():
    codec = pixels.codec("n64:IA8")
    first, second = picture(16, 8), picture(16, 8, 3)
    data = bytes(16) + codec.encode(first) + codec.encode(second)
    params = {"pixel_format": "n64:IA8", "width": 16, "height": 8,
              "textures": [{"name": "a", "offset": "0x10"}, {"name": "b", "offset": 16 + 128}]}
    textures = raw.read(data, params)
    assert [t.name for t in textures] == ["a", "b"]
    assert raw.write(data, {0: textures[0].image, 1: textures[1].image}, params) == data


def test_unknown_texture_format_is_refused():
    with pytest.raises(ValueError):
        texture_formats.read("nope", b"")


# -- compression ------------------------------------------------------------------------------------


def test_smallest_yaz0_decompresses_to_its_input():
    rng = random.Random(4)
    for data in (b"", b"a", bytes(rng.randrange(4) for _ in range(3000)), b"abc" * 500):
        packed = yaz0.compress_smallest(data)
        assert yaz0.decompress(packed) == data
        assert len(packed) <= len(yaz0.compress(data))


def make_yar(blocks):
    stored = []
    for block in blocks:
        packed = yaz0.compress(block)
        stored.append(packed + bytes(-len(packed) % 16))
    ends, at = [], 0
    for packed in stored:
        at += len(packed)
        ends.append(at)
    header = 4 + 4 * len(ends)
    out = struct.pack(f">I{len(ends)}I", header, *ends) + b"".join(stored)
    return out + bytes(-len(out) % 16)


def test_yar_blocks_unpack_and_pack_again():
    blocks = [bytes([i]) * 256 + bytes(range(64)) for i in range(4)]
    data = make_yar(blocks)
    plain, pack = sources._decompress(data, "yar")
    assert plain == b"".join(blocks)
    assert pack(plain) == data
    edited = bytearray(plain)
    edited[330] = 0xEE
    again, _pack = sources._decompress(pack(bytes(edited)), "yar")
    assert again == bytes(edited)


def test_braces_expand():
    assert sources.expand_braces("t/{a,b}_{1,2}.bti") == ["t/a_1.bti", "t/a_2.bti", "t/b_1.bti", "t/b_2.bti"]


# -- sources: projects, archives, the translation copy ---------------------------------------------------


@pytest.fixture
def project(tmp_path):
    source, translation, project_dir = tmp_path / "source", tmp_path / "translation", tmp_path / "project"
    for folder in (source, translation, project_dir):
        folder.mkdir()
    (source / "Layout").mkdir()
    title = make_flim_3ds("ETC1A4", 32, 16, picture(32, 16))
    inner = sarc({"timg/Title_00.bflim": title, "timg/Other.bflim": make_flim_3ds("A4", 16, 8, picture(16, 8))})
    outer = sarc({"Title.szs": yaz0.compress(inner), "readme.txt": b"hello"})
    (source / "Layout" / "Pack.pack").write_bytes(yaz0.compress(outer))
    (source / "card.bti").write_bytes(make_bti(5, 24, 12, picture(24, 12)))
    pack = bytes(64) + make_bntx([("Name", 0x0B, picture(16, 8))]) + bytes(32)
    (source / "pack.bin").write_bytes(zlib.compress(pack))
    meta = {"source_path": str(source), "translation_path": str(translation)}
    descriptors = [
        {"label": "Title", "kind": "title_screen", "format": "bflim", "path": "Layout/*.pack",
         "member": "Title.szs/timg/Title_*.bflim"},
        {"label": "Card", "format": "bti", "path": ["missing/*.bti", "*.bti"]},
        {"label": "Packed", "format": "bntx", "path": "pack.bin",
         "params": {"compression": "zlib", "file_offset": 64, "file_size": len(pack) - 96}},
    ]
    return meta, descriptors, source, translation, project_dir


def test_sources_find_nested_members_globs_and_slices(project):
    meta, descriptors, *_ = project
    found = sources.resolve(descriptors, meta)
    assert [s.key for s in found] == ["Layout/Pack.pack/Title.szs/timg/Title_00.bflim", "card.bti", "pack.bin@40"]
    assert found[0].kind == "title_screen" and found[0].size == (32, 16) and found[0].pixel_format == "ETC1A4"
    assert found[0].export_name == "Layout_Pack.pack_Title.szs_timg_Title_00.bflim.png"
    assert found[2].name == "Name"


def test_writing_goes_to_the_translation_copy_and_revert_restores_the_texture_bytes(project):
    meta, descriptors, source, translation, _ = project
    found = sources.resolve(descriptors, meta)
    before = {p: p.read_bytes() for p in source.rglob("*") if p.is_file()}
    edited = [(s, Image.new("RGBA", s.size, (255, 255, 255, 255))) for s in found]
    assert len(sources.write_many(edited)) == 3
    assert {p: p.read_bytes() for p in source.rglob("*") if p.is_file()} == before     # the source is never written
    for s, _image in edited:
        assert s.read_current().image.getpixel((1, 1))[3] == 255
        assert s.read_original().image.tobytes() != s.read_current().image.tobytes()
    assert sources.write_many((s, None) for s in found)
    for s in found:      # the texture files come back byte for byte (archives around them may be laid out anew)
        original = sources.unwrap(Path(s.source_path).read_bytes(), s.member, s.params)[0]
        assert sources.unwrap(Path(s.translation_path).read_bytes(), s.member, s.params)[0] == original
    assert (translation / "card.bti").read_bytes() == (source / "card.bti").read_bytes()
    assert sources.write_many((s, s.read_current().image) for s in found) == []


def test_a_wrong_size_or_a_missing_translation_folder_is_refused(project):
    meta, descriptors, *_ = project
    found = sources.resolve(descriptors, meta)
    with pytest.raises(ValueError):
        sources.write_many([(found[1], picture(5, 5))])
    no_translation = sources.resolve(descriptors, {"source_path": meta["source_path"]})
    with pytest.raises(ValueError):
        no_translation[1].write(no_translation[1].read_current().image)


def test_a_file_opened_directly_is_written_in_place_and_remembers_its_original(tmp_path):
    path = tmp_path / "pack.ctpk"
    path.write_bytes(make_ctpk([("a.tga", 13, picture(16, 8)), ("b.tga", 11, picture(8, 8))]))
    found = sources.open_file(str(path))
    assert [s.name for s in found] == ["a.tga", "b.tga"]
    assert found[1].write(Image.new("RGBA", (8, 8), (255, 255, 255, 255)))
    assert found[1].read_current().image.getpixel((0, 0))[3] == 255
    assert found[1].read_original().image.tobytes() == picture(8, 8).convert("RGBA").tobytes() or         found[1].read_original().image.tobytes() != found[1].read_current().image.tobytes()
    archive = tmp_path / "Lyt.arc"
    archive.write_bytes(sarc({"timg/A.bflim": make_flim_3ds("A4", 16, 8, picture(16, 8)), "x.bin": b"x"}))
    assert [s.member for s in sources.open_file(str(archive))] == ["timg/A.bflim"]
    nothing = tmp_path / "nothing.bin"
    nothing.write_bytes(b"nope")
    with pytest.raises(ValueError):
        sources.open_file(str(nothing))


def test_status_file_round_trip(tmp_path):
    assert sources.load_status(str(tmp_path)) == {}
    sources.save_status(str(tmp_path), {"a": "redrawn", "b": "", "c": "checked"})
    assert sources.load_status(str(tmp_path)) == {"a": "redrawn", "c": "checked"}
    Path(sources.status_path(str(tmp_path))).write_text("{bad", encoding="utf-8")
    assert sources.load_status(str(tmp_path)) == {}


# -- the plugin hook and the plugins' texture lists -------------------------------------------------------


def test_plugin_hook_reads_texture_sources_json_next_to_the_rules(tmp_path, monkeypatch):
    import importlib
    import sys
    folder = tmp_path / "plug_textures"
    folder.mkdir()
    (folder / "__init__.py").write_text("", encoding="utf-8")
    (folder / "rules.py").write_text("from plugins.base_game_rules import BaseGameRules\n"
                                     "class GameRules(BaseGameRules):\n    pass\n", encoding="utf-8")
    described = [{"label": "Title", "format": "bti", "path": "title.bti"}]
    (folder / "texture_sources.json").write_text(json.dumps(described), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module("plug_textures.rules")
    try:
        assert module.GameRules().get_texture_sources() == described
    finally:
        sys.modules.pop("plug_textures.rules", None)
        sys.modules.pop("plug_textures", None)
    from plugins.base_game_rules import BaseGameRules
    assert BaseGameRules().get_texture_sources() == []


@pytest.mark.parametrize("path", sorted((ROOT / "plugins").glob("*/texture_sources.json")), ids=lambda p: p.parent.name)
def test_every_plugin_texture_list_is_well_formed(path):
    entries = json.loads(path.read_text(encoding="utf-8"))
    assert entries and isinstance(entries, list)
    known = set(texture_formats.formats())
    for entry in entries:
        assert entry["label"] and entry["path"] and entry["format"] in known, entry
        params = entry.get("params") or {}
        if entry["format"] == "raw":
            pixels.codec(params["pixel_format"])
            assert all("offset" in t for t in params.get("textures") or [params])
        if "compression" in params:
            assert params["compression"] in ("zlib", "gzip", "yar", "yaz0", "zstd", "none")


# -- Grezzo (OoT3D / MM3D): CTXB textures in ZAR/GAR archives, LzS compression ----------------------------


def make_ctxb(entries):
    """``[(name, (gl_format, gl_type), image)]`` -> a CTXB."""
    from core.texture_formats import ctxb
    chunk, count = 0x18, len(entries)
    data_at = chunk + 12 + 36 * count
    table, blobs = b"", b""
    for name, key, image in entries:
        blob = pixels.codec("pica:" + ctxb.FORMATS[key]).encode(image)
        table += struct.pack("<IHBBHHHHI", len(blob), 1, 0, 0, image.width, image.height, key[0], key[1], len(blobs))
        table += name.encode().ljust(16, b"\0")
        blobs += blob
    head = b"ctxb" + struct.pack("<IIIII", data_at + len(blobs), 1, 0, chunk, data_at)
    return head + b"tex " + struct.pack("<II", 12 + 36 * count, count) + table + blobs


def make_gar(files):
    """A GAR v2 of ``{name: bytes}`` (one type, data 0x80-aligned)."""
    names = list(files)
    info_at = 0x20
    names_at = info_at + 12 * len(names)
    name_blob, name_offsets = b"", []
    for name in names:
        name_offsets.append(names_at + len(name_blob))
        name_blob += name.encode() + b"\0"
    offsets_at = names_at + len(name_blob)
    offsets_at += -offsets_at % 4
    data_at = offsets_at + 4 * len(names)
    data_at += -data_at % 0x80
    body, starts = b"", []
    for name in names:
        body += bytes(-len(body) % 0x80)
        starts.append(data_at + len(body))
        body += files[name]
    head = bytearray(data_at)
    head[:4] = b"GAR\x02"
    struct.pack_into("<IHHIII", head, 4, data_at + len(body), 1, len(names), 0x1C, info_at, offsets_at)
    for i, name in enumerate(names):
        struct.pack_into("<III", head, info_at + 12 * i, len(files[name]), name_offsets[i], name_offsets[i])
        struct.pack_into("<I", head, offsets_at + 4 * i, starts[i])
    head[names_at:names_at + len(name_blob)] = name_blob
    return bytes(head) + body


def test_lzs_round_trip_with_back_references():
    from core.containers import grezzo
    rng = random.Random(9)
    for data in (b"", b"abc", bytes(rng.randrange(3) for _ in range(5000)), b"0123456789" * 700):
        packed = grezzo.lzs_compress(data)
        assert packed[:4] == grezzo.LZS_MAGIC and grezzo.lzs_decompress(packed) == data
    assert len(grezzo.lzs_compress(b"0123456789" * 700)) < 1000


def test_ctxb_in_a_compressed_gar_opens_and_writes_back(tmp_path):
    from core.containers import grezzo
    card = make_ctxb([("boss", (0x675B, 0x1401), picture(32, 16))])
    path = tmp_path / "boss.gar.lzs"
    path.write_bytes(grezzo.lzs_compress(make_gar({"tex/boss_euen.ctxb": card, "model/x.cmb": b"cmb" * 50})))
    found = sources.open_file(str(path))
    assert [(s.member, s.pixel_format, s.size) for s in found] == [("tex/boss_euen.ctxb", "ETC1A4", (32, 16))]
    container = grezzo.ZarContainer(grezzo.lzs_decompress(path.read_bytes()))
    assert container.pack() == grezzo.lzs_decompress(path.read_bytes())
    assert found[0].write(Image.new("RGBA", (32, 16), (255, 255, 255, 255)))
    archive = grezzo.ZarContainer(grezzo.lzs_decompress(path.read_bytes()))
    assert archive.read_file("model/x.cmb") == b"cmb" * 50
    assert found[0].read_current().image.getpixel((4, 4))[3] == 255
    assert found[0].read_original().image.getpixel((4, 4)) != (255, 255, 255, 255)


def test_ctxb_formats_round_trip():
    from core.texture_formats import ctxb
    data = make_ctxb([("a", (0x6758, 0x1401), picture(16, 8)), ("b", (0x675A, 0x1401), picture(8, 8))])
    textures = ctxb.read(data, {})
    assert [(t.name, t.pixel_format) for t in textures] == [("a", "LA8"), ("b", "ETC1")]
    assert ctxb.write(data, {0: textures[0].image, 1: textures[1].image}, {}) == data


def make_tpl(images):
    """``[(gx format id, image)]`` (no palettes) -> a TPL."""
    table = 0x0C
    heads_at = table + 8 * len(images)
    data_at = heads_at + 0x24 * len(images)
    data_at += -data_at % 0x20
    heads, blobs, table_bytes = b"", b"", b""
    for fmt, image in images:
        codec = pixels.codec(f"gx:{bti.FORMATS[fmt]}")
        table_bytes += struct.pack(">II", heads_at + len(heads), 0)
        heads += struct.pack(">HHII", image.height, image.width, fmt, data_at + len(blobs)) + bytes(0x24 - 12)
        blobs += codec.encode(_padded(image, codec))
    body = b"\x00\x20\xaf\x30" + struct.pack(">II", len(images), table) + table_bytes + heads
    return body + bytes(data_at - len(body)) + blobs


def test_tpl_images_read_and_write():
    from core.texture_formats import tpl
    data = make_tpl([(2, picture(16, 8)), (14, picture(16, 16, 5))])
    assert texture_formats.detect(data) == "tpl"
    textures = tpl.read(data, {})
    assert [(t.pixel_format, t.image.size) for t in textures] == [("IA4", (16, 8)), ("CMPR", (16, 16))]
    assert tpl.write(data, {0: textures[0].image, 1: textures[1].image}, {}) == data
    new = tpl.write(data, {1: Image.new("RGBA", (16, 16), (0, 0, 255, 255))}, {})
    assert tpl.read(new, {})[1].image.getpixel((9, 9))[2] > 240
    assert tpl.read(new, {})[0].image.tobytes() == textures[0].image.tobytes()
