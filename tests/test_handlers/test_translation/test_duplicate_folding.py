"""A block with the same string five times costs one translated item and fills five rows (WP4 4.1)."""
import json
from unittest.mock import MagicMock, patch

import pytest

from core.data_state_processor import DataStateProcessor
from core.translation.run_memory import RunMemory
from handlers.translation.ai_prompt_composer import AIPromptComposer
from handlers.translation_handler import TranslationHandler


@pytest.fixture
def window():
    from conftest import MockMainWindow
    mw = MockMainWindow()
    mw.data_store = mw
    mw.data_store.data = [["Yes", "Hello there", "Yes", "Yes", "No", "Yes", "Yes"]]
    mw.data_store.edited_file_data = []
    mw.data_store.edited_data = {}
    mw.data_store.unsaved_changes = False
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 0
    mw.data_store.block_names = {"0": "Block0"}
    mw.data_store.displayed_string_indices = list(range(7))
    mw.data_store.current_chapter_id = None
    mw.data_store.current_category_name = None
    mw.project_manager = None
    mw.block_to_project_file_map = {0: 0}
    mw.ui_updater = MagicMock()
    mw.undo_manager = MagicMock()
    mw.saved_translations_manager = None
    mw.default_tag_mappings = {}
    mw.string_metadata = {}
    mw.icon_sequences = []
    mw.game_dialog_max_width_pixels = 9999
    mw.line_width_warning_threshold_pixels = 9999
    mw.lines_per_page = 99
    mw.prompt_editor_enabled = False
    mw.translation_config = {"provider": "disabled", "workers": 1}
    mw.current_game_rules = MagicMock()
    mw.current_game_rules.convert_editor_text_to_data.side_effect = lambda text: text
    mw.current_game_rules.get_text_representation_for_editor.side_effect = lambda text: text
    mw.current_game_rules.get_shift_enter_char.return_value = "\n"
    return mw


@pytest.fixture
def handler(window):
    processor = DataStateProcessor(window)
    window.data_processor = processor
    with patch('handlers.translation.facade.handler.TranslationUIHandler'), \
         patch('PyQt6.QtCore.QTimer.singleShot'):
        translation_handler = TranslationHandler(window, processor, window.ui_updater)
    translation_handler.ui_handler = MagicMock()
    translation_handler.glossary_handler = MagicMock()
    translation_handler.glossary_handler.load_prompts.return_value = ("system prompt", None)
    translation_handler._run_ai_task = MagicMock()
    translation_handler.save_progress_to_metadata = MagicMock()
    assert isinstance(translation_handler.prompt_composer, AIPromptComposer)
    return translation_handler


def _context(window):
    items = [{"id": index, "text": text} for index, text in enumerate(window.data_store.data[0])]
    return {
        'type': 'translate_block_chunked', 'provider': MagicMock(), 'source_items': items, 'block_idx': 0,
        'mode_description': 'block 1', 'attempt': 1, 'max_retries': 1,
    }


def _reply(chunk, translate):
    return json.dumps({"translated_strings": [
        {"id": item["id"], "translation": translate(item["text"])} for item in chunk
    ]}, ensure_ascii=False)


UKRAINIAN = {"Yes": "Так", "No": "Ні", "Hello there": "Привіт"}


def test_identical_strings_are_sent_once_and_every_row_gets_the_translation(handler, window):
    context = _context(window)

    handler._initiate_batch_translation(context)

    sent = handler._run_ai_task.call_args.args[1]['source_items']
    assert [item["text"] for item in sent] == ["Yes", "Hello there", "No"]         # five "Yes" -> one item
    assert context['duplicate_followers'] == {0: [2, 3, 5, 6]}
    assert handler.translation_progress[0]['duplicate_followers'] == {0: [2, 3, 5, 6]}

    context['calculated_chunks'] = [sent]
    handler._handle_chunk_translated(0, _reply(sent, UKRAINIAN.get), context)

    rows = [window.data_processor.get_current_string_text(0, index)[0] for index in range(7)]
    assert rows == ["Так", "Привіт", "Так", "Так", "Ні", "Так", "Так"]


