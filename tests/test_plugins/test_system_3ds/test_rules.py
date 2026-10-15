"""3DS system plugin on synthetic 3ds-ua files: which column a parse fills, byte-exact saves, ids, widths, reference."""
import difflib
import json

import pytest

from core.formats import SaveContext, translation_parse
from core.project_library import plugin_facts
from plugins.system_3ds import rules as system_rules
from plugins.system_3ds.rules import GameRules, read_entries

# Indented, CRLF, a comment, a Russian column, an extra key the save must keep, a null English.
STRINGS = (
    '{\r\n  "_comment": "kept as it is",\r\n'
    '  "lau_title_menu": {\r\n    "en": "HOME Menu",\r\n    "ru": "Меню HOME",\r\n    "ua": "Меню HOME"\r\n  },\r\n'
    '  "lau_1b_start": {\r\n    "en": "Open",\r\n    "ua": "{t:1.0:6200}Запустити{/t:1.0}"\r\n  },\r\n'
    '  "keytop": {\r\n    "en": "абв",\r\n    "ua": "абв",\r\n    "ua_real": "абвґ"\r\n  },\r\n'
    '  "no_english": {\r\n    "en": null,\r\n    "ua": ""\r\n  }\r\n}\r\n'
).encode("utf-8")
# One entry per line, LF: the area files of the owner's repo.
COMPACT = (
    '{\n  "_comment": "regions",\n'
    '  "9": { "en": "Moscow City", "ru": "Москва", "ua": "Москва" },\n'
    '  "10": { "en": "Adygey", "ru": "Республика Адыгея", "ua": "Республіка Адигея" }\n}\n'
).encode("utf-8")
LAYOUT = json.dumps({"up_LZ.bin": {"./blyt/StartTopEU_U_00.bclyt": {"TextBoxTitle_00": [
    {"en": "Select a language.", "ru": "Выберите язык.", "ua": "Виберіть мову."}]}}},
    ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _loaded(*files):
    """A plugin after the host's project load: every source parsed, then every translation in the translation role."""
    rules = GameRules()
    rules.reset_runtime_state()
    originals = [rules.load_data_from_json_obj(raw)[0][0] for raw in files]
    with translation_parse(rules):
        translations = [rules.load_data_from_json_obj(raw)[0][0] for raw in files]
    return rules, originals, translations


def _save(rules, raw, texts):
    rules.prepare_save_context(SaveContext(block_indices=[0], existing_versions=lambda: iter([raw])))
    return rules.save_data_to_json_obj([texts])


def test_the_source_role_gives_the_english_original_and_the_translation_role_the_ukrainian():
    rules, originals, translations = _loaded(STRINGS)
    assert originals == [["HOME Menu", "Open", "абв", ""]]
    assert translations == [["Меню HOME", "{t:1.0:6200}Запустити{/t:1.0}", "абв", ""]]
    assert len(rules.export_runtime_state()["blocks"]) == 1  # a translation parse adds no block
    assert rules.load_data_from_json_obj(STRINGS)[0][0][0] == "HOME Menu"  # the role is back to source


def test_the_project_sync_parse_of_json_names_one_block_and_changes_nothing():
    rules = GameRules()
    assert rules.load_data_from_json_obj(json.loads(STRINGS)) == ([], {})
    assert rules.export_runtime_state() == {"blocks": []}


@pytest.mark.parametrize("raw", [STRINGS, COMPACT, LAYOUT])
def test_a_save_without_a_change_gives_back_the_same_bytes(raw):
    rules, _, translations = _loaded(raw)
    assert _save(rules, raw, translations[0]) == raw


@pytest.mark.parametrize("raw, index", [(STRINGS, 1), (COMPACT, 1), (LAYOUT, 0)])
def test_an_edit_changes_only_that_ua_value(raw, index):
    rules, _, translations = _loaded(raw)
    texts = list(translations[0])
    texts[index] = "Нове \"значення\"\nз рядком"
    saved = _save(rules, raw, texts)
    before, after = json.loads(raw), json.loads(saved)
    entries = read_entries(saved.decode("utf-8"))
    assert entries[index].ua == texts[index]
    assert [entry.ua for entry in entries] == texts
    changed = [line for line in difflib.ndiff(raw.decode("utf-8").splitlines(), saved.decode("utf-8").splitlines())
               if line[:1] in "+-"]
    assert len(changed) == 2  # one line out, one line in
    if raw is STRINGS:
        assert after["keytop"] == before["keytop"] and after["_comment"] == before["_comment"]
        assert after["lau_1b_start"]["en"] == "Open" and b"\r\n" in saved


def test_a_save_refuses_a_file_that_gained_strings_outside_picoripi():
    rules, _, translations = _loaded(COMPACT)
    with pytest.raises(ValueError, match="changed outside Picoripi"):
        _save(rules, STRINGS, translations[0])


def test_string_ids_are_the_label_or_the_pane_path():
    rules, _, _ = _loaded(STRINGS, LAYOUT)
    assert rules.string_key(0, 1) == "lau_1b_start"
    assert rules.string_key(1, 0) == "up_LZ.bin/./blyt/StartTopEU_U_00.bclyt/TextBoxTitle_00#0"
    assert rules.get_scene_context_for_string(1, 0) == {"resource": rules.string_key(1, 0)}
    assert rules.string_key(2, 0) is None


def test_only_string_and_layout_files_are_blocks():
    rules = GameRules()
    assert rules.includes_source_file("strings/home_menu/message__menu_msbt_LZ.json")
    assert rules.includes_source_file("layouts/system_settings.json")
    assert not rules.includes_source_file("strings/system_settings/_all_langs.json")
    assert not rules.includes_source_file("manuals/sound.json")
    assert not rules.includes_source_file("homoglyphs.json")


def test_widths_follow_the_scale_tags_and_take_the_widest_line():
    rules = GameRules()
    widths = rules._widths_table()
    word = widths.glyph("З") + widths.glyph("а")
    assert system_rules.line_widths("За", widths) == [pytest.approx(word)]
    # {t:1.0:3200} is 50 %; {/t:1.0} closes the run; tags draw nothing.
    assert system_rules.line_widths("{t:1.0:3200}За{/t:1.0}За", widths) == [pytest.approx(word * 1.5)]
    assert rules.calculate_string_width_override("За\nЗаЗа", {}) == round(word * 2)


def test_only_a_string_with_a_known_pane_box_has_a_limit():
    rules, _, _ = _loaded(STRINGS, LAYOUT)
    assert rules.get_string_layout(0, 0) is None
    # The pane is 194 px wide at font size 18.75: 194 * 25 / 18.75 font pixels.
    assert rules.get_string_layout(1, 0) == {"max_width": 258, "warn_width": 258}


def test_the_reference_is_the_russian_column_of_the_matching_file(tmp_path):
    folder = tmp_path / "strings" / "home_menu"
    folder.mkdir(parents=True)
    (folder / "message__menu.json").write_bytes(STRINGS)
    (tmp_path / "layouts").mkdir()
    (tmp_path / "layouts" / "system_settings.json").write_bytes(LAYOUT)
    rules, _, _ = _loaded(LAYOUT, STRINGS)
    assert rules.load_reference_patch(str(tmp_path)) == {(0, 0): "Выберите язык.", (1, 0): "Меню HOME"}


def test_the_project_manager_counts_ukrainian_against_english_in_a_same_folder_project(tmp_path):
    (tmp_path / "strings" / "area").mkdir(parents=True)
    (tmp_path / "strings" / "area" / "EU_100.json").write_bytes(COMPACT)
    project = tmp_path / "project.uiproj"
    project.write_text(json.dumps({
        "plugin_name": "system_3ds", "metadata": {"source_path": str(tmp_path), "translation_path": str(tmp_path)},
        "blocks": [{"source_file": "strings/area/EU_100.json", "translation_file": "strings/area/EU_100.json"}]}),
        encoding="utf-8")
    # "Москва" and "Республіка Адигея" differ from the English: both count as translated.
    assert plugin_facts.count_project(project)["counts"] == {"lines": 2, "needs_translation": 2, "translated": 2}
