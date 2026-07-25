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


def test_layout_contract_can_allow_minimal_line_and_window_expansion():
    translated = "one\ntwo\nthree\nfour\nfive"
    assert validate_translation_layout(
        "one\ntwo\nthree",
        translated,
        4,
        allow_line_expansion=True,
    ) == translated


def test_layout_contract_still_rejects_merged_lines_when_expansion_is_allowed():
    with pytest.raises(TranslationLayoutError):
        validate_translation_layout(
            "one\ntwo\nthree",
            "one two\nthree",
            4,
            allow_line_expansion=True,
        )
