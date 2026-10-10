import pytest

from core.translation.layout_contract import (
    TranslationLayoutError,
    layout_signature,
    resolve_lines_per_window,
    validate_translation_layout,
)


def test_layout_contract_preserves_line_and_blank_line_shape():
    source = "First line\n\nThird line\n"
    translated = "Перший рядок\n\nТретій рядок\n"
    assert layout_signature(source) == {
        "line_count": 4,
        "blank_line_indices": [1, 3],
        "ends_with_newline": True,
    }
    assert validate_translation_layout(source, translated) == translated


@pytest.mark.parametrize("translated", [
    "Перший рядок Третій рядок\n",
    "Перший рядок\nТретій рядок\n\n",
    "Перший рядок\n\nТретій рядок",
])
def test_layout_contract_rejects_merged_moved_or_removed_newlines(translated):
    with pytest.raises(TranslationLayoutError):
        validate_translation_layout("First line\n\nThird line\n", translated)


def test_layout_signature_reports_visible_lines_and_dialogue_windows():
    assert layout_signature("one\ntwo\nthree\n", 4) == {
        "line_count": 4,
        "blank_line_indices": [3],
        "ends_with_newline": True,
        "visible_line_count": 3,
        "lines_per_window": 4,
        "window_count": 1,
    }
    assert layout_signature("one\ntwo\nthree\nfour\nfive", 4)["window_count"] == 2


def test_resolve_lines_per_window_prefers_per_string_layout():
    class Rules:
        def get_string_layout(self, block_idx, string_idx):
            assert (block_idx, string_idx) == (2, 3)
            return {"lines_per_page": 4}

    class Window:
        current_game_rules = Rules()
        lines_per_page = 7

    assert resolve_lines_per_window(Window(), 2, 3) == 4


def test_layout_contract_can_allow_line_and_window_expansion():
    translated = "one\ntwo\nthree\nfour\nfive"
    assert validate_translation_layout("one\ntwo\nthree", translated, 4, allow_reflow=True) == translated


def test_a_reflow_may_merge_lines_the_translation_does_not_need():
    """Live run 2026-10-03: a three-line source rendered in two lines cost a whole chunk four times."""
    source = "But the moment Darbus reached out\nand touched the treasure...everything\nwent wrong."
    translated = "Але в ту мить, коли Дарбус простягнув руку\nі торкнувся скарбу... все пішло шкереберть."
    assert validate_translation_layout(source, translated, 3, allow_reflow=True) == translated
    with pytest.raises(TranslationLayoutError):
        validate_translation_layout(source, translated, 3)


@pytest.mark.parametrize("translated", [
    "Перший рядок Третій рядок\n",          # the page break is gone
    "Перший рядок\n\nТретій рядок",         # the trailing newline is gone
])
def test_a_reflow_keeps_page_breaks_and_the_trailing_newline(translated):
    with pytest.raises(TranslationLayoutError):
        validate_translation_layout("First line\n\nThird line\n", translated, allow_reflow=True)


def test_a_line_left_in_the_source_language_is_refused():
    from core.translation.layout_contract import check_translated

    source = "You bought a {Color:Red}slice of pie{Color:White}! One bite,\nand you're in heaven!"
    with pytest.raises(TranslationLayoutError, match="item 12 is not translated"):
        check_translated(source, "You bought a {Color:Red}шматочок пирога{Color:White}! One bite,\nand you're in heaven!",
                         item_id=12)
    check_translated(source, "Ти купив {Color:Red}шматочок пирога{Color:White}! Один шматок,\nі ти в раю!")
    check_translated("Hello, Link!", "Hello, Link!")            # too short to judge: names, greetings, codes


def test_check_tags_kept_refuses_a_lost_added_or_changed_tag():
    from core.translation.layout_contract import TranslationLayoutError, check_tags_kept
    source = "Hi, {playerName}!{delay:8} Ready?{menu5:0}\nYes\nNo"
    check_tags_kept(source, "{delay:8}Привіт, {playerName}! Готовий?{menu5:0}\nТак\nНі")   # order may change
    for reply in ("Привіт! Готовий?{menu5:0}\nТак\nНі",                          # lost
                  "Привіт, {playerName}!{delay:8}{delay:8} Готовий?{menu5:0}\nТак\nНі",   # added
                  "Привіт, {PlayerName}!{delay:8} Готовий?{menu5:0}\nТак\nНі"):  # changed
        with pytest.raises(TranslationLayoutError):
            check_tags_kept(source, reply)
