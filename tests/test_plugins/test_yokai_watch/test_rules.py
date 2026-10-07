"""Yo-kai Watch plugin: cfg.bin round trips, editor text, hidden strings, layout; the real files when present."""
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.yokai_watch import tags
from plugins.yokai_watch.cfgbin import CfgBin
from plugins.yokai_watch.rules import category, layout_key
from plugins.yokai_watch.textfile import TextFile

from .samples import cfg_file, dialogue_file, noun_info

SOURCE = Path(r"E:\Emulators\RomHacking\Yo-kai Watch\Yo-kai Watch\3DS\source")
UKRAINIAN = "Ґанок і їжак — «є» п’ять"


def test_plugin_loads_and_validates():
    rules = check_loads("yokai_watch")
    assert rules.get_display_name() == "Yo-kai Watch"
    assert ".bin" in {e for f in rules.get_file_formats() for e in f.extensions}
    assert rules.get_capabilities() == {"speaker_attribution", "glossary_seed"}
    check_validator("yokai_watch")


def test_sample_round_trips_byte_for_byte():
    data = dialogue_file()
    check_round_trip("yokai_watch", data)
    rules = load_rules("yokai_watch")
    blocks, names = rules.load_data_from_json_obj(data)
    assert rules.save_data_to_json_obj(blocks, names) == data
    assert CfgBin(data).build() == data


def test_editor_text_has_real_line_breaks_and_curly_tags():
    blocks, _ = load_rules("yokai_watch").load_data_from_json_obj(dialogue_file())
    assert blocks[0][:2] == ["Hey there, {PNAME01}!", "Let's look for {CG}bugs{/C}\nby the river.{PAGE}Ready?"]


def test_japanese_leftovers_are_hidden_and_written_back_unchanged():
    data = dialogue_file()
    rules = load_rules("yokai_watch")
    blocks, names = rules.load_data_from_json_obj(data)
    assert len(blocks[0]) == 3 and "ダミー" not in blocks[0]
    blocks[0] = [UKRAINIAN, "Рядок 1\nрядок 2{PAGE}Готово?", "Привіт, {PNAME01}!"]
    saved = rules.save_data_to_json_obj(blocks, names)
    texts = [e.values[2] for e in CfgBin(saved).entries if e.name == "TEXT_INFO"]
    assert texts == [UKRAINIAN, "Рядок 1\\nрядок 2<PAGE>Готово?", "ダミー", "Привіт, <PNAME01>!"]


def test_identical_strings_share_one_slot_until_one_is_translated():
    data = dialogue_file()
    assert CfgBin(data).raw.count("Hey there".encode()) == 1
    rules = load_rules("yokai_watch")
    blocks, names = rules.load_data_from_json_obj(data)
    blocks[0][0] = "Привіт, {PNAME01}!"
    saved = rules.save_data_to_json_obj(blocks, names)
    texts = [e.values[2] for e in CfgBin(saved).entries if e.name == "TEXT_INFO"]
    assert texts[0] == "Привіт, <PNAME01>!" and texts[3] == "Hey there, <PNAME01>!"


def test_growth_moves_the_key_table_and_keeps_every_entry():
    data = dialogue_file()
    rules = load_rules("yokai_watch")
    blocks, names = rules.load_data_from_json_obj(data)
    blocks[0][1] = "Дуже довгий рядок, " * 20
    saved = rules.save_data_to_json_obj(blocks, names)
    assert len(saved) > len(data)
    again = CfgBin(saved)
    assert [e.name for e in again.entries] == [e.name for e in CfgBin(data).entries]
    assert again.encoding == "utf-8" and again.string_offset % 16 == 0


def test_every_save_is_built_from_the_source():
    source = dialogue_file()
    rules = load_rules("yokai_watch")
    blocks, names = rules.load_data_from_json_obj(source)
    blocks[0][0] = UKRAINIAN
    translated = rules.save_data_to_json_obj(blocks, names)
    fresh = load_rules("yokai_watch")
    fresh.prepare_save_context(SaveContext(existing_versions=lambda: iter([translated, source])))
    again, _ = fresh.load_data_from_json_obj(translated)
    assert fresh.save_data_to_json_obj(again, names) == translated


