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
    "story_context_ref", "role_instruction", "NARRATIVE CANON", "TRANSCRIPTION RULES", "DIALOGUE FLOW",
    "ADDRESSEE", "TAG ALIAS LEGEND", "ANCHORED TAGS", "REFERENCE TRANSLATIONS", "OUTPUT SHAPE IS IMMUTABLE",
])
def test_batch_rules_cover_every_instruction_the_user_message_used_to_carry(rule):
    assert rule in batch_rules("SysPrompt")


def test_optional_fields_are_only_mentioned_conditionally():
    rules = batch_rules("SysPrompt")
    for field in ('"story_context_ref"', '"established_narrative_context"', '"dialogue_flow"',
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
