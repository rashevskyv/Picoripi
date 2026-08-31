import pytest
from unittest.mock import MagicMock, patch, ANY
from PyQt6.QtWidgets import QDialog

from handlers.translation.glossary_handler import GlossaryHandler
from core.glossary_manager import GlossaryEntry, GlossaryOccurrence
from core.translation.providers import ProviderResponse

@pytest.fixture
def mock_main_handler():
    mh = MagicMock()
    mh.mw = MagicMock()
    mh.mw.tools_menu = MagicMock()
    mh.mw.data_store.data = [["Block 0 String 0", "Block 0 String 1"]]
    mh.mw.current_game_rules = MagicMock()
    mh.mw.current_game_rules.get_display_name.return_value = "Test Game"
    mh.ui_handler = MagicMock()
    mh.ai_lifecycle_manager = MagicMock()
    return mh

@pytest.fixture
def gh(mock_main_handler):
    with patch('handlers.translation.glossary_handler.GlossaryManager'), \
         patch('handlers.translation.glossary_handler.GlossaryPromptManager'), \
         patch('handlers.translation.glossary_handler.GlossaryOccurrenceUpdater'):
        handler = GlossaryHandler(mock_main_handler)
        handler._prompt_manager = MagicMock()
        handler._occurrence_updater = MagicMock()
        handler.glossary_manager = MagicMock()
        return handler

def test_gh_proxies(gh):
    gh._prompt_manager.current_prompts_path = "path"
    assert gh._current_prompts_path == "path"
    
    gh._occurrence_updater.translation_update_dialog = "dialog"
    assert gh.translation_update_dialog == "dialog"
    gh.translation_update_dialog = "new_dialog"
    assert gh._occurrence_updater.translation_update_dialog == "new_dialog"
    
    gh.load_prompts()
    gh._prompt_manager.load_prompts.assert_called_once()
    
    gh.save_prompt_section("s", "f", "v")
    gh._prompt_manager.save_prompt_section.assert_called_with("s", "f", "v")
    
    gh._get_glossary_prompt_template()
    gh._prompt_manager.get_glossary_prompt_template.assert_called_once()
    
    gh._update_glossary_highlighting()
    gh._prompt_manager._update_glossary_highlighting.assert_called_once()
    
    gh._ensure_glossary_loaded(glossary_text="t", plugin_name="p", glossary_path="pth")
    gh._prompt_manager._ensure_glossary_loaded.assert_called_with(glossary_text="t", plugin_name="p", glossary_path="pth")
    
    gh.request_glossary_occurrence_update(a=1)
    gh._occurrence_updater.request_glossary_occurrence_update.assert_called_with(a=1)
    
    gh.request_glossary_occurrence_batch_update(b=2)
    gh._occurrence_updater.request_glossary_occurrence_batch_update.assert_called_with(b=2)
    
    gh.request_glossary_notes_variation(c=3)
    gh._occurrence_updater.request_glossary_notes_variation.assert_called_with(c=3)
    
    gh._handle_occurrence_ai_result(d=4)
    gh._occurrence_updater.handle_occurrence_ai_result.assert_called_with(d=4)
    
    gh._handle_occurrence_batch_success(e=5)
    gh._occurrence_updater.handle_occurrence_batch_success.assert_called_with(e=5)
    
    gh._handle_occurrence_ai_error("err", True)
    gh._occurrence_updater._handle_occurrence_ai_error.assert_called_with("err", True)
    
    gh._handle_glossary_occurrence_update_success(1, 2)
    gh._occurrence_updater.handle_glossary_occurrence_update_success.assert_called_with(1, 2)
    
    gh._handle_glossary_occurrence_batch_success(3, 4)
    gh._occurrence_updater.handle_glossary_occurrence_batch_success.assert_called_with(3, 4)

@patch('handlers.translation.glossary_handler.QAction')
def test_gh_install_menu_actions(mock_action, gh):
    gh.main_handler._reset_session_action = None
    gh.install_menu_actions()
    
    # Needs to be called twice to cover the condition where actions exist
    # First time adds them
    assert gh._open_glossary_action is not None
    assert gh.main_handler._reset_session_action is not None
    mock_action.return_value.setShortcut.assert_any_call("Ctrl+G")
    mock_action.return_value.setToolTip.assert_any_call("Open glossary and jump to occurrences (Ctrl+G)")
    
    # Second time doesn't recreate
    action1 = gh._open_glossary_action
    gh.install_menu_actions()
    assert gh._open_glossary_action == action1

