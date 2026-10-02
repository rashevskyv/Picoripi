"""The engine's request rules: fixed text in the system prompt, data only in the user message."""
from unittest.mock import MagicMock

import pytest

from handlers.translation.prompt_composer import AIPromptComposer
from handlers.translation.prompt_composer.instructions import (
    ENGINE_MARKER,
    append_engine_rules,
    batch_rules,
    single_rules,
    strip_engine_rules,
)
from utils.utils import resolve_target_language_prompt


@pytest.fixture
def composer(mock_mw):
    main_handler = MagicMock()
    main_handler.mw = mock_mw
    main_handler._glossary_manager.get_relevant_terms.return_value = []
    mock_mw.current_game_rules.get_display_name.return_value = "Test Game"
    mock_mw.current_game_rules.get_text_representation_for_editor.side_effect = lambda text: text
    mock_mw.data_store.block_names = {"0": "Block 0"}
    mock_mw.data_store.reference_languages_data = {}
    mock_mw.data_store.reference_data = {}
    mock_mw.default_tag_mappings = {"{Color:Red}": "{0}"}
    mock_mw.target_language = "Ukrainian"
    composer = AIPromptComposer(main_handler)
    composer.story_context.get_mempalace_client = lambda: None
    composer.story_context.fetch_story_context = lambda *args, **kwargs: None
    return composer


def test_two_different_chunks_get_the_same_system_prompt(composer):
    plain = [{"id": 0, "text": "Hello."}, {"id": 1, "text": "Bye."}]
    tagged = [{"id": 2, "text": "Take the {Color:Red}sword{Color:White}!"}]
    items = plain + tagged

    system_a, user_a, _ = composer.compose_batch_request("SysPrompt", plain, items, block_idx=0, mode_description="m")
    system_b, user_b, _ = composer.compose_batch_request("SysPrompt", tagged, items, block_idx=0, mode_description="m")

    assert system_a == system_b
    for user in (user_a, user_b):
        assert "INSTRUCTIONS:" not in user
        assert user.split("\n\n", 1)[1].startswith("JSON DATA TO PROCESS:\n{")
    assert "tag_alias_legend" in user_b and "tag_alias_legend" not in user_a


def test_single_string_system_prompt_does_not_depend_on_the_string(composer):
    system_a, user_a = composer.compose_messages(
        "SysPrompt", "One line", block_idx=0, string_idx=0, expected_lines=1, mode_description="m")
    system_b, user_b = composer.compose_messages(
        "SysPrompt", "Three\nwhole\nlines {Color:Red}", block_idx=0, string_idx=1, expected_lines=3, mode_description="m")

    assert system_a == system_b
    assert "CONTEXT PRIORITY" in system_a and 'in the form {"translation":"..."}' in system_a
    assert "GLOSSARY IS MANDATORY" not in user_a


@pytest.mark.parametrize("rule", [
    "Translate the \"text\" field", "translated_strings", "LAYOUT PRIORITY", "GLOSSARY IS MANDATORY",
    "story_context_ref", "role_instruction", "TRANSCRIPTION RULES", "DIALOGUE FLOW",
    "ADDRESSEE", "TAG ALIAS LEGEND", "ANCHORED TAGS", "REFERENCE TRANSLATIONS", "OUTPUT SHAPE IS IMMUTABLE",
])
def test_batch_rules_cover_every_instruction_the_user_message_used_to_carry(rule):
    assert rule in batch_rules("SysPrompt")


def test_optional_fields_are_only_mentioned_conditionally():
    rules = batch_rules("SysPrompt")
    for field in ('"story_context_ref"', '"dialogue_flow"',
                  '"addressee"', '"tag_alias_legend"', '"reference_translations"'):
        lines = [line for line in rules.splitlines() if field in line]
        assert any(" If " in line or "present" in line for line in lines), field


def test_cohesion_sentence_is_not_sent_twice():
    shipped = "Rules...\n\nIMPORTANT: All text chunks you receive in a single request are part of a larger, cohesive block of text."
    assert "cohesive block of text" not in batch_rules(shipped)
    assert "cohesive block of text" in batch_rules("A plugin prompt without it")


def test_transcription_examples_are_only_given_for_the_language_they_belong_to():
    rules = append_engine_rules("SysPrompt", batch_rules("SysPrompt"))
    assert "Hyrule -> Гайрул" in resolve_target_language_prompt(rules, "Ukrainian")
    spanish = resolve_target_language_prompt(rules, "Spanish")
    assert "Гайрул" not in spanish and "IF_TARGET_LANG" not in spanish
    assert "into Spanish" in spanish


def test_rules_are_appended_once_and_never_saved():
    once = append_engine_rules("My prompt", single_rules("translation"))
    assert once.count(ENGINE_MARKER) == 1
    # A prompt that came back from the editor already carries the rules.
    assert append_engine_rules(once, single_rules("translation")) == once
    assert strip_engine_rules(once) == "My prompt"
    assert strip_engine_rules("No engine rules here") == "No engine rules here"


def test_each_single_request_type_has_its_own_rules():
    translation = single_rules("translation")
    variations = single_rules("variation_list")
    selection = single_rules("variation_list", has_selection=True)
    notes = single_rules("glossary_notes_variation")
    assert 'in the form {"translation":"..."}' in translation
    assert "10 different" in variations and "selected text segment" in selection
    assert "{{TERM}}" in notes and "CONTEXT PRIORITY" not in notes
    assert len({translation, variations, selection, notes}) == 4


