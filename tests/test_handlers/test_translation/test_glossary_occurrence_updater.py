import pytest
from unittest.mock import MagicMock, patch

from handlers.translation.glossary_occurrence_updater import GlossaryOccurrenceUpdater
from core.glossary_manager import GlossaryEntry, GlossaryOccurrence
from core.translation.providers import ProviderResponse

@pytest.fixture
def mock_gh():
    gh = MagicMock()
    gh.mw = MagicMock()
    gh.main_handler = MagicMock()
    gh.main_handler.ai_lifecycle_manager = MagicMock()
    return gh

@pytest.fixture
def updater(mock_gh):
    return GlossaryOccurrenceUpdater(mock_gh)

class _RecordingUIUpdater:
    """Records the UI refresh calls the occurrence updater makes, in order."""

    def __init__(self):
        self.calls = []

    def update_text_views(self):
        self.calls.append(("update_text_views",))

    def populate_strings_for_block(self, *args):
        self.calls.append(("populate_strings_for_block", args))

    def update_block_item_text_with_problem_count(self, block_idx):
        self.calls.append(("update_block_item_text_with_problem_count", block_idx))


class _RecordingTranslationUpdateDialog:
    """Records the AI busy and batch flags the updater sets on the dialog."""

    def __init__(self):
        self.calls = []

    def set_ai_busy(self, busy):
        self.calls.append(("set_ai_busy", busy))

    def set_batch_active(self, active):
        self.calls.append(("set_batch_active", active))


@patch('handlers.translation.glossary_occurrence_updater.GlossaryTranslationUpdateDialog')
def test_gou_show_translation_update_dialog(mock_dialog, updater):
    mock_dialog_inst = mock_dialog.return_value
    
    entry = GlossaryEntry("t", "tr")
    occ = GlossaryOccurrence(entry, 0, 0, 0, 0, 0, "line")
    
    # Show closed dialog
    updater.show_translation_update_dialog(entry=entry, previous_translation="old", occurrences=[occ])
    assert updater._current_translation_entry == entry
    assert updater._previous_translation_value == "old"
    assert updater.translation_update_dialog == mock_dialog_inst
    mock_dialog_inst.show.assert_called_once()
    
    # Show already open dialog
    mock_dialog_inst.isVisible.return_value = True
    updater.show_translation_update_dialog(entry=entry, previous_translation="old2", occurrences=[occ])
    mock_dialog_inst.raise_.assert_called_once()
    mock_dialog_inst.activateWindow.assert_called_once()

def test_gou_on_dialog_closed(updater):
    updater.translation_update_dialog = MagicMock()
    updater._pending_ai_occurrences = [1]
    updater._current_translation_entry = "e"
    updater._previous_translation_value = "v"
    updater._batch_prompt_override = "p"
    
    updater._on_dialog_closed()
    assert updater.translation_update_dialog is None
    assert updater._pending_ai_occurrences == []
    assert updater._current_translation_entry is None
    assert updater._previous_translation_value is None
    assert updater._batch_prompt_override is None

def test_gou_occurrence_helpers(updater):
    occ = GlossaryOccurrence(GlossaryEntry("t", "tr"), 1, 2, 3, 0, 0, "line")
    
    # Original text
    updater._gh._get_original_string.return_value = "orig"
    assert updater._get_occurrence_original_text(occ) == "orig"
    updater._gh._get_original_string.assert_called_with(1, 2)
    
    # Translation text
    updater._main_handler.data_processor.get_current_string_text.return_value = ("trans", {})
    assert updater._get_occurrence_translation_text(occ) == "trans"
    updater._main_handler.data_processor.get_current_string_text.assert_called_with(1, 2)
    
    # Apply translation - active occurrence
    updater._mw.data_store.physical_block_idx = 1
    updater._mw.data_store.current_string_idx = 2
    updater._apply_occurrence_translation(occ, "new_t")
    
    updater._main_handler.data_processor.update_edited_data.assert_called_once_with(
        1, 2, "new_t", skip_ui_refresh=True
    )
    updater._mw.ui_updater.populate_strings_for_block.assert_not_called()
    updater._mw.ui_updater.update_text_views.assert_called_once()
    updater._mw.ui_updater.update_block_item_text_with_problem_count.assert_called_once_with(1)

def test_gou_apply_occurrence_translation_non_active(updater):
    occ = GlossaryOccurrence(GlossaryEntry("t", "tr"), 1, 2, 3, 0, 0, "line")
    ui = _RecordingUIUpdater()
    updater._mw.ui_updater = ui

    # Inactive case 1: different string index
    updater._mw.data_store.physical_block_idx = 1
    updater._mw.data_store.current_string_idx = 99
    updater._apply_occurrence_translation(occ, "new_t")

    updater._main_handler.data_processor.update_edited_data.assert_called_once_with(
        1, 2, "new_t", skip_ui_refresh=True
    )
    assert ui.calls == [("update_block_item_text_with_problem_count", 1)]

    # Inactive case 2: different physical block index
    updater._main_handler.data_processor.update_edited_data.reset_mock()
    ui.calls.clear()
    updater._mw.data_store.physical_block_idx = 5
    updater._mw.data_store.current_string_idx = 2
    updater._apply_occurrence_translation(occ, "new_t2")

    updater._main_handler.data_processor.update_edited_data.assert_called_once_with(
        1, 2, "new_t2", skip_ui_refresh=True
    )
    assert ui.calls == [("update_block_item_text_with_problem_count", 1)]

