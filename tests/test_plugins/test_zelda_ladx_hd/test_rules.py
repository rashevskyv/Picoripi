"""Rules of Link's Awakening DX HD: load, save, layout keeping and runtime state (no Qt)."""
from plugins.zelda_ladx_hd.rules import GameRules
from plugins.zelda_ladx_hd import lng


FILE = (
    "// Language file\r\n"
    "menu_start Start Game\r\n"
    "\r\n"
    "menu_back Back\r\n"
)


def _load(rules, text):
    data, names = rules.load_data_from_json_obj(text)
    return data, names


def test_load_gives_one_block_per_entry_named_by_key():
    rules = GameRules()
    data, names = _load(rules, FILE)
    assert data == [["Start Game"], ["Back"]]
    assert names == {"0": "menu_start", "1": "menu_back"}


def test_save_without_edits_is_byte_exact():
    rules = GameRules()
    data, names = _load(rules, FILE)
    assert rules.save_data_to_json_obj(data, names) == FILE


def test_save_writes_edited_values_and_keeps_layout():
    rules = GameRules()
    data, names = _load(rules, FILE)
    data[1] = ["Назад"]
    assert rules.save_data_to_json_obj(data, names) == (
        "// Language file\r\nmenu_start Start Game\r\n\r\nmenu_back Назад\r\n"
    )


def test_value_with_real_line_break_is_refused():
    rules = GameRules()
    data, names = _load(rules, FILE)
    data[0] = ["two\nlines"]
    try:
        rules.save_data_to_json_obj(data, names)
    except ValueError as error:
        assert "one line" in str(error)
    else:
        raise AssertionError("a multi-line value must be refused")


def test_runtime_state_survives_export_and_restore():
    rules = GameRules()
    data, names = _load(rules, FILE)
    state = rules.export_runtime_state()
    fresh = GameRules()
    fresh.restore_runtime_state(state)
    assert fresh.save_data_to_json_obj(data, names) == FILE


def test_two_files_in_one_project_keep_their_own_layouts():
    rules = GameRules()
    eng_text = "// eng\r\na One\r\n"
    dialog_text = "b Two\n"
    eng_data, eng_names = _load(rules, eng_text)
    dialog_data, dialog_names = _load(rules, dialog_text)
    assert rules.save_data_to_json_obj(eng_data, eng_names) == eng_text
    assert rules.save_data_to_json_obj(dialog_data, dialog_names) == dialog_text


def test_unknown_layout_writes_entries_with_crlf():
    rules = GameRules()
    assert rules.save_data_to_json_obj([["x"], ["y"]], {0: "k1", 1: "k2"}) == "k1 x\r\nk2 y\r\n"


def test_reset_forgets_layouts():
    rules = GameRules()
    data, names = _load(rules, FILE)
    rules.reset_runtime_state()
    assert rules.save_data_to_json_obj(data, names) == "menu_start Start Game\r\nmenu_back Back\r\n"


def test_file_format_is_text_and_keeps_line_endings():
    rules = GameRules()
    (fmt,) = rules.get_file_formats()
    assert fmt.extensions == (".lng",)
    assert fmt.mode == "text"
    assert fmt.newline == ""


def test_spellcheck_ignore_pattern_matches_tags_and_escapes():
    import re
    pattern = re.compile(GameRules().get_spellcheck_ignore_pattern())
    assert pattern.search("Hi [NAME]") is not None
    assert pattern.search("line\\nnext") is not None
    assert lng.IGNORE_PATTERN == GameRules().get_spellcheck_ignore_pattern()
