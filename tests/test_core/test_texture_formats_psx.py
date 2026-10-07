"""PlayStation textures: CLUT colours, raw CI4/CI8, TIM, Vagrant Story GIM / HF1 / RLE, the text-save carry-over,
the Vagrant Story staff-roll font; every plugin texture of the real game when it is unpacked here."""
import json
import struct
from pathlib import Path

import pytest
from PIL import Image

from core import font_formats, texture_formats
from core.texture_formats import pixels, sources, vagrant

ROOT = Path(__file__).resolve().parents[2]
CLUT = [0x0000, 0x8000, 0x001F, 0x03E0, 0x7C00, 0x7FFF] + [0x4210 + i for i in range(10)]


def clut_bytes(values=CLUT) -> bytes:
    return struct.pack(f"<{len(values)}H", *values)


def indices_4bit(width, height, seed=1) -> bytes:
    return bytes(((x * seed + y) % 6) | (((x + 1) * seed + y) % 6) << 4 for y in range(height) for x in range(0, width, 2))


def paint(image: Image.Image, colour, box=(1, 1, 3, 3)) -> Image.Image:
    image = image.copy()
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            image.putpixel((x, y), colour)
    return image


def test_psx_colour_keeps_transparent_and_black_apart():
    decode, encode = pixels.psx_clut()
    assert decode(0) == (0, 0, 0, 0) and decode(0x8000) == (0, 0, 0, 255)
    assert encode(0, 0, 0, 255) == 0x8000 and encode(0, 0, 0, 0) == 0 and encode(255, 0, 0, 255) == 0x1F
    assert decode(0x7C00) == (0, 0, 255, 255)


def test_raw_psx_ci4_reads_writes_and_keeps_its_clut():
    data = clut_bytes() + indices_4bit(8, 4)
    params = {"pixel_format": "psx:CI4", "offset": 32, "tlut_offset": 0, "width": 8, "height": 4}
    image = texture_formats.read("raw", data, params)[0].image
    assert texture_formats.write("raw", data, {0: image}, params) == data
    edited = paint(image, (255, 0, 0, 255))
    out = texture_formats.write("raw", data, {0: edited}, params)
    assert out[:32] == data[:32]
    assert texture_formats.read("raw", out, params)[0].image.tobytes() == edited.tobytes()
    near = texture_formats.write("raw", data, {0: paint(image, (250, 4, 3, 255))}, params)
    assert near == out and near[:32] == data[:32]          # a new colour takes the nearest entry