def test_gh_initialize_glossary_highlighting(gh):
    gh.initialize_glossary_highlighting()
    gh._prompt_manager.initialize_highlighting.assert_called_once()

@patch('handlers.translation.glossary_handler.QProgressDialog')
@patch('handlers.translation.glossary_handler.GlossaryOccurrenceWorker')
@patch('handlers.translation.glossary_handler.GlossaryDialog')
@patch('handlers.translation.glossary_handler.QMessageBox')
def test_gh_show_glossary_dialog(mock_box, mock_dialog, mock_worker_cls, mock_progress, gh):
    mock_dialog_inst = mock_dialog.return_value
    mock_pd_inst = mock_progress.return_value
    mock_worker_inst = mock_worker_cls.return_value

    mock_worker_inst.isInterruptionRequested.return_value = False
    # Simulate async worker completion immediately when worker.start() is called
    mock_worker_inst.start.side_effect = lambda: mock_worker_inst.finished_with_result.connect.call_args[0][0]({"a": []})
    
    # Prompts None
    gh._prompt_manager.load_prompts.return_value = (None, None)
    gh.show_glossary_dialog()
    assert gh.dialog is None
    
    # Empty glossary
    gh._prompt_manager.load_prompts.return_value = ("sys", "text")
    gh.glossary_manager.get_entries.return_value = []
    gh.show_glossary_dialog()
    assert gh.dialog == mock_dialog_inst
    mock_dialog_inst.show.assert_called_once()
    mock_dialog_inst.show.reset_mock()
    gh.dialog = None  # reset
    
    # No data
    gh.glossary_manager.get_entries.return_value = [GlossaryEntry("a", "b", "c")]
    gh.mw.data_store.data = None
    gh.show_glossary_dialog()
    mock_box.information.assert_called_once()
    mock_box.reset_mock()
    
    # Success
    gh.mw.data_store.data = [[]]
    gh.show_glossary_dialog("initial")
    assert gh.dialog == mock_dialog_inst
    mock_dialog_inst.show.assert_called_once()
    
    # Already shown
    mock_dialog_inst.isVisible.return_value = True
    gh.show_glossary_dialog()
    mock_dialog_inst.raise_.assert_called_once()
    mock_dialog_inst.activateWindow.assert_called_once()
    
    # Close
    gh._on_glossary_dialog_closed()
    assert gh.dialog is None


def test_glossary_occurrence_worker_run():
    from handlers.translation.glossary_handler import GlossaryOccurrenceWorker
    mock_gm = MagicMock()
    mock_gm.build_occurrence_index.return_value = {"word": []}
    
    worker = GlossaryOccurrenceWorker(mock_gm, ["data"])
    
    finished_mock = MagicMock()
    worker.finished_with_result.connect(finished_mock)
    
    worker.run()
    
    mock_gm.build_occurrence_index.assert_called_once_with(["data"], is_cancelled=ANY)
    finished_mock.assert_called_once_with({"word": []})


def test_glossary_occurrence_worker_exception():
    from handlers.translation.glossary_handler import GlossaryOccurrenceWorker
    mock_gm = MagicMock()
    mock_gm.build_occurrence_index.side_effect = Exception("Thread error")
    
    worker = GlossaryOccurrenceWorker(mock_gm, ["data"])
    
    finished_mock = MagicMock()
    worker.finished_with_result.connect(finished_mock)
    
    worker.run()
    
    finished_mock.assert_called_once_with({})

