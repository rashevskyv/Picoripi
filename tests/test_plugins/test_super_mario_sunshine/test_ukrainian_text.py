"""Ukrainian in Super Mario Sunshine on synthetic data: the shipped code map, BMG and executable text saved through it,
characters with no code refused, and the game fonts found in the unpacked tree."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.font_formats.sources import resolve
from plugins.super_mario_sunshine import build
from plugins.super_mario_sunshine.dol_text import STRINGS, apply_document, document_of
from plugins.super_mario_sunshine.rules import GameRules
from plugins.zelda_bmg import bmg_tool

from .test_bmg_text_first import bmg
from .test_dol_text import retail_dol

MAP_PATH = Path(GameRules.data_dir) / "translation_map.json"
UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
TEXT = "Привіт, Ґаджете! Їжак з’їв яєчню; пʼять ІЄЇ."


def _codes(text: str, rules: GameRules) -> bytes:
    return rules.encode_string_with_mapping(text).encode("cp1252")


def test_the_map_gives_every_ukrainian_letter_and_the_apostrophe_its_own_unused_code():
    table = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    assert set(table) == set(UKRAINIAN) | set(UKRAINIAN.lower()) | {"ʼ"}
    codes = [ord(value) for value in table.values()]
    assert all(len(value) == 1 for value in table.values()) and len(set(codes)) == len(codes) == 67
    # 0xA1-0xFF: one Latin-1 byte the font editor accepts as a slot; 0xA5 is the Y-button cell the game's text uses.
    assert all(0xA1 <= code <= 0xFF for code in codes) and 0xA5 not in codes


def test_ukrainian_text_is_written_as_one_byte_per_letter_and_read_back():
    rules = GameRules()
    encoded = _codes(TEXT, rules)
    assert len(encoded) == len(TEXT)
    assert encoded.startswith(bytes([0xCF, 0xF0, 0xE8, 0xE2, 0xB3, 0xF2]))      # Привіт on its cp1251 codes
    assert rules.decode_string_with_mapping(encoded.decode("cp1252")) == TEXT
    assert _codes("Mario, 1-UP!\n", rules) == b"Mario, 1-UP!\n"                  # the game's own text is unchanged


@pytest.mark.parametrize("char", ["ы", "Ё", "あ", "À"])
def test_a_character_with_no_code_is_refused_by_name_with_its_message(char):
    rules = GameRules()
    rules.load_data_from_json_obj(bmg(["Hello", "Second line"], leading_nul=True))
    with pytest.raises(ValueError) as error:
        rules.save_data_to_json_obj([["Привіт", f"Слово {char}"]], {})
    assert repr(char) in str(error.value) and "Message 1" in str(error.value)


def test_a_bmg_saved_with_ukrainian_holds_the_mapped_bytes_and_loads_back():
    rules = GameRules()
    original = bmg(["Hello", "Second line"], leading_nul=True)
    rules.load_data_from_json_obj(original)
    saved = rules.save_data_to_json_obj([["Hello", TEXT]], {})
    assert _codes(TEXT, GameRules()) + b"\0" in saved and b"?" not in saved
    data, _names = GameRules().load_data_from_json_obj(saved)
    assert data == [["Hello", TEXT]]
    tool = bmg_tool.BMGFile()
    tool.load(saved)
    assert tool.original_enc_val == 0


def test_a_shift_jis_message_file_takes_ukrainian_once_its_japanese_is_replaced():
    japanese = bmg(["Hello"], leading_nul=True).replace(b"Hello", "、、!".encode("shift_jis"))   # 0x81: not cp1252
    rules = GameRules()
    rules.load_data_from_json_obj(japanese)
    assert rules.last_loaded_bmg.encoding == "shift_jis"
    with pytest.raises(ValueError, match="has no code"):
        rules.save_data_to_json_obj([["、、!"]], {})
    rules.load_data_from_json_obj(japanese)
    saved = rules.save_data_to_json_obj([["Так"]], {})
    assert bytes([0xD2, 0xE0, 0xEA, 0]) in saved


@pytest.mark.usefixtures("synthetic_strings")
def test_executable_text_takes_ukrainian_and_refuses_a_character_with_no_code():
    dol = retail_dol()
    rules = GameRules()
    rules.prepare_save_context(SimpleNamespace(relative_path="sys/main_strings.dolstr"))
    texts, _names = rules.load_data_from_json_obj(document_of(dol))
    texts[0][1] = "Так"
    yes_at = next(offset for ident, offset, _r, _e in STRINGS if ident == "yes")
    patched = apply_document(dol, rules.save_data_to_json_obj(texts, {}))
    assert patched[yes_at:yes_at + 4] == bytes([0xD2, 0xE0, 0xEA, 0])
    texts[0][1] = "Ды"
    with pytest.raises(ValueError, match="main.dol/yes"):
        rules.save_data_to_json_obj(texts, {})


def test_the_fonts_are_found_in_the_archive_folders_and_written_to_the_translation(tmp_path):
    source, translation = tmp_path / "unpacked", tmp_path / "translation"
    font = source / "files" / "data" / "nintendo.szs" / "font" / "standard_fontex.bfn"
    font.parent.mkdir(parents=True)
    font.write_bytes(b"FONTbfn1" + bytes(24))
    found = resolve(GameRules().get_font_sources(), {"source_path": str(source), "translation_path": str(translation)})
    assert [f.name for f in found] == ["standard_fontex.bfn"]          # the subtitle font is absent here: skipped
    assert found[0].read_current() == font.read_bytes()
    found[0].write(b"FONTbfn1" + b"\1" * 24)
    rel = "files/data/nintendo.szs/font/standard_fontex.bfn"
    assert (translation / rel).read_bytes() == b"FONTbfn1" + b"\1" * 24 and font.read_bytes()[8:] == bytes(24)
    assert list(build.changed_files(source, translation)) == [rel]
    assert build.archive_split(rel) == ("files/data/nintendo.szs", "font/standard_fontex.bfn")