def test_gou_apply_occurrence_translation_virtual_view_active(updater):
    occ = GlossaryOccurrence(GlossaryEntry("t", "tr"), 1, 2, 3, 0, 0, "line")

    # In virtual view, current_block_idx is negative (e.g. -3), but physical_block_idx matches
    ui = _RecordingUIUpdater()
    updater._mw.ui_updater = ui
    updater._mw.data_store.current_block_idx = -3
    updater._mw.data_store.physical_block_idx = 1
    updater._mw.data_store.current_string_idx = 2
    updater._apply_occurrence_translation(occ, "virtual_text")

    updater._main_handler.data_processor.update_edited_data.assert_called_once_with(
        1, 2, "virtual_text", skip_ui_refresh=True
    )
    assert ui.calls == [("update_text_views",), ("update_block_item_text_with_problem_count", 1)]

def test_gou_request_ai_occurrence_update(updater):
    # No dialog
    updater._request_ai_occurrence_update(None, False)
    
    dialog = _RecordingTranslationUpdateDialog()
    updater.translation_update_dialog = dialog
    updater._current_translation_entry = GlossaryEntry("t", "tr")
    occ = GlossaryOccurrence(updater._current_translation_entry, 1, 2, 3, 0, 0, "line")

    updater._main_handler.data_processor.get_current_string_text.return_value = ("trans", {})

    requested_from_batch = []
    with patch.object(updater, 'request_glossary_occurrence_update',
                      new=lambda **kwargs: requested_from_batch.append(kwargs["from_batch"])):
        updater._request_ai_occurrence_update(occ, False)
        assert dialog.calls == [("set_ai_busy", True)]
        assert requested_from_batch == [False]

        dialog.calls.clear()
        requested_from_batch.clear()
        updater._request_ai_occurrence_update(occ, True)
        assert dialog.calls == [("set_ai_busy", True), ("set_batch_active", True)]
        assert requested_from_batch == [True]

@patch('handlers.translation.glossary_occurrence_updater.QMessageBox')
def test_gou_request_glossary_occurrence_update(mock_box, updater):
    # No provider
    updater._main_handler.ai_lifecycle_manager._prepare_provider.return_value = None
    assert updater.request_glossary_occurrence_update(
        occurrence=None, original_text="", current_translation="", term="t",
        old_term_translation="", new_term_translation="", dialog=None, from_batch=False
    ) is None
    
    # Provider, no prompts
    provider = MagicMock()
    updater._main_handler.ai_lifecycle_manager._prepare_provider.return_value = provider
    updater._gh.load_prompts.return_value = (None, None)
    assert updater.request_glossary_occurrence_update(
        occurrence=None, original_text="", current_translation="", term="t",
        old_term_translation="", new_term_translation="", dialog=None, from_batch=False
    ) is None
    
    # Success, edit rejected
    updater._gh.load_prompts.return_value = ("sys", "txt")
    updater._main_handler.prompt_composer.compose_glossary_occurrence_update_request.return_value = ("c_sys", "c_user")
    updater._main_handler._maybe_edit_prompt.return_value = None
    assert updater.request_glossary_occurrence_update(
        occurrence=None, original_text="", current_translation="", term="t",
        old_term_translation="", new_term_translation="", dialog=None, from_batch=False
    ) is None
    
    # Success
    updater._main_handler._maybe_edit_prompt.return_value = ("e_sys", "e_user")
    res = updater.request_glossary_occurrence_update(
        occurrence=None, original_text="", current_translation="", term="t",
        old_term_translation="", new_term_translation="", dialog=None, from_batch=False
    )
    assert res == ("e_sys", "e_user")
    updater._main_handler.ai_lifecycle_manager.run_ai_task.assert_called_once()

def test_gou_ai_response_handlers(updater):
    occ = GlossaryOccurrence(GlossaryEntry("t", "tr"), 1, 2, 3, 0, 0, "line")
    
    # handle_occurrence_ai_result
    updater.translation_update_dialog = MagicMock()
    updater._pending_ai_occurrences = [occ]
    
    with patch.object(updater, '_resume_ai_occurrence_batch') as mock_res:
        updater.handle_occurrence_ai_result(occurrence=occ, updated_translation="u", from_batch=True)
        updater.translation_update_dialog.on_ai_result.assert_called_with(occ, "u")
        mock_res.assert_called_once()
        
        mock_res.reset_mock()
        updater._pending_ai_occurrences = []
        updater.handle_occurrence_ai_result(occurrence=occ, updated_translation="u", from_batch=True)
        updater.translation_update_dialog.set_ai_busy.assert_called_with(False)
        updater.translation_update_dialog.set_batch_active.assert_called_with(False)
        
        updater.handle_occurrence_ai_result(occurrence=occ, updated_translation="u", from_batch=False)
        assert updater._batch_prompt_override is None

    # Error
    updater._handle_occurrence_ai_error("err", False)
    updater.translation_update_dialog.on_ai_error.assert_called_with("err")
    assert updater._pending_ai_occurrences == []