@patch('handlers.translation.glossary_handler.GlossaryEditDialog')
def test_gh_add_edit_glossary_entry(mock_dialog, gh):
    mock_dialog_inst = mock_dialog.return_value
    mock_dialog_inst.exec.return_value = QDialog.DialogCode.Rejected
    
    # Test rejection
    gh.add_glossary_entry("Test")
    mock_dialog_inst.get_values.assert_not_called()
    
    # Test accepted, update translation
    mock_dialog_inst.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog_inst.get_values.return_value = ("NewTrans", "NewNotes")
    
    gh.glossary_manager.get_entry.return_value = GlossaryEntry("Test", "OldTrans", "OldNotes")
    entry_mock = MagicMock()
    entry_mock.original = "Test"
    gh.glossary_manager.update_entry.return_value = entry_mock
    
    gh.edit_glossary_entry("Test", is_new=False)
    gh.glossary_manager.update_entry.assert_called_with("Test", "NewTrans", "NewNotes")
    gh.glossary_manager.save_to_disk.assert_called()
    gh._prompt_manager._update_glossary_highlighting.assert_called()
    gh._occurrence_updater.show_translation_update_dialog.assert_called()
    
    # Test accepted, only notes updated for existing entry
    mock_dialog_inst.get_values.return_value = ("", "NewNotes")
    entry = GlossaryEntry("Test", "Trans", "OldNotes")
    gh.glossary_manager.get_entry.return_value = entry
    gh.edit_glossary_entry("Test", is_new=False)
    gh.glossary_manager.update_entry.assert_called_with("Test", "Trans", "NewNotes")

@patch('handlers.translation.glossary_handler.GlossaryEditDialog')
def test_gh_ai_fill_glossary_entry(mock_dialog, gh):
    d = mock_dialog.return_value
    
    gh.main_handler._prepare_provider.return_value = None
    gh._ai_fill_glossary_entry("term", "context", d)
    d.set_ai_busy.assert_not_called()
    
    provider = MagicMock()
    gh.main_handler._prepare_provider.return_value = provider
    gh._prompt_manager.get_glossary_prompt_template.return_value = (None, None)
    gh._ai_fill_glossary_entry("term", "context", d)
    d.set_ai_busy.assert_not_called()
    
    gh._prompt_manager.get_glossary_prompt_template.return_value = ("t {{GAME_NAME}}", None)
    gh.main_handler._maybe_edit_prompt.return_value = None
    gh._ai_fill_glossary_entry("term", "context", d)
    d.set_ai_busy.assert_not_called()
    
    gh.main_handler._maybe_edit_prompt.return_value = ("sys", "user")
    gh._ai_fill_glossary_entry("term", "context", d)
    d.set_ai_busy.assert_called_with(True)
    gh.main_handler._run_ai_task.assert_called_once()

from components.glossary_edit_dialog import GlossaryEditDialog

@patch('handlers.translation.glossary_handler.QMessageBox')
def test_gh_handle_ai_fill(mock_box, gh):
    dialog = MagicMock(spec=GlossaryEditDialog)
    dialog.get_values.return_value = ("oldT", "oldN")
    ctx = {'dialog': dialog}
    
    # Error
    gh._handle_ai_fill_error("err", ctx)
    dialog.set_ai_busy.assert_called_with(False)
    mock_box.warning.assert_called_once()
    mock_box.reset_mock()
    
    # Success bad JSON
    gh.main_handler.ai_lifecycle_manager._clean_model_output.return_value = "invalid"
    gh._handle_ai_fill_success(ProviderResponse(), ctx)
    mock_box.warning.assert_called_once()
    mock_box.reset_mock()
    
    # Success no fields
    gh.main_handler.ai_lifecycle_manager._clean_model_output.return_value = "{}"
    gh._handle_ai_fill_success(ProviderResponse(), ctx)
    mock_box.information.assert_called_once()
    mock_box.reset_mock()
    
    # Success
    gh.main_handler.ai_lifecycle_manager._clean_model_output.return_value = '{"translation": "nT", "notes": "nN"}'
    gh._handle_ai_fill_success(ProviderResponse(), ctx)
    dialog.set_values.assert_called_with("nT", "nN")

def test_gh_start_glossary_notes_variation(gh):
    d = MagicMock()
    gh._occurrence_updater.request_glossary_notes_variation.return_value = False
    gh._start_glossary_notes_variation(term="t", translation="tr", notes="n", context_line="c", target_dialog=d)
    
    d.set_ai_busy.assert_called_with(False)

