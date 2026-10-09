"""Yo-kai Watch plugin: cfg.bin round trips, editor text, hidden strings, layout; the real files when present."""
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.yokai_watch import tags
from plugins.yokai_watch.cfgbin import CfgBin
from plugins.yokai_watch.rules import category, layout_key
from plugins.yokai_watch.textfile import TextFile

from .samples import cfg_file, dialogue_file, noun_info, text_info

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


def test_switch_games_show_the_japanese_lines_and_translate_them(tmp_path, monkeypatch):
    data = dialogue_file()
    text_file = TextFile(data, japanese=True)
    assert text_file.texts()[2] == "ダミー" and text_file.japanese_rows() == [2]
    rules = load_rules("yokai_watch")
    (tmp_path / "data/res/text").mkdir(parents=True)
    (tmp_path / "data/res/text/system_text_ja.cfg.bin").write_bytes(data)      # a Yo-kai Watch 1 (Switch) source
    monkeypatch.setattr(rules, "_source_root", lambda: tmp_path)
    blocks, names = rules.load_data_from_json_obj(data)
    assert len(blocks[0]) == 4 and rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][2] = "Манекен"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert [e.values[2] for e in CfgBin(saved).entries if e.name == "TEXT_INFO"][2] == "Манекен"


def test_a_shift_jis_table_becomes_utf8_when_ukrainian_goes_in():
    data = cfg_file([("TEXT_INFO_BEGIN", [2]), text_info(1, 0, "ダミー"), text_info(2, 0, "テスト"), ("TEXT_INFO_END", [])],
                    utf8=False)
    table = CfgBin(data)
    assert table.encoding == "shift-jis" and table.build() == data
    assert CfgBin(table.build({(1, 2): "Test"})).encoding == "shift-jis"     # ASCII fits: the table stays as it is
    again = CfgBin(table.build({(1, 2): UKRAINIAN}))
    assert again.encoding == "utf-8"
    assert [e.values[2] for e in again.entries if e.name == "TEXT_INFO"] == [UKRAINIAN, "テスト"]


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


SOURCE_3 = Path(r"E:\Emulators\RomHacking\Yo-kai Watch\Yo-kai Watch 3\source")
SOURCE_NX = Path(r"E:\Emulators\RomHacking\Yo-kai Watch\Yo-kai Watch\Switch\source")


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


@pytest.mark.skipif(not SOURCE_NX.is_dir(), reason="needs the Yo-kai Watch Switch workspace (YO_KAI_WATCH_SWITCH)")
def test_switch_files_round_trip_byte_for_byte_and_an_edit_keeps_the_other_lines():
    """Yo-kai Watch 1 (Switch): the Japanese tables with the English fan mod's text, some of them Shift-JIS under a
    UTF-8 footer, the mod's own tables with repeated strings."""
    from plugins.yokai_watch.speakers import Speakers, game_of
    assert game_of(SOURCE_NX) == "ywnx"
    files = sorted(SOURCE_NX.rglob("*_ja.cfg.bin"))
    assert len(files) == 2014
    rows = 0
    for path in files:
        data = path.read_bytes()
        text_file = TextFile(data, path.name)
        assert text_file.build(text_file.texts()) == data, path
        rows += len(text_file.rows)
    assert rows > 47000
    japanese = shift_jis = 0
    for path in files:
        data = path.read_bytes()
        text_file = TextFile(data, path.name, japanese=True)
        assert text_file.build(text_file.texts()) == data, path
        japanese += len(text_file.japanese_rows())
        if text_file.japanese_rows() and text_file.table.encoding != "utf-8" and not shift_jis:
            texts = text_file.texts()                       # a Japanese line of a Shift-JIS table translated
            texts[text_file.japanese_rows()[0]] = UKRAINIAN
            again = TextFile(text_file.build(texts), path.name, japanese=True)
            assert again.table.encoding == "utf-8" and again.texts() == texts, path
            shift_jis += 1
    assert japanese > 13000 and shift_jis
    path = SOURCE_NX / "data/res/map/t101g00/t101g00_npc_text_ja.cfg.bin"      # the mod repeats strings here
    text_file = TextFile(path.read_bytes(), path.name)
    texts = text_file.texts()
    texts[0] = UKRAINIAN
    again = TextFile(text_file.build(texts), path.name)
    assert again.texts() == texts
    speakers = Speakers(SOURCE_NX, SOURCE_NX.parent / "meta")
    event = SOURCE_NX / "data/txt/ev/ev01_0010_ja.cfg.bin"
    named = [speakers.speaker(event.relative_to(SOURCE_NX).as_posix(), r.text_id, r.number, r.text)
             for r in TextFile(event.read_bytes(), event.name).rows]
    assert "Whisper" in named or "Nate" in named


SOURCE_YW4 = Path(r"E:\Emulators\RomHacking\Yo-kai Watch\Yo-kai Watch 4\source")
SOURCE_YAY = Path(r"E:\Emulators\RomHacking\Yo-kai Watch\Yo-kai Academy Y\source")


def test_square_bracket_colours_and_pictures_of_the_switch_sequels_are_tags():
    assert tags.TAG_RE.fullmatch("[CR1]") and tags.TAG_RE.fullmatch("[C]") and tags.TAG_RE.fullmatch("[$gaiji_c1_2]")
    assert not tags.TAG_RE.fullmatch("[Mani]")
    assert tags.describe("[CG2]") == "Text colour until [C]"
    assert tags.describe("[$gaiji_c1_2]") == "Inline picture 'gaiji_c1_2'"
    assert category("data/common/text/ja/event/ev01_0300.cfg.bin", "TEXT_INFO", 2) == "dialogue"
    assert category("data/common/text/ja/purpose/c02_purpose_text.cfg.bin", "TEXT_INFO", 2) == "objective"


@pytest.mark.parametrize("source, game, tables, least_rows, least_japanese", [
    (SOURCE_YW4, "yw4", 2316, 38000, 500), (SOURCE_YAY, "yay", 1672, 19000, 12000)], ids=["yw4", "yay"])
def test_switch_sequel_files_round_trip_byte_for_byte_and_an_edit_keeps_the_other_lines(source, game, tables,
                                                                                         least_rows, least_japanese):
    """Yo-kai Watch 4++ / Yo-kai Academy Y (Switch): data/common/text/ja with the English fan mods' text."""
    if not (source / "data/common/text/ja").is_dir():
        pytest.skip(f"needs the workspace {source.parent}")
    from plugins.yokai_watch.speakers import game_of
    assert game_of(source) == game
    files = sorted((source / "data/common/text/ja").rglob("*.cfg.bin"))
    assert len(files) == tables
    rows = 0
    for path in files:
        data = path.read_bytes()
        text_file = TextFile(data, path.name)
        assert text_file.build(text_file.texts()) == data, path
        rows += len(text_file.rows)
    assert rows > least_rows
    japanese = 0
    for path in files:
        data = path.read_bytes()
        text_file = TextFile(data, path.name, japanese=True)
        assert text_file.build(text_file.texts()) == data, path
        japanese += len(text_file.japanese_rows())
    assert japanese > least_japanese
    path = source / "data/common/text/ja/system_text.cfg.bin"
    text_file = TextFile(path.read_bytes(), path.name)
    texts = text_file.texts()
    texts[0] = UKRAINIAN
    again = TextFile(text_file.build(texts), path.name)
    assert again.texts() == texts
