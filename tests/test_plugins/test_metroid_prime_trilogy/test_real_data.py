"""Metroid Prime Trilogy on the user's own unpacked disc (skipped without it): every string table of the three
games and the menu saves back byte for byte and keeps an edit in every language, every font packs back unchanged
and keeps an edited glyph, and every texture format of the interface writes back unchanged and keeps an edit."""
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.font_formats import retro_font_gx
from core.texture_formats import bti, txtr_gx
from plugins.metroid_prime_trilogy.rules import GameRules
from plugins.metroid_prime_trilogy.strg import Strg

SOURCE = Path(r"E:\Emulators\RomHacking\Metroid\Prime Trilogy\source")
GAMES = ("MP1", "MP2", "MP3", "Menu")


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


@pytest.mark.parametrize("game", GAMES)
def test_every_string_table_saves_back_byte_for_byte(game):
    files = sorted(_need(SOURCE / game / "text").rglob("*.strg"))
    assert len(files) > 250
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path


def test_an_edited_string_keeps_its_tags_in_every_language():
    path = next(_need(SOURCE / "Menu" / "text").rglob("FrontEnd.*.strg"))
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(path.read_bytes())
    index = next(i for i, text in enumerate(blocks[0]) if text.startswith("{image="))
    blocks[0][index] = blocks[0][index] + " UA TEST"
    saved = rules.save_data_to_json_obj(blocks, names)
    table = Strg(saved)
    assert len(table.languages) == 6
    for language in table.languages:
        assert table.strings[language][index].startswith("&image=0x")
        assert table.strings[language][index].endswith(" UA TEST")
    assert GameRules().load_data_from_json_obj(saved)[0][0][index] == blocks[0][index]


def _fonts():
    return sorted(p for game in GAMES for p in (SOURCE / game / "font").glob("*.font")) if SOURCE.exists() else []


@pytest.mark.parametrize("path", _fonts(), ids=lambda p: f"{p.parent.parent.name}-{p.stem}")
def test_font_packs_back_and_keeps_an_edit(path):
    data = path.read_bytes()
    metadata, sheets = font_formats.extract("retro_font_gx", data)
    assert font_formats.pack("retro_font_gx", metadata, sheets, data) == data
    gly = metadata["GLY1"][0]
    char = "E" if "E" in font_formats.char_map(metadata) else next(iter(font_formats.char_map(metadata)))
    glyph = font_formats.char_map(metadata)[char]
    x = (glyph % gly["glyph_horizontal_count"]) * gly["cell_width"]
    y = (glyph // gly["glyph_horizontal_count"]) * gly["cell_height"]
    ImageDraw.Draw(sheets[0]).rectangle((x, y, x + 1, y + 1), fill=(255, 255, 255, 255))
    metadata["WID1"][0]["packets"][glyph]["width"] += 1
    edited = font_formats.pack("retro_font_gx", metadata, sheets, data)
    assert edited != data and len(edited) == len(data)
    again, sheets_again = font_formats.extract("retro_font_gx", edited)
    assert sheets_again[0].getpixel((x, y)) == (255, 255, 255, 255)
    assert again["WID1"][0]["packets"][glyph]["width"] == metadata["WID1"][0]["packets"][glyph]["width"]
    form, _tex = retro_font_gx.split(edited)
    assert form[:4] == b"FONT"


def _one_of_each_format():
    seen = {}
    for game in GAMES:
        for path in sorted(_need(SOURCE / game / "texture").rglob("*.txtr")):
            data = path.read_bytes()
            fmt = int.from_bytes(data[:4], "big")
            width, height = int.from_bytes(data[4:6], "big"), int.from_bytes(data[6:8], "big")
            if fmt not in seen and width * height <= 256 * 256:
                seen[fmt] = data
    return seen


def test_every_interface_texture_format_writes_back_and_keeps_an_edit():
    formats = _one_of_each_format()
    assert {0, 1, 2, 3, 4, 5, 7, 8, 9, 10} <= set(formats)
    for fmt, data in formats.items():
        texture = texture_formats.read("txtr_gx", data)[0]
        assert texture.pixel_format == bti.FORMATS[txtr_gx.FORMATS[fmt]]
        assert texture_formats.write("txtr_gx", data, {0: texture.image}) == data, fmt
        edited = texture.image.copy()
        ImageDraw.Draw(edited).rectangle((0, 0, 7, 7), fill=(255, 255, 255, 255))
        new = texture_formats.write("txtr_gx", data, {0: edited})
        assert len(new) == len(data)
        back = texture_formats.read("txtr_gx", new)[0].image
        assert back.getpixel((2, 2)) == edited.getpixel((2, 2)) or fmt in (4, 5), fmt   # C4 / C8: nearest colour