def test_gh_handle_notes_variation_from_dialog(gh):
    # Setup dialog
    gh.dialog = MagicMock()
    gh.mw.data_store.data = [["Block 0 String 0"]]
    
    occurrence = GlossaryOccurrence(GlossaryEntry("t", "tr", "n"), 0, 0, 0, 0, 0, "Block 0 String 0")
    gh.glossary_manager.build_occurrence_index.return_value = {"t": [occurrence]}
    
    gh._handle_notes_variation_from_dialog(GlossaryEntry("t", "tr", "n"))
    gh._occurrence_updater.request_glossary_notes_variation.assert_called_once()

@patch('handlers.translation.glossary_handler.QMessageBox')
def test_gh_handle_glossary_notes_variation_success(mock_box, gh):
    gh.main_handler.ai_lifecycle_manager._clean_model_output.return_value = "cleaned"
    gh.main_handler.ui_handler.parse_variation_payload.return_value = []
    
    gh._handle_glossary_notes_variation_success(ProviderResponse(), {})
    mock_box.information.assert_called_once()
    
    gh.main_handler.ui_handler.parse_variation_payload.return_value = ["v1"]
    gh.main_handler.ui_handler.show_variations_dialog.return_value = "v1"
    
    d = MagicMock()
    d.get_values.return_value = ("tr", "old")
    gh._handle_glossary_notes_variation_success(ProviderResponse(), {'dialog': d})
    d.set_values.assert_called_with("tr", "v1")

def test_gh_jump_to_occurrence(gh):
    occ = GlossaryOccurrence(GlossaryEntry("t", "tr", "n"), 0, 1, 2, 0, 0, "line")
    gh._jump_to_occurrence(occ)
    gh.main_handler.ui_handler._activate_entry.assert_called_with({'block_idx': 0, 'string_idx': 1, 'line_idx': 2})

def test_gh_handle_glossary_entry_update(gh):
    entry1 = GlossaryEntry("old", "tr", "n")
    gh.glossary_manager.get_entry.return_value = entry1
    gh.glossary_manager.update_entry.return_value = True
    
    gh._handle_glossary_entry_update("old", "new", "nn")
    # status=None keeps the entry's lifecycle stage; the dialog passes a real
    # status only when the user confirms a translation.
    gh.glossary_manager.update_entry.assert_called_with("old", "new", "nn", profiled=None, status=None)
    gh._prompt_manager._update_glossary_highlighting.assert_called()


def test_gh_handle_glossary_entry_update_persists_category(gh):
    entry = GlossaryEntry("Ash", "", "", section="Characters")
    gh.glossary_manager.get_entry.return_value = entry
    gh.glossary_manager.update_entry.return_value = entry
    gh.glossary_manager.get_entries.return_value = [entry]

    gh._handle_glossary_entry_update("Ash", "", "", section="Creatures")

    gh.glossary_manager.update_entry.assert_called_once_with(
        "Ash", "", "", profiled=None, status=None, section="Creatures"
    )


def test_gh_handle_glossary_entry_delete(gh):
    gh.glossary_manager.delete_entry.return_value = True
    gh._handle_glossary_entry_delete("term")
    gh.glossary_manager.delete_entry.assert_called_with("term")
    gh._prompt_manager._update_glossary_highlighting.assert_called()


def test_gh_handle_apply_speaker_name_success_focuses_term(gh):
    gh.mw.speaker_merge_handler = MagicMock()
    gh.mw.speaker_merge_handler.save_names.return_value = True
    gh.dialog = MagicMock()

    gh._handle_apply_speaker_name("Ash", "Ashy")

    gh.mw.speaker_merge_handler.save_names.assert_called_once_with({"Ash": "Ashy"})
    gh.dialog.focus_term.assert_called_once_with("Ashy")


def test_gh_handle_apply_speaker_name_failure_does_not_focus_term(gh):
    gh.mw.speaker_merge_handler = MagicMock()
    gh.mw.speaker_merge_handler.save_names.return_value = False
    gh.dialog = MagicMock()

    gh._handle_apply_speaker_name("Ash", "Ashy")

    gh.mw.speaker_merge_handler.save_names.assert_called_once_with({"Ash": "Ashy"})
    gh.dialog.focus_term.assert_not_called()