def tim(bits, width, height, pixel_bytes, clut=None) -> bytes:
    flags = {4: 0, 8: 1, 16: 2}[bits] | (8 if clut else 0)
    out = struct.pack("<II", 0x10, flags)
    if clut:
        out += struct.pack("<I4H", 12 + len(clut), 0, 480, len(clut) // 2, 1) + clut
    words = width * bits // 16
    return out + struct.pack("<I4H", 12 + len(pixel_bytes), 0, 0, words, height) + pixel_bytes


def test_tim_files_back_to_back():
    first = tim(4, 8, 4, indices_4bit(8, 4), clut_bytes())
    second = tim(16, 2, 2, struct.pack("<4H", 0x8000, 0x1F, 0, 0x7FFF))
    data = first + second + b"IQ table"
    textures = texture_formats.read("tim", data)
    assert [t.image.size for t in textures] == [(8, 4), (2, 2)] and texture_formats.detect(data, "x") == "tim"
    assert textures[1].image.getpixel((1, 0)) == (255, 0, 0, 255)
    edited = paint(textures[0].image, (0, 255, 0, 255))
    out = texture_formats.write("tim", data, {0: edited, 1: textures[1].image})
    assert len(out) == len(data) and out[len(first):] == data[len(first):]
    assert texture_formats.read("tim", out)[0].image.tobytes() == edited.tobytes()


def test_one_tim_with_an_empty_clut_block_shows_grey_levels():
    data = struct.pack("<II", 0x10, 8) + struct.pack("<I4H", 12, 0, 480, 0, 0) + tim(4, 8, 4, indices_4bit(8, 4))[8:]
    texture, = texture_formats.read("tim", data)
    assert texture.name == "" and texture.pixel_format == "PSX 4-bit"
    grey = texture.image.getpixel((1, 0))
    assert grey[0] == grey[1] == grey[2] > 0
    assert texture_formats.write("tim", data, {0: texture.image}) == data


def gim(wide=False) -> bytes:
    """One layer of 2 x 1 cells over a sheet of one tile row (cell 2 empty)."""
    cell = 0x0200 | 1                              # page 0, tile row 0, column 1
    head = bytes((2, 1, 1, 20 if wide else 1)) + struct.pack("<HH", 1 if wide else 0, 0) + struct.pack("<2H", cell, 0)
    head += bytes(-len(head) % 4)
    rows = (20 if wide else 1) * 16
    colours = [0x8000, 0x7FFF, 0x1F] + [0x4210] * 61
    cluts = struct.pack(f"<{rows}H", *(colours * 5)[:rows])        # the 8-bit CLUT starts at entry 64
    sheet = bytes((x + y) % 3 for y in range(15) for x in range(128))
    return head + cluts + sheet


@pytest.mark.parametrize("wide", [False, True])
def test_vagrant_gim_layer_round_trip(wide):
    data = gim(wide)
    image = texture_formats.read("vs_gim", data)[0].image
    assert image.size == (128, 15) and image.getpixel((70, 0))[3] == 0          # the empty cell
    assert texture_formats.write("vs_gim", data, {0: image}) == data
    edited = paint(image, (255, 255, 255, 255), (2, 2, 9, 9))
    out = texture_formats.write("vs_gim", data, {0: edited})
    assert len(out) == len(data)
    assert texture_formats.read("vs_gim", out)[0].image.tobytes() == edited.tobytes()


def test_vagrant_help_sprite_round_trip():
    blocks = bytes(i % 3 for i in range(3 * 128))
    data = struct.pack("<II", 3, 16) + blocks + clut_bytes([0x8000, 0x7FFF, 0x1F] + [0] * 253)
    params = {"sprites": [{"name": "word", "width": 13, "height": 16, "clut": 0, "blocks": [2, 0]}]}
    image = texture_formats.read("vs_hf1", data, params)[0].image
    assert image.size == (13, 16) and texture_formats.write("vs_hf1", data, {0: image}, params) == data
    edited = paint(image, (255, 0, 0, 255), (9, 3, 12, 6))
    out = texture_formats.write("vs_hf1", data, {0: edited}, params)
    assert out[8 + 128:8 + 256] == data[8 + 128:8 + 256]       # block 1 is not the sprite's
    assert texture_formats.read("vs_hf1", out, params)[0].image.tobytes() == edited.tobytes()


def _fits(vram, room):
    try:
        vagrant._rle_encode(vram, room)
    except ValueError:
        return False
    return True


def rle_file(width=8, height=4):
    words = [vagrant.FILL] * (width * height // 2)
    words[3:6] = [0x7FFF001F, 0x03E07C00, 0x7FFF7FFF]
    vram = struct.pack(f"<{len(words)}I", *words)
    room = next(size for size in range(4, 4 * len(words) + 8, 4) if 4 * len(words) + 8 > size and _fits(vram, size))
    stream = vagrant._rle_encode(vram, room)                    # as tight as the game's own stream
    params = {"offset": 4, "end": 4 + len(stream), "width": width, "height": height,
              "textures": [{"name": "picture", "pixel_format": "psx:RGB555"},
                           {"name": "sprite", "pixel_format": "psx:4bpp", "x": 2, "y": 1, "width": 8, "height": 2}]}
    return b"HEAD" + stream + b"TAIL", params


def test_vagrant_rle_picture_keeps_its_place():
    data, params = rle_file()
    picture, sprite = texture_formats.read("vs_rle", data, params)
    assert picture.image.size == (8, 4) and sprite.image.size == (8, 2)
    assert texture_formats.write("vs_rle", data, {0: picture.image}, params) == data
    edited = picture.image.copy()
    edited.putpixel((6, 0), (0, 0, 255, 255))                 # a drawn pixel stays drawn: the size holds
    out = texture_formats.write("vs_rle", data, {0: edited}, params)
    assert len(out) == len(data) and out[-4:] == b"TAIL"
    assert texture_formats.read("vs_rle", out, params)[0].image.tobytes() == edited.tobytes()
    crowded = Image.new("RGBA", (8, 4), (8, 8, 8, 255))
    with pytest.raises(ValueError):
        texture_formats.write("vs_rle", data, {0: crowded}, params)


def test_text_save_keeps_the_pictures(tmp_path):
    source, translation = tmp_path / "src", tmp_path / "tr"
    source.mkdir()
    translation.mkdir()
    data = b"TEXT" + clut_bytes() + indices_4bit(8, 4)
    (source / "PROG.PRG").write_bytes(data)
    descriptor = {"label": "x", "format": "raw", "path": "PROG.PRG",
                  "params": {"pixel_format": "psx:CI4", "offset": 36, "tlut_offset": 4, "width": 8, "height": 4}}
    meta = {"source_path": str(source), "translation_path": str(translation)}
    found = sources.resolve([descriptor], meta)
    found[0].write(paint(found[0].read_original().image, (255, 0, 0, 255)))
    edited = (translation / "PROG.PRG").read_bytes()
    rebuilt = b"NEW!" + data[4:]                              # the text save starts from the source
    mine = sources.resolve_for_file([descriptor], meta, str(translation / "PROG.PRG"))
    assert len(mine) == 1 and not sources.resolve_for_file([descriptor], meta, str(translation / "OTHER.PRG"))
    assert sources.carry_over(mine, edited, rebuilt) == b"NEW!" + edited[4:]


def test_vagrant_staff_roll_font_sets():
    data = bytearray(0x40 + 224 + 256 * 224 // 2)
    data[0x40:0x40 + 224] = bytes(range(1, 225))
    texture = 0x40 + 224
    data[texture:] = bytes((i * 7) & 0xFF for i in range(len(data) - texture))
    data = bytes(data)
    for which in (0, 1):
        params = {"layout": "credits", "set": which, "texture": hex(texture), "widths": "0x40"}
        meta, sheets = font_formats.extract("vagrant", data, params)
        assert sheets[0].size == (256, 112) and meta["WID1"][0]["packets"][0]["width"] == 1 + 112 * which
        assert font_formats.pack("vagrant", meta, sheets, data, params) == data
        meta["WID1"][0]["packets"][5]["width"] = 0
        out = font_formats.pack("vagrant", meta, sheets, data, params)
        assert out[0x40 + 112 * which + 5] == 0 and sum(a != b for a, b in zip(out, data)) == 1


WS = Path(r"E:\Emulators\RomHacking\Vagrant Story\source")


@pytest.mark.skipif(not (WS / "GIM").is_dir(), reason="Vagrant Story not unpacked here")
def test_real_vagrant_textures_read_and_write_back(tmp_path):
    descriptors = json.loads((ROOT / "plugins/vagrant_story/texture_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(WS), "translation_path": str(tmp_path)})
    assert len(found) == 86
    for source in found:
        data = Path(source.source_path).read_bytes()
        texture = source.read_original()
        assert texture_formats.write(source.format, data, {source.index: texture.image}, source.params) == data
