"""Atomic Bomberman plugin: the string table, placeholder and hint-row checks, build copies (synthetic tables only)."""
from plugins.atomic_bomberman.config import PROBLEM_DEFINITIONS, PROBLEM_HINT_ROW_WIDTH, PROBLEM_OPTIONS_ROW_WIDTH, PROBLEM_PLACEHOLDER
from plugins.atomic_bomberman.rules import GameRules, text_width_px


def load(table):
    rules = GameRules()
    blocks, _names = rules.load_data_from_json_obj(table)
    return rules, blocks


def test_load_and_save_keep_keys_and_values():
    table = {"Players": "Гравці", "{0} of {1}": "{1} з {0}", "Empty": ""}
    rules, blocks = load(table)
    assert blocks == [["Гравці", "{1} з {0}", ""]]
    assert rules.save_data_to_json_obj(blocks, {"0": "unused"}) == table


def test_an_edited_value_is_saved_under_its_key():
    rules, blocks = load({"A": "a", "B": "b"})
    blocks[0][1] = "bb"
    assert rules.save_data_to_json_obj(blocks, {}) == {"A": "a", "B": "bb"}


def test_input_that_is_not_a_string_table_gives_no_strings():
    rules, blocks = load(["not", "a", "table"])
    assert blocks == [[]]
    assert rules.save_data_to_json_obj(blocks, {}) == {}


def test_placeholder_mismatch_is_reported_and_reordering_is_not():
    rules, _ = load({"{0} of {1}": "{0} з {1}", "Players": "Гравці"})
    assert rules.get_text_fit_problems_for_string(0, 0, "{1} з {0}") == []
    assert rules.get_text_fit_problems_for_string(0, 0, "{0} з") == [PROBLEM_PLACEHOLDER]
    assert rules.get_text_fit_problems_for_string(0, 1, "Гравці") == []


def test_hint_row_is_measured_in_the_free_font():
    assert text_width_px("ab") == 16
    assert text_width_px("a b") == 8 + 6 + 8
    rules, _ = load({"Up/Down: select   Enter: play   Esc: back": "Вгору/Вниз: вибір   Enter: грати   Esc: назад",
                     "Gold Bomberman: ": "Золотий бомбермен: "})
    assert rules.get_text_fit_problems_for_string(0, 0, "Вгору/Вниз: вибір   Enter: грати   Esc: назад") == []
    too_wide = "Вгору/Вниз: " + "ж" * 70  # 81 characters: 648 px, more than the 580 px limit
    assert rules.get_text_fit_problems_for_string(0, 0, too_wide) == [PROBLEM_HINT_ROW_WIDTH]
    assert rules.get_text_fit_problems_for_string(0, 1, "ж" * 70) == []  # only the hint rows are measured


def test_options_language_row_is_measured_with_the_english_and_each_language_name():
    # Row limit 580 px; a letter is 8 px. "English" is 56 px.
    rules, _ = load({"Language: ": "Мова: ", "_language_name": "Українська", "Players": "Гравці"})
    assert rules.get_text_fit_problems_for_string(0, 0, "Мова: ") == []
    assert rules.get_text_fit_problems_for_string(0, 1, "Українська") == []
    # A label of 70 letters (560 px) and "English" (56 px) are more than the row holds.
    assert rules.get_text_fit_problems_for_string(0, 0, "м" * 70) == [PROBLEM_OPTIONS_ROW_WIDTH]
    assert rules.get_text_fit_problems_for_string(0, 2, "ж" * 90) == []  # other texts are not this row

    # A name typed in the editor is measured beside the label as it was loaded: "Мова: " and 58 letters
    # (510 px) with "English" (56 px) fit, 566 px; with "Українська" (80 px) they do not, 590 px.
    rules, _ = load({"Language: ": "Мова: " + "м" * 58, "_language_name": "Українська"})
    assert rules.get_text_fit_problems_for_string(0, 1, "Українська") == [PROBLEM_OPTIONS_ROW_WIDTH]
    assert rules.get_text_fit_problems_for_string(0, 1, "Укр") == []


def test_a_tag_in_the_editor_form_counts_as_its_placeholder():
    rules, _ = load({"{0}'s game": "Гра: {0}"})
    assert rules.get_text_fit_problems_for_string(0, 0, "Гра: [0]") == []
    assert rules.get_text_fit_problems_for_string(0, 0, "Гра: [1]") == [PROBLEM_PLACEHOLDER]


def test_the_platforms_are_pc_and_switch_and_each_target_names_one_of_them():
    rules = GameRules()
    assert [platform["id"] for platform in rules.get_platforms()] == ["pc", "switch"]
    platforms = {target["id"]: target["platforms"] for target in rules.get_build_targets()}
    assert platforms == {"lang_pc": ["pc"], "switch_sdmc": ["switch"]}


def test_both_checks_have_problem_definitions():
    assert PROBLEM_PLACEHOLDER in PROBLEM_DEFINITIONS
    assert PROBLEM_HINT_ROW_WIDTH in PROBLEM_DEFINITIONS
    assert PROBLEM_OPTIONS_ROW_WIDTH in PROBLEM_DEFINITIONS


def test_build_copies_the_table_for_the_pc_and_the_switch_export(tmp_path):
    translation = tmp_path / "translation"
    translation.mkdir()
    (translation / "uk.json").write_text('{"A": "а"}', encoding="utf-8")
    never_cancelled = lambda: False  # noqa: E731 - a plain callable is what the host passes
    progress = lambda percent, name: None  # noqa: E731
    rules = GameRules()
    ids = [target["id"] for target in rules.get_build_targets()]
    assert ids == ["lang_pc", "switch_sdmc"]

    pc_out = tmp_path / "pc"
    pc_out.mkdir()
    folder = rules.build_target("lang_pc", str(tmp_path), str(translation), str(pc_out), progress, never_cancelled)
    assert (pc_out / "lang" / "uk.json").read_text(encoding="utf-8") == '{"A": "а"}'
    assert folder.endswith("lang")

    switch_out = tmp_path / "switch"
    switch_out.mkdir()
    rules.build_target("switch_sdmc", str(tmp_path), str(translation), str(switch_out), progress, never_cancelled)
    assert (switch_out / "switch" / "atomic-bomberman" / "lang" / "uk.json").exists()
