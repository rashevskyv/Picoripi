"""Jak and Daxter font descriptors: the cell labels follow the game's glyph table, and an edited cell is written
to the translation copy only (a synthetic sheet, no game data)."""
import json
from pathlib import Path

from PIL import Image

from core.font_formats import extract, pack
from core.font_formats.sources import resolve

PLUGIN_FONTS = Path(__file__).resolve().parents[3] / "plugins" / "jak_and_daxter" / "font_sources.json"
LATIN = "textures/GAME/0196_ascii.12lo.png"


def _descriptors():
    return json.loads(PLUGIN_FONTS.read_text(encoding="utf-8"))


def test_latin_cells_follow_the_game_byte_rule():
    chars = next(d for d in _descriptors() if d["path"] == LATIN)["params"]["chars"]
    assert len(chars) == 160
    assert chars[49] == "A"            # game byte 0x41 = cell 0x41 - 16
    assert chars[53] == "E"
    assert chars[4] == ""              # the <TIL> token has no single character
    assert chars[20] == "ワ"           # game byte 0x24 is the katakana wa


def test_kana_sheet_cells_start_at_byte_144():
    kana = next(d for d in _descriptors() if d["path"].endswith("ascii.12hi.png"))
    assert kana["params"]["chars"][7] == "あ"     # game byte 0x97
    assert kana["params"]["chars"][16] == "か"    # game byte 0xa0


def test_edited_cell_goes_to_translation_only(tmp_path):
    source = tmp_path / "source" / "textures" / "GAME"
    source.mkdir(parents=True)
    translation = tmp_path / "translation"
    Image.new("RGBA", (128, 256), (0, 0, 0, 0)).save(source / "0196_ascii.12lo.png")
    descriptor = next(d for d in _descriptors() if d["path"] == LATIN)
    meta = {"source_path": str(tmp_path / "source"), "translation_path": str(translation),
            "is_directory_mode": True}
    (font,) = [s for s in resolve([descriptor], meta)]
    data = font.read_current()
    metadata, sheets = extract(font.format, data, font.params)
    assert pack(font.format, metadata, sheets, data, font.params) == data
    cell = sheets[0].convert("RGBA")
    cell.paste((255, 255, 255, 255), (108, 64, 120, 80))     # cell 49, the 'A'
    font.write(pack(font.format, metadata, [cell], data, font.params))
    assert font.translation_path.endswith("0196_ascii.12lo.png")
    assert Image.open(font.translation_path).convert("RGBA").getpixel((110, 70))[3] == 255
    assert Image.open(font.source_path).convert("RGBA").getpixel((110, 70))[3] == 0


def test_jak2_and_jak3_sheets_follow_their_code_prefixes():
    # 12 Latin: byte 16 + cell; 12 kana: code 01 (16 + cell); 24 kanji: code 02 (16 + cell)
    for tag in ("Jak 2", "Jak 3"):
        latin = next(d for d in _descriptors() if d["label"] == f"{tag} font 12 Latin (GAME font.12lo)")
        kana = next(d for d in _descriptors() if d["label"] == f"{tag} font 12 kana (GAME font.12hi)")
        kanji = next(d for d in _descriptors() if d["label"] == f"{tag} font 24 kanji (GAME font.24lo2)")
        assert latin["params"]["chars"][49] == "A"
        assert kana["params"]["chars"][7] == "あ"
        assert kanji["params"]["chars"][0] == "発"