def test_gh_reassign_speaker_name_focuses_new_term_only_on_success(gh):
    gh.mw.speaker_merge_handler = MagicMock()
    gh.mw.speaker_merge_handler.reassign_name.return_value = True
    gh.dialog = MagicMock()

    gh._handle_reassign_speaker_name("Ash", "ASHEI", "TELMA")

    gh.mw.speaker_merge_handler.reassign_name.assert_called_once_with("Ash", "ASHEI", "TELMA")
    gh.dialog.focus_term.assert_called_once_with("TELMA")


def test_gh_confirmed_speaker_codes_includes_shared_voice_parts(gh):
    gh.mw.project_manager.project_dir = None
    with patch(
        "handlers.translation.glossary_handler.load_speaker_aliases",
        return_value={"Ash": "ASHEI", "Other": "ASHEI / TELMA"},
    ):
        assert gh._confirmed_speaker_codes("ASHEI") == ["Ash", "Other"]
        assert gh._confirmed_speaker_codes("TELMA") == ["Other"]


def test_gh_placeholder_speaker_callback_recognizes_legacy_code_and_alias(gh):
    gh.mw.current_game_rules.is_placeholder_speaker.side_effect = lambda term: term == "Ash"
    gh.mw.project_manager.project_dir = None

    with patch("handlers.translation.glossary_handler.load_speaker_aliases", return_value={}):
        callback = gh._placeholder_speaker_callback()
    assert callback("Ash") is True
    assert callback("Ashei") is False

    with patch("handlers.translation.glossary_handler.load_speaker_aliases", return_value={"Ash": "Ashei"}):
        callback = gh._placeholder_speaker_callback()
    assert callback("Ash") is False

    with patch(
        "handlers.translation.glossary_handler.load_speaker_aliases",
        return_value={"Ash": "ASHEI / TELMA"},
    ):
        callback = gh._placeholder_speaker_callback()
    assert callback("Ash") is False


def test_gh_format_variant_discussion_context(gh):
    from core.glossary_manager import DescriptionFragment, TranslationVariant
    entry = GlossaryEntry(
        original="Spring Goron",
        translation="Ґорон Джерела",
        notes="A Goron living near the hot spring.",
        fragments=(
            DescriptionFragment("He manages the thermal bath."),
        ),
        translation_variants=(
            TranslationVariant("Ґорон Джерела", "spring = bathhouse"),
            TranslationVariant("Весняний Ґорон", "spring = season"),
        ),
    )
    gh.mw.target_language = "Ukrainian"
    context = gh.format_variant_discussion_context(entry)
    assert "Term: Spring Goron" in context
    assert "Target language: Ukrainian" in context
    assert "Description:\nA Goron living near the hot spring." in context
    assert "Description fragments:\n- He manages the thermal bath." in context
    assert "Proposed translation candidates:" in context
    assert "- Ґорон Джерела (Rationale: spring = bathhouse)" in context
    assert "- Весняний Ґорон (Rationale: spring = season)" in context
    assert "You must recommend exactly one of the displayed candidates above, verbatim." in context

    # Test fallback target language
    gh.mw.target_language = None
    fallback_context = gh.format_variant_discussion_context(entry)
    assert "Target language: Ukrainian" in fallback_context

    gh.mw.target_language = "German"
    custom_context = gh.format_variant_discussion_context(entry)
    assert "Target language: German" in custom_context


def test_gh_handle_discuss_variants_from_dialog(gh):
    from core.glossary_manager import TranslationVariant
    entry = GlossaryEntry(
        original="Spring Goron",
        translation="Ґорон Джерела",
        notes="A Goron.",
        translation_variants=(
            TranslationVariant("Ґорон Джерела", "spring = bathhouse"),
        ),
    )
    gh.mw.ai_chat_handler = MagicMock()
    gh._handle_discuss_variants_from_dialog(entry)

    gh.mw.ai_chat_handler.show_chat_window.assert_called_once()
    initial_text = gh.mw.ai_chat_handler.show_chat_window.call_args.kwargs["initial_text"]
    assert "Term: Spring Goron" in initial_text
    assert "Ґорон Джерела" in initial_text


def test_gh_handle_discuss_variants_from_dialog_safe_noops(gh):
    gh.mw.ai_chat_handler = None
    # None entry or missing chat handler must not raise
    gh._handle_discuss_variants_from_dialog(None)
    entry = GlossaryEntry(original="Test", translation="")
    gh._handle_discuss_variants_from_dialog(entry)