# --- rows around the chunk --------------------------------------------------

def _data_composer(composer, blocks):
    composer.mw.data_store.data = blocks
    composer.main_handler.data_processor.get_current_string_text.side_effect = (
        lambda block, row: (f"T{block}.{row}" if row % 2 else "", False)
    )
    composer.data_processor = composer.main_handler.data_processor
    return composer


def test_surrounding_rows_follow_the_real_position_not_the_chunk_numbering(composer):
    blocks = [[f"b{b} row {r}" for r in range(60)] for b in range(6)]
    _data_composer(composer, blocks)
    items = [{"id": i, "text": f"sel {i}"} for i in range(3)]
    temp_id_map = {0: (5, 40), 1: (5, 41), 2: (5, 42)}

    _, user, _ = composer.compose_batch_request(
        "SysPrompt", items, items, block_idx=5, mode_description="selection", temp_id_map=temp_id_map)

    for row in (37, 38, 39, 43, 44, 45):
        assert f"[Row #{row}] (Original): \\\"b5 row {row}\\\"" in user
    assert "(Translation): \\\"T5.37\\\"" in user          # a neighbour that is already translated
    for row in (0, 1, 2, 3, 36, 40, 41, 42, 46):
        assert f"[Row #{row}]" not in user


def test_surrounding_rows_for_a_chunk_that_spans_two_blocks(composer):
    blocks = [[f"b{b} row {r}" for r in range(20)] for b in range(3)]
    _data_composer(composer, blocks)
    items = [{"id": i, "text": f"sel {i}"} for i in range(2)]
    # A project-wide run: synthetic block index, real places in the map (string keys as in saved progress).
    temp_id_map = {"0": (0, 5), "1": (2, 10)}

    _, user, _ = composer.compose_batch_request(
        "SysPrompt", items, items, block_idx=999997, mode_description="story first", temp_id_map=temp_id_map)

    assert user.count("--- Dialogue BEFORE this chunk (block ") == 2
    assert "b0 row 4" in user and "b0 row 6" in user
    assert "b2 row 9" in user and "b2 row 11" in user
    assert "b1 row" not in user


def test_surrounding_rows_of_a_plain_block_run(composer):
    _data_composer(composer, [[f"row {r}" for r in range(10)]])
    items = [{"id": 0, "text": "row 0"}, {"id": 1, "text": "row 1"}]

    _, user, _ = composer.compose_batch_request("SysPrompt", items, items, block_idx=0, mode_description="block")

    assert "--- Dialogue BEFORE" not in user          # nothing precedes row 0
    assert "--- Dialogue AFTER this chunk ---" in user
    assert "row 2" in user and "row 4" in user and "row 5" not in user


# --- payload size (WP2 2.5) --------------------------------------------------

def _payload(user):
    import json
    return json.loads(user.split("JSON DATA TO PROCESS:\n", 1)[1])


def test_a_plain_item_carries_only_what_is_specific_to_it(composer):
    composer.mw.lines_per_page = 3
    composer.mw.string_metadata = {}
    composer.mw.line_width_warning_threshold_pixels = 280
    composer.mw.game_dialog_max_width_pixels = 300
    composer.mw.current_game_rules.get_string_layout.return_value = None
    composer.mw.current_game_rules.get_preview_window_style.return_value = None
    composer.mw.current_game_rules.get_translation_context_for_string.return_value = {}
    composer.mw.current_game_rules.get_addressee_for_string.return_value = None
    composer.mw.current_game_rules.get_ai_flow_context_for_string.return_value = None
    composer.mw.current_game_rules.get_ai_flow_overview.return_value = None
    composer._resolve_prompt_speaker = lambda *args, **kwargs: (None, set())
    items = [
        {"id": 0, "text": "First line\nsecond line"},
        {"id": 1, "text": "One\n\nthree\nfour\nfive\n"},
    ]

    _, user, _ = composer.compose_batch_request("SysPrompt", items, items, block_idx=0, mode_description="m")
    payload = _payload(user)

    plain, busy = payload["strings_to_translate"]
    assert plain == {"id": 0, "text": "First line\nsecond line", "layout": {"line_count": 2}}
    assert busy["layout"] == {
        "line_count": 6, "blank_line_indices": [1, 5], "ends_with_newline": True, "window_count": 2,
    }
    assert payload["layout_defaults"] == {
        "lines_per_window": 3, "warning_line_width_px": 280, "max_line_width_px": 300,
    }
    assert list(payload)[0] == "layout_defaults"


def test_an_item_with_its_own_width_keeps_it(composer):
    from handlers.translation.prompt_composer.batch_mixin import _hoist_layout_defaults
    items = [
        {"id": 0, "layout": {"line_count": 1, "max_line_width_px": 300, "lines_per_window": 3}},
        {"id": 1, "layout": {"line_count": 1, "max_line_width_px": 300, "lines_per_window": 3}},
        {"id": 2, "layout": {"line_count": 1, "max_line_width_px": 180, "lines_per_window": 3}},
    ]

    defaults = _hoist_layout_defaults(items)

    assert defaults == {"lines_per_window": 3, "max_line_width_px": 300}
    assert [item["layout"] for item in items] == [
        {"line_count": 1}, {"line_count": 1}, {"line_count": 1, "max_line_width_px": 180},
    ]
