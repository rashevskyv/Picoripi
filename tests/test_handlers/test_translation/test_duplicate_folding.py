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


# -- D46: a plugin's duplicate context (the 3DS manual: one context for every paragraph) ----------------------

MANUAL_TEXT = "Текст"
WIDE = "large/Page_000_large_0#0"
NARROW = "small/Page_001_small_0#1"
FITS_ONLY_WIDE = "а" * 12


def _manual_rules(monkeypatch, doc, window, data):
    """The 3DS manual plugin with one synthetic manual loaded as block 0; ``data`` is the block's source column."""
    from plugins.manual_3ds import layout
    from plugins.manual_3ds import rules as m3d

    advances = {ch: 10.0 for ch in "абвгґдеєжзиіїйклмнопрстуфхцчшщьюяabcdefghijklmnopqrstuvwxyz"}
    advances[" "] = 9.0
    monkeypatch.setattr(m3d._DATA, "widths", layout.Widths({"advances": advances, "homoglyphs": {}}))
    wide = {"part": "large", "font_size": 24.0, "char_space": 0.0, "icon_widths": [], "lines": [[[10.0, 300.0]]]}
    narrow = {"part": "small", "font_size": 24.0, "char_space": 0.0, "icon_widths": [],
              "lines": [[[20.0, 100.0, 250.0]]]}
    keys = list(doc)
    table = {m3d.fingerprint(keys): {"name": "synthetic", "entries": {WIDE: wide, NARROW: narrow}}}
    monkeypatch.setattr(m3d._DATA, "geometry", table)
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(json.dumps(doc, ensure_ascii=False))
    window.current_game_rules = rules
    window.data_store.data = data
    return rules


def _manual_doc(width_narrow=100.0):
    return {WIDE: {"lines": 1, "width": 300.0, "en": "", "ru": MANUAL_TEXT},
            NARROW: {"lines": 1, "width": width_narrow, "en": "", "ru": MANUAL_TEXT}}


def test_without_a_plugin_context_the_key_is_the_five_value_tuple_of_before(handler, window):
    window.current_game_rules = None
    composer = handler.prompt_composer

    key = composer.duplicate_context_key({"id": 0, "text": "Yes"}, 0, None)

    assert key == ("NONE", "", "99", "{}", "{}")   # a one-word text has no speaker
    saved = composer.saved_context(0, 0, "Yes")
    assert saved == {"speaker": "NONE", "addressee": "", "fold": _sha(key), "speaker_en": ""}


def _sha(key):
    import hashlib
    return hashlib.sha1(json.dumps(key, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]


def test_the_paragraphs_of_one_manual_share_one_key_whatever_their_window(monkeypatch, handler, window):
    _manual_rules(monkeypatch, _manual_doc(), window, [[MANUAL_TEXT, MANUAL_TEXT]])
    composer = handler.prompt_composer

    wide = composer.duplicate_context_key({"id": 0, "text": MANUAL_TEXT}, 0, None)
    narrow = composer.duplicate_context_key({"id": 1, "text": MANUAL_TEXT}, 0, None)

    assert wide == narrow == ("NONE", "", json.dumps({"content_role": "Manual text"}, sort_keys=True), "{}")


def test_the_saved_context_keeps_the_legacy_fold_of_its_own_place(monkeypatch, handler, window):
    _manual_rules(monkeypatch, _manual_doc(), window, [[MANUAL_TEXT, MANUAL_TEXT]])
    composer = handler.prompt_composer

    wide = composer.saved_context(0, 0, MANUAL_TEXT)
    narrow = composer.saved_context(0, 1, MANUAL_TEXT)

    assert wide["fold"] == narrow["fold"]
    assert wide["fold_legacy"] != narrow["fold_legacy"], "the legacy fold still tells the two windows apart"
    assert wide["fold_legacy"] != wide["fold"]


def test_the_paragraph_of_another_manual_block_gets_the_same_key(monkeypatch, handler, window):
    rules = _manual_rules(monkeypatch, _manual_doc(), window, [[MANUAL_TEXT], [MANUAL_TEXT]])
    other = {"large/Page_007_large_0#0": {"lines": 2, "width": 240.0, "en": "", "ru": MANUAL_TEXT}}
    rules.load_data_from_json_obj(json.dumps(other, ensure_ascii=False))
    composer = handler.prompt_composer

    first = composer.duplicate_context_key({"id": 0, "text": MANUAL_TEXT}, 0, None)
    second = composer.duplicate_context_key({"id": 0, "text": MANUAL_TEXT}, 1, None)

    assert first == second, "the speaker and the addressee of a manual paragraph do not depend on its block"


def test_a_follower_that_does_not_fit_its_place_stays_untranslated(monkeypatch, handler, window):
    _manual_rules(monkeypatch, _manual_doc(), window, [[MANUAL_TEXT, MANUAL_TEXT]])
    context = _context(window)
    context['source_items'] = [{"id": 0, "text": MANUAL_TEXT}, {"id": 1, "text": MANUAL_TEXT}]
    handler._initiate_batch_translation(context)
    assert context['duplicate_followers'] == {0: [1]}
    sent = handler._run_ai_task.call_args.args[1]['source_items']
    context['calculated_chunks'] = [sent]

    handler._handle_chunk_translated(0, _reply(sent, lambda text: FITS_ONLY_WIDE), context)

    assert window.data_processor.get_current_string_text(0, 0)[0] == FITS_ONLY_WIDE   # the wide paragraph takes it
    assert not window.data_processor.is_string_translated(0, 1)                      # the narrow one refuses it


def test_a_two_word_manual_paragraph_has_the_same_key_in_two_blocks(monkeypatch, handler, window):
    """A text of two words goes through the speaker resolver (a one-word text is never a speaker)."""
    phrase = "Текст один"
    rules = _manual_rules(monkeypatch, {WIDE: {"lines": 1, "width": 300.0, "en": "", "ru": phrase}},
                          window, [[phrase], [phrase]])
    other = {"large/Page_007_large_0#0": {"lines": 2, "width": 240.0, "en": "", "ru": phrase}}
    rules.load_data_from_json_obj(json.dumps(other, ensure_ascii=False))
    composer = handler.prompt_composer

    first = composer.duplicate_context_key({"id": 0, "text": phrase}, 0, None)
    second = composer.duplicate_context_key({"id": 0, "text": phrase}, 1, None)

    assert first == second
    assert first[0] == ""   # no speaker is looked up for a manual paragraph
