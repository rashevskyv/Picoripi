"""Metroid Prime 4: Beyond on the user's own dump (skipped without it): every English table saves back byte for
byte, every font page packs back unchanged and keeps an edited glyph, every texture format the interface uses
writes back unchanged and keeps an edit, and the BakAI fonts carry the Ukrainian alphabet."""
import struct
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import font_formats, texture_formats
from core.font_formats import retro_font
from core.texture_formats import astc, txtr
from plugins.metroid_prime4.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Metroid\Prime 4 Beyond")
UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_every_english_table_saves_back_byte_for_byte():
    files = sorted(_need(WS / "source" / "text").glob("*.msbt"))
    assert len(files) == 98
    messages = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        messages += len(blocks[0])
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
    assert messages == 5792


def test_an_edited_message_keeps_its_tags():
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(_need(WS / "source" / "text" / "FrontEnd.msbt").read_bytes())
    index = next(i for i, label in rules._msbt.labels.items() if label == "FE_PressStart")
    assert blocks[0][index] == "PRESS {icon:123}"
    blocks[0][index] = "UA TEST {icon:123}"
    again = GameRules()
    assert again.load_data_from_json_obj(rules.save_data_to_json_obj(blocks, names))[0][0][index] == "UA TEST {icon:123}"


@pytest.mark.parametrize("name, pages", [("FONT_Geneva", 1), ("FONT_Primary", 5), ("FONT_Small", 5)])
def test_font_pages_pack_back_and_keep_an_edit(name, pages):
    data = _need(WS / "source" / "font" / f"{name}.rfont").read_bytes()
    assert font_formats.detect(data) == "retro_font"
    for page in range(pages):
        metadata, sheets = font_formats.extract("retro_font", data, {"page": page})
        assert font_formats.pack("retro_font", metadata, sheets, data, {"page": page}) == data
    metadata, sheets = font_formats.extract("retro_font", data, {"page": 0})
    gly = metadata["GLY1"][0]
    glyph = font_formats.char_map(metadata)["E"]
    x, y = (glyph % gly["glyph_horizontal_count"]) * gly["cell_width"], (glyph // gly["glyph_horizontal_count"]) * gly["cell_height"]
    ImageDraw.Draw(sheets[0]).rectangle((x, y, x + 3, y + 3), fill=(255, 255, 255, 255))
    edited = font_formats.pack("retro_font", metadata, sheets, data, {"page": 0})
    assert edited != data and len(edited) == len(data)
    _metadata, again = font_formats.extract("retro_font", edited, {"page": 0})
    assert again[0].getpixel((x + 1, y + 1))[3] == 255


def test_bakai_fonts_have_the_ukrainian_alphabet():
    for name in ("FONT_Geneva", "FONT_Primary", "FONT_Small"):
        data = _need(WS / "translation" / "font" / f"{name}.rfont").read_bytes()
        assert retro_font.split(data)[1], name
        metadata, _sheets = font_formats.extract("retro_font", data, {"page": 0})
        assert set(UKRAINIAN) <= set(font_formats.char_map(metadata)), name


def _one_of_each_format():
    seen = {}
    for path in sorted(_need(WS / "source" / "texture").rglob("*.txtr")):
        data = path.read_bytes()
        head = txtr._Txtr(data)
        if head.layers == 1 and head.format not in seen and head.width * head.height <= 512 * 512:
            seen[head.format] = data
    return seen


def test_every_interface_texture_format_writes_back_and_keeps_an_edit():
    formats = _one_of_each_format()
    assert {0, 13, 69, 72} <= set(formats)
    for fmt, data in formats.items():
        textures = texture_formats.read("txtr", data)
        if "not supported" in textures[0].pixel_format:
            continue
        image = textures[0].image
        assert texture_formats.write("txtr", data, {0: image}) == data, fmt
        edited = image.copy()
        ImageDraw.Draw(edited).rectangle((0, 0, 7, 7), fill=(255, 255, 255, 255))
        new = texture_formats.write("txtr", data, {0: edited})
        back = texture_formats.read("txtr", new)[0].image
        assert back.getpixel((2, 2))[:3] == (255, 255, 255), fmt
        if fmt in txtr.ASTC:
            assert txtr._Txtr(new).format == txtr.ASTC_TO[fmt]
            assert back.tobytes() == edited.tobytes()


def test_streamed_astc_textures_decode_without_error_blocks():
    checked = 0
    for path in sorted(_need(WS / "source" / "texture" / "Patch").glob("*.txtr")):
        data = path.read_bytes()
        head = txtr._Txtr(data)
        if head.format not in txtr.ASTC or head.width * head.height > 256 * 256:
            continue
        image = texture_formats.read("txtr", data)[0].image
        assert (255, 0, 255, 255) not in {pixel for pixel in image.getdata()}, path.name
        checked += 1
    assert checked >= 3


def test_astc_void_extent_and_reserved_blocks():
    colour = struct.pack("<4H", 0x1234, 0xABCD, 0xFF00, 0x8000)
    void = (0x1FC | 0xC00).to_bytes(2, "little") + b"\xff" * 6 + colour
    assert astc.decode_block(void, 4, 4) == bytes((0x12, 0xAB, 0xFF, 0x80)) * 16
    assert astc.decode_block(bytes(16), 4, 4) == bytes(astc.ERROR) * 16


def test_astc_image_size_is_cropped_to_the_texture():
    void = (0x1FC | 0xC00).to_bytes(2, "little") + b"\xff" * 6 + struct.pack("<4H", 0xFF00, 0, 0, 0xFF00)
    pixels = astc.decode(void * 4, 7, 5, 4, 4)
    assert Image.frombytes("RGBA", (7, 5), pixels).getpixel((6, 4)) == (255, 0, 0, 255)
