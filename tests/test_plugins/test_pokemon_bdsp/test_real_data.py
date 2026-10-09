"""Pokémon BDSP on the user's own dump (skipped without it): every English table saves back byte for byte and
rebuilds its labels from the editor text, every font packs back unchanged and keeps an edited glyph, every
texture PNG writes back unchanged, and the fonts' Ukrainian coverage is what the status file reports."""
import json
from pathlib import Path

import pytest
from PIL import ImageDraw

from core import font_formats, texture_formats
from core.font_formats import bfotf, sources
from plugins.pokemon_bdsp import msg
from plugins.pokemon_bdsp.rules import GameRules

WS = Path(r"E:\Emulators\RomHacking\Pokemon\Brilliant Diamond and Shining Pearl")
PLUGIN = Path(__file__).resolve().parents[3] / "plugins" / "pokemon_bdsp"
UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_every_table_saves_back_and_rebuilds_its_labels():
    files = sorted(_need(WS / "source" / "message").glob("english_*.bdmsg"))
    assert len(files) == 128
    labels = differ = 0
    for path in files:
        raw = path.read_bytes()
        rules = GameRules()
        blocks, names = rules.load_data_from_json_obj(raw)
        assert rules.save_data_to_json_obj(blocks, names) == raw, path
        table, indices, texts = msg.load_table(raw)
        for index, text in zip(indices, texts):
            label = table["labelDataArray"][index]
            words, tags = msg.text_words(text, msg.end_pattern(label))
            labels += 1
            same = (tags == label["tagDataArray"]
                    and [{k: v for k, v in w.items() if k != "strWidth"} for w in words]
                    == [{k: v for k, v in w.items() if k != "strWidth"} for w in label["wordDataArray"]])
            differ += not same
    assert labels == 42946
    assert differ <= 5          # a closing empty word after </size>: the rebuild ends on the tag itself


def _fonts():
    descriptors = json.loads((PLUGIN / "font_sources.json").read_text(encoding="utf-8"))
    return sources.resolve(descriptors, {"source_path": str(_need(WS / "source")), "translation_path": "",
                                         "is_directory_mode": True})


def test_every_font_packs_back_unchanged():
    found = _fonts()
    assert len(found) == 16
    for font in found:
        data = font.read_original()
        metadata, sheets = font_formats.extract(font.format, data, font.params)
        assert font_formats.pack(font.format, metadata, sheets, data, font.params) == data, font.label


def test_an_edited_sdf_glyph_reaches_the_atlas():
    font = next(f for f in _fonts() if "efigs_font (SDF" in f.label)
    data = font.read_original()
    metadata, sheets = font_formats.extract("tmp_sdf", data, {})
    glyph = font_formats.char_map(metadata)["e"]
    grid = metadata["GLY1"][0]
    x, y = (glyph % 32) * grid["cell_width"], (glyph // 32) * grid["cell_height"]
    ImageDraw.Draw(sheets[0]).rectangle((x + 6, y + 6, x + 14, y + 14), fill=(255, 255, 255, 255))
    edited = font_formats.pack("tmp_sdf", metadata, sheets, data, {})
    again, again_sheets = font_formats.extract("tmp_sdf", edited, {})
    assert again_sheets[0].crop((x + 6, y + 6, x + 15, y + 15)).getextrema()[3] == (255, 255)
    assert sources.split_pair(edited)[0] == sources.split_pair(data)[0]


def test_ukrainian_letters_of_the_english_fonts():
    static = json.loads(_need(WS / "source" / "font" / "efigs_font" / "efigs_font.json").read_text(encoding="utf-8"))
    codes = {char["m_Unicode"] for char in static["m_CharacterTable"]}
    assert not any(ord(c) in codes for c in UKRAINIAN)          # no Cyrillic in the static atlas
    fallback = bfotf.OpenType((WS / "source" / "font" / "efigs_font" / "FOT-UDKakugoC80Pro-DB.otf").read_bytes())
    missing = "".join(c for c in UKRAINIAN if ord(c) not in fallback.cmap())
    assert missing == "ҐЄІЇґєії"


def test_every_texture_png_writes_back_unchanged():
    files = sorted(_need(WS / "source" / "texture").rglob("*.png"))
    descriptors = json.loads((PLUGIN / "texture_sources.json").read_text(encoding="utf-8"))
    assert len(files) == len(descriptors) == 24
    for path in files:
        data = path.read_bytes()
        texture = texture_formats.read("png", data)[0]
        assert texture_formats.write("png", data, {0: texture.image}) == data
