"""J3D model textures (TEX1) and GBA tiles in a packed multiboot program: read, unedited write, edit, limits."""
import struct

import pytest
from PIL import Image, ImageDraw

from core import texture_formats
from core.containers import lz10
from core.texture_formats import gba, j3d
from test_core.test_texture_formats import make_bti, picture
from test_plugins.test_zelda_tingle import samples


def make_j3d(bti_files, names):
    """A J3D2bdl4 file with an INF1 stand-in and a TEX1 section holding these palette-less BTIs."""
    count = len(bti_files)
    heads, datas = [], []
    for data in bti_files:
        heads.append(bytearray(data[:0x20]))
        datas.append(data[0x20:])
    names_table = struct.pack(">HH", count, 0xFFFF)
    strings = b""
    for name in names:
        names_table += struct.pack(">HH", 0, 4 + 4 * count + len(strings))
        strings += name.encode() + b"\0"
    names_table += strings
    table_at = 0x20
    body_at = table_at + 32 * count
    blob = b""
    for index, head in enumerate(heads):
        struct.pack_into(">I", head, 0x1C, body_at + len(blob) - (table_at + 32 * index))   # from this header
        blob += datas[index]
    names_at = body_at + len(blob)
    tex1 = bytearray(b"TEX1" + bytes(4) + struct.pack(">HHII", count, 0xFFFF, table_at, names_at))
    tex1 += bytes(table_at - len(tex1)) + b"".join(heads) + blob + names_table
    tex1 += bytes(-len(tex1) % 32)
    struct.pack_into(">I", tex1, 4, len(tex1))
    inf1 = b"INF1" + struct.pack(">I", 0x20) + bytes(0x18)
    body = inf1 + bytes(tex1)
    return b"J3D2bdl4" + struct.pack(">II", 0x20 + len(body), 2) + bytes(0x10) + body


def test_j3d_lists_named_textures_and_writes_one_in_place():
    first, second = picture(16, 8), picture(8, 8)
    model = make_j3d([make_bti(5, 16, 8, first), make_bti(2, 8, 8, second)], ["logo_sub", "logo_sub_e"])
    assert texture_formats.detect(model) == "j3d"
    textures = j3d.read(model, {})
    assert [(t.name, t.pixel_format, t.image.size) for t in textures] == [
        ("logo_sub", "RGB5A3", (16, 8)), ("logo_sub_e", "IA4", (8, 8))]
    assert j3d.write(model, {0: textures[0].image, 1: textures[1].image}, {}) == model
    edited = textures[1].image.copy()
    ImageDraw.Draw(edited).rectangle((0, 0, 3, 3), fill=(255, 255, 255, 255))
    new = j3d.write(model, {1: edited}, {})
    assert len(new) == len(model) and new != model
    again = j3d.read(new, {})
    assert again[0].image.tobytes() == textures[0].image.tobytes()
    assert again[1].image.getpixel((1, 1)) == (255, 255, 255, 255)


def _gba_params(room):
    return {"program_offset": "0x1A4", "program_address": hex(samples.PROGRAM_ADDRESS), "tail_pointers": ["0x190", "0x198"],
            "textures": [{"name": "tiles", "block": hex(samples.PROGRAM_ADDRESS + samples.TILES_AT), "room": hex(room),
                          "offset": 0, "tiles": samples.GLYPHS, "columns": 8,
                          "palette": hex(samples.PROGRAM_ADDRESS + 0x780), "bank": 0}]}


def _client_with_palette():
    program = bytearray(samples.program())
    colours = [0] + [(i * 2) | (i * 2) << 5 | (i * 2) << 10 for i in range(1, 16)]   # greys, colour 15 near white
    struct.pack_into("<16H", program, 0x780, *colours)
    return samples.client(bytes(program))


def test_gba_tiles_read_in_their_palette_and_write_back_the_same_file():
    client = _client_with_palette()
    params = _gba_params(samples.TILE_ROOM)
    (texture,) = gba.read(client, params)
    assert texture.image.size == (64, 32) and texture.pixel_format == "GBA 4bpp"
    assert texture.image.getpixel((0, 0)) == (16, 16, 16, 255)          # nibble 1 of glyph 0
    assert gba.write(client, {0: texture.image}, params) == client


def test_gba_edit_keeps_untouched_nibbles_and_survives_a_reread():
    client = _client_with_palette()
    params = _gba_params(samples.TILE_ROOM)
    image = gba.read(client, params)[0].image.copy()
    ImageDraw.Draw(image).rectangle((8, 0, 9, 1), fill=(250, 250, 250, 255))
    new = gba.write(client, {0: image}, params)
    assert new != client
    back = gba.read(new, params)[0].image
    assert back.getpixel((8, 0)) == (246, 246, 246, 255)               # nearest grey: colour 15
    assert back.getpixel((16, 0)) == image.getpixel((16, 0))            # another tile is untouched
    assert texture_formats.read("gba", new, params)[0].image.size == (64, 32)


def test_gba_block_that_outgrows_its_room_is_refused():
    client = _client_with_palette()
    packed = len(lz10.compress(samples.tiles(), vram=True))
    params = _gba_params(packed)
    image = Image.effect_noise((64, 32), 90).convert("RGBA")
    with pytest.raises(ValueError, match="room"):
        gba.write(client, {0: image}, params)