def test_the_run_memory_learns_what_was_translated_and_the_next_request_shows_it(handler, window):
    context = _context(window)
    handler._initiate_batch_translation(context)
    sent = handler._run_ai_task.call_args.args[1]['source_items']
    context['calculated_chunks'] = [sent]

    handler._handle_chunk_translated(0, _reply(sent, UKRAINIAN.get), context)

    assert isinstance(handler.run_memory, RunMemory)
    assert handler.run_memory.similar(["YES"]) == [{"text": "Yes", "translation": "Так"}]

    _system, user, _ = handler.prompt_composer.compose_batch_request(
        "system prompt", [{"id": 0, "text": "yes"}], [{"id": 0, "text": "yes"}],
        block_idx=0, mode_description="block 1",
    )
    payload = json.loads(user.split('JSON DATA TO PROCESS:\n', 1)[1])
    assert payload['already_translated_in_this_run'] == [{"text": "Yes", "translation": "Так"}]


def test_a_request_without_matching_memory_has_no_memory_section(handler, window):
    _system, user, _ = handler.prompt_composer.compose_batch_request(
        "system prompt", [{"id": 0, "text": "Yes"}], [{"id": 0, "text": "Yes"}],
        block_idx=0, mode_description="block 1",
    )

    assert 'already_translated_in_this_run' not in user


def test_a_new_run_starts_with_an_empty_memory_and_a_continued_one_keeps_it(handler, window):
    handler.run_memory.remember("Yes", "Так")

    handler._initiate_batch_translation(dict(_context(window), continues_run=True))
    assert len(handler.run_memory) == 1

    handler._initiate_batch_translation(_context(window))
    assert len(handler.run_memory) == 0


def test_folding_can_be_switched_off(handler, window):
    window.translation_config['fold_duplicates'] = False
    context = _context(window)

    handler._initiate_batch_translation(context)

    assert len(handler._run_ai_task.call_args.args[1]['source_items']) == 7
    assert 'duplicate_followers' not in context


def test_the_same_text_from_two_speakers_is_sent_twice(handler, window):
    speakers = {0: "Ilia", 2: "Ilia", 3: "Rusl", 5: "Rusl", 6: "Rusl"}
    context = _context(window)

    with patch.object(
        AIPromptComposer, '_resolve_prompt_speaker',
        side_effect=lambda block, string, text, translation_context: (speakers.get(string), set()),
    ):
        handler._initiate_batch_translation(context)

    assert context['duplicate_followers'] == {0: [2], 3: [5, 6]}


def test_a_resumed_run_takes_the_followers_from_the_saved_progress_and_does_not_fold_again(handler, window):
    context = _context(window)
    handler._initiate_batch_translation(context)
    progress = handler.translation_progress[0]
    # what a restart does to the saved progress: ids become strings
    progress['duplicate_followers'] = json.loads(json.dumps(progress['duplicate_followers']))

    resumed = dict(_context(window), is_resume=True, source_items=progress['source_items'])
    handler._initiate_batch_translation(resumed)

    assert resumed['duplicate_followers'] == {"0": [2, 3, 5, 6]}
    sent = handler._run_ai_task.call_args.args[1]['source_items']
    resumed['calculated_chunks'] = [sent]
    handler._handle_chunk_translated(0, _reply(sent, UKRAINIAN.get), resumed)

    assert window.data_processor.get_current_string_text(0, 6)[0] == "Так"


def test_a_follower_that_is_already_translated_is_not_overwritten(handler, window):
    window.data_processor.update_edited_data(0, 3, "Авжеж", action_type="EDIT", skip_ui_refresh=True)
    context = _context(window)
    handler._initiate_batch_translation(context)
    sent = handler._run_ai_task.call_args.args[1]['source_items']
    context['calculated_chunks'] = [sent]

    handler._handle_chunk_translated(0, _reply(sent, UKRAINIAN.get), context)

    assert window.data_processor.get_current_string_text(0, 3)[0] == "Авжеж"       # the user's text stays
    assert (3, "Авжеж") in handler.current_session_previous_translations[0]       # and is offered for comparison
    assert window.data_processor.get_current_string_text(0, 2)[0] == "Так"