def test_nouns_show_name_and_plural_and_passwords_stay_hidden():
    data = cfg_file([("NOUN_INFO_BEGIN", [1]), noun_info(7, "Rusty Ring", "Rusty Rings"), ("NOUN_INFO_END", [])])
    assert TextFile(data).texts() == ["Rusty Ring", "Rusty Rings"]
    assert [row.param for row in TextFile(data).rows] == [5, 9]
    assert TextFile(dialogue_file(), "password_text_en.cfg.bin").rows == []


def test_not_a_table_gives_one_empty_block():
    assert load_rules("yokai_watch").load_data_from_json_obj(b"\x01\x02\x03\x04" * 8) == ([[]], {})


def test_tags_round_trip_and_describe():
    game = "Hey <PNAME01>!\\nNext<PAGE><CR>x</C> [g_coin]"
    assert tags.from_editor(tags.to_editor(game)) == game
    assert tags.describe("{PAGE}") == "Next page of the message window"
    assert tags.describe("[g_coin]") == "Inline picture 'g_coin'"
    assert tags.describe("plain") == ""


def test_categories_and_layout_keys():
    assert category("data/txt/ev/ev01_0080_m_en.cfg.bin", "TEXT_INFO", 2) == "dialogue"
    assert category("data/res/text/chara_text_en.cfg.bin", "NOUN_INFO", 5) == "name"
    assert category("data/res/text/item_text_en.cfg.bin", "NOUN_INFO", 9) == "plural"
    assert category("data/res/text/chara_text_en.cfg.bin", "TEXT_INFO", 2) == "medallium"
    assert layout_key("data/res/map/t101g00/t101g00_npc_text_en.cfg.bin", "TEXT_INFO", 2) == "dialogue|TEXT_INFO|2"
    assert layout_key("data/res/text/menu/shopmenu_text_en.cfg.bin", "TEXT_INFO", 2) == "shopmenu|TEXT_INFO|2"
    layout = load_rules("yokai_watch")._layouts("yw1")
    assert layout["dialogue|TEXT_INFO|2"]["lines"] == 2 and layout["dialogue|TEXT_INFO|2"]["max"] >= 300


def test_width_ignores_tags():
    rules = load_rules("yokai_watch")
    widths = {"a": {"width": 10}, "б": {"width": 7}}
    assert rules.calculate_string_width_override("a{PNAME01}б[g_coin]", widths) == 17


@pytest.mark.skipif(not SOURCE.is_dir(), reason="needs the Yo-kai Watch workspace (E:\\Emulators\\RomHacking\\Yo-kai Watch\\Yo-kai Watch\\3DS)")
def test_real_files_round_trip_byte_for_byte():
    files = sorted(SOURCE.rglob("*_en.cfg.bin"))
    assert len(files) == 2005
    rows = 0
    for path in files:
        data = path.read_bytes()
        text_file = TextFile(data, path.name)
        texts = text_file.texts()
        assert text_file.build(texts) == data, path
        assert all(tags.from_editor(t) == r.text for t, r in zip(texts, text_file.rows)), path
        rows += len(texts)
    assert rows > 40000


SOURCE_3 = Path(r"E:\Emulators\RomHacking\Yo-kai Watch\Yo-kai Watch 3\3DS\source")


@pytest.mark.skipif(not SOURCE_3.is_dir(), reason="needs the Yo-kai Watch 3 workspace (YOKAI_WATCH_3)")
def test_yokai_watch_3_files_round_trip_byte_for_byte():
    files = sorted(SOURCE_3.rglob("*_en.cfg.bin"))
    assert len(files) == 5641
    rows = 0
    for path in files:
        data = path.read_bytes()
        text_file = TextFile(data, path.name)
        assert text_file.build(text_file.texts()) == data, path
        rows += len(text_file.rows)
    assert rows > 130000
    layout = load_rules("yokai_watch")._layouts("yw3")
    assert layout["dialogue|TEXT_INFO|2"]["lines"] == 2