def test_gou_handle_glossary_occurrence_update_success(updater):
    occ = GlossaryOccurrence(GlossaryEntry("t", "tr"), 1, 2, 3, 0, 0, "line")
    ctx = {"occurrence": occ, "from_batch": False, "composer_args": {"expected_lines": 1}}
    
    errors, results = [], []

    # Invalid JSON
    updater._main_handler.ai_lifecycle_manager._clean_model_output.return_value = "{"
    with patch.object(updater, '_handle_occurrence_ai_error', new=lambda message, from_batch: errors.append(from_batch)):
        updater.handle_glossary_occurrence_update_success(ProviderResponse(), ctx)
    assert errors == [False]
    assert results == []

    # Valid JSON
    updater._main_handler.ai_lifecycle_manager._clean_model_output.return_value = '{"translation": "new"}'
    updater._main_handler.ai_lifecycle_manager._trim_trailing_whitespace_from_lines.return_value = "new"
    with patch.object(updater, 'handle_occurrence_ai_result', new=lambda **kwargs: results.append(kwargs)):
        updater.handle_glossary_occurrence_update_success(ProviderResponse(), ctx)
    assert results == [{"occurrence": occ, "updated_translation": "new", "from_batch": False}]
    assert errors == [False]

def test_gou_handle_glossary_occurrence_batch_success(updater):
    ctx = {"from_batch": True, "expected_lines": {"0": 1}, "occurrence_lookup": {"0": MagicMock()}}
    
    # Valid JSON
    updater._main_handler.ai_lifecycle_manager._clean_model_output.return_value = '{"occurrences": [{"id": "0", "translation": "new"}]}'
    updater._main_handler.ai_lifecycle_manager._trim_trailing_whitespace_from_lines.return_value = "new"
    with patch.object(updater, 'handle_occurrence_batch_success') as mock_batch:
        updater.handle_glossary_occurrence_batch_success(ProviderResponse(), ctx)
        mock_batch.assert_called_with(results={"0": "new"}, context=ctx)

@patch('handlers.translation.glossary_occurrence_updater.QMessageBox')
def test_gou_request_glossary_notes_variation(mock_box, updater):
    # No provider
    updater._main_handler.ai_lifecycle_manager._prepare_provider.return_value = None
    assert not updater.request_glossary_notes_variation(term="t", translation="tr", current_notes="n", context_line=None, dialog=None)
    
    # Provider, no prompts
    provider = MagicMock()
    updater._main_handler.ai_lifecycle_manager._prepare_provider.return_value = provider
    updater._gh.load_prompts.return_value = (None, None)
    assert not updater.request_glossary_notes_variation(term="t", translation="tr", current_notes="n", context_line=None, dialog=None)

    # Success
    updater._gh.load_prompts.return_value = ("sys", "txt")
    updater._main_handler.prompt_composer.compose_variation_request.return_value = ("c_sys", "c_user")
    updater._main_handler._maybe_edit_prompt.return_value = ("e_sys", "e_user")
    
    assert updater.request_glossary_notes_variation(term="t", translation="tr", current_notes="n", context_line="ctx", dialog=None)
    updater._main_handler.ai_lifecycle_manager.run_ai_task.assert_called_once()


def test_gou_show_translation_update_dialog_filtering(mock_gh, updater):
    updater._main_handler.data_processor.is_string_translated.side_effect = lambda b, s: s == 1
    
    entry = GlossaryEntry("t", "tr")
    occ0 = GlossaryOccurrence(entry, 0, 0, 0, 0, 0, "line0")
    occ1 = GlossaryOccurrence(entry, 0, 1, 0, 0, 0, "line1")
    
    with patch('handlers.translation.glossary_occurrence_updater.GlossaryTranslationUpdateDialog') as mock_dialog:
        updater.show_translation_update_dialog(entry=entry, previous_translation="old", occurrences=[occ0, occ1])
        
        mock_dialog.assert_called_once()
        kwargs = mock_dialog.call_args[1]
        assert len(kwargs['occurrences']) == 1
        assert kwargs['occurrences'][0] == occ1


def test_gou_show_translation_update_dialog_no_translated_occurrences(mock_gh, updater):
    updater._main_handler.data_processor.is_string_translated.return_value = False
    
    entry = GlossaryEntry("t", "tr")
    occ = GlossaryOccurrence(entry, 0, 0, 0, 0, 0, "line")
    
    built = []
    with patch('handlers.translation.glossary_occurrence_updater.GlossaryTranslationUpdateDialog', new=lambda **kwargs: built.append(kwargs)):
        updater.show_translation_update_dialog(entry=entry, previous_translation="old", occurrences=[occ])

    assert built == []
    updater._mw.statusBar.showMessage.assert_called_with("No translated occurrences found to update.", 4000)

