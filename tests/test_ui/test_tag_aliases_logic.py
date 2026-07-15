import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QMessageBox
from plugins.base_game_rules import BaseGameRules
from handlers.text_operation_handler import TextOperationHandler
from core.data_state_processor import DataStateProcessor
from ui.main_window.main_window_actions import MainWindowActions

@patch('handlers.text_operation_handler.AsyncIssueScanner')
def test_text_edited_resolves_alias_to_tag(mock_async_scanner, mock_mw):
    # Setup default mappings
    mock_mw.default_tag_mappings = {"{RedColor}": "{Color:Red}"}
    mock_mw.current_game_rules = BaseGameRules(main_window_ref=mock_mw)
    mock_mw.helper.get_font_map_for_string.return_value = {}
    
    # Mock text edit component with on-screen text containing the alias
    edited_text_edit = MagicMock()
    edited_text_edit.toPlainText.return_value = "This is {RedColor} text"
    mock_mw.edited_text_edit = edited_text_edit
    
    # Mock data store
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = 0
    mock_mw.data_store.data = [["original"]]
    mock_mw.data_store.edited_file_data = []
    mock_mw.data_store.edited_data = {}
    mock_mw.data_store.edited_sublines = set()
    mock_mw.is_programmatically_changing_text = False
    mock_mw.line_width_warning_threshold_pixels = 200
    
    # Initialize real DataStateProcessor and TextOperationHandler
    dsp = DataStateProcessor(mock_mw)
    mock_mw.data_processor = dsp
    
    handler = TextOperationHandler(mock_mw, dsp, mock_mw.ui_updater)
    
    # Act
    handler.text_edited()
    handler._on_preview_update_timer_timeout()
    
    # Assert
    # The raw text in edited_data must contain the original tag, not the alias
    assert mock_mw.data_store.edited_data[(0, 0)] == "This is {Color:Red} text"


def test_text_views_shows_alias_instead_of_tag(mock_mw):
    # Setup default mappings
    mock_mw.default_tag_mappings = {"{RedColor}": "{Color:Red}"}
    rules = BaseGameRules(main_window_ref=mock_mw)
    
    original_text = "This is {Color:Red} text with another {Color:Red}"
    
    # Act - convert text to display representation
    editor_text = rules.get_text_representation_for_editor(original_text)
    
    # Assert
    # On screen we must see the alias
    assert editor_text == "This is {RedColor} text with another {RedColor}"
    
    # Act - convert back to storage format
    data_text = rules.convert_editor_text_to_data(editor_text)
    
    # Assert
    # The storage format must restore the original tag
    assert data_text == original_text


def test_alias_replacement_matches_complete_tag_tokens(mock_mw):
    mock_mw.default_tag_mappings = {
        "{Short}": "{escape:0:0037}",
        "{Full}": "{escape:0:003700}",
    }
    rules = BaseGameRules(main_window_ref=mock_mw)

    assert rules.get_text_representation_for_editor("{escape:0:003700}") == "{Full}"
    assert rules.convert_editor_text_to_data("{Full}") == "{escape:0:003700}"


@patch('ui.main_window.main_window_actions.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes)
def test_remove_tag_alias_replaces_alias_with_tag_in_edited_data(mock_question, mock_mw):
    # Setup default mappings and actual window actions
    mock_mw.default_tag_mappings = {"{OldAlias}": "{OldTag}"}
    mock_mw.helper = MagicMock()
    
    # Setup edited_data containing the stale alias (e.g. from session or copy-paste)
    mock_mw.data_store.edited_data = {
        (0, 0): "Some {OldAlias} text",
        (0, 1): "Unrelated text"
    }
    
    actions = MainWindowActions(mock_mw)
    
    # Act - remove the alias
    actions.remove_tag_alias("{OldAlias}", "{OldTag}")
    
    # Assert
    # The alias should be removed from default_tag_mappings
    assert "{OldAlias}" not in mock_mw.default_tag_mappings
    # The stale alias in edited_data must be replaced with the original tag
    assert mock_mw.data_store.edited_data[(0, 0)] == "Some {OldTag} text"
    assert mock_mw.data_store.edited_data[(0, 1)] == "Unrelated text"
    # Highlighters and views should be refreshed
    mock_mw.helper.reconfigure_all_highlighters.assert_called_once()
    mock_mw.ui_updater.update_text_views.assert_called_once()


@patch('ui.main_window.main_window_actions.TagAliasDialog')
def test_edit_tag_alias_replaces_old_alias_in_edited_data(mock_dialog_class, mock_mw):
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = 1  # QDialog.Accepted
    mock_dialog.get_data.return_value = ("{NewAlias}", None)
    mock_dialog_class.return_value = mock_dialog

    # Setup default mappings and actual window actions
    mock_mw.default_tag_mappings = {"{OldAlias}": "{OldTag}"}
    mock_mw.helper = MagicMock()
    
    # Setup edited_data containing the old alias
    mock_mw.data_store.edited_data = {
        (0, 0): "Some {OldAlias} text"
    }
    
    actions = MainWindowActions(mock_mw)
    
    # Act - edit the alias to "{NewAlias}"
    actions.edit_tag_alias("{OldAlias}", "{OldTag}")
    
    # Assert
    # Old alias is gone, new alias is set to the same original tag
    assert "{OldAlias}" not in mock_mw.default_tag_mappings
    assert "{NewAlias}" in mock_mw.default_tag_mappings
    assert mock_mw.default_tag_mappings["{NewAlias}"] == "{OldTag}"
    
    # Stale old alias in edited_data is cleaned up back to the raw tag
    # (since the editor updates representation dynamically when displaying)
    assert mock_mw.data_store.edited_data[(0, 0)] == "Some {OldTag} text"
    # Views and highlighters are refreshed
    mock_mw.helper.reconfigure_all_highlighters.assert_called_once()
    mock_mw.ui_updater.update_text_views.assert_called_once()


def test_tag_alias_dialog_focus_and_return_pressed(qtbot):
    from ui.main_window.main_window_actions import TagAliasDialog
    from PyQt6.QtWidgets import QDialog

    dialog = TagAliasDialog(
        parent=None,
        title="Test Title",
        original_tag="{Color:Red}",
        current_alias="{RedColor}",
        current_width=100
    )
    qtbot.addWidget(dialog)

    accepted_calls = 0
    def fake_accept():
        nonlocal accepted_calls
        accepted_calls += 1
    dialog.accept = fake_accept

    dialog.alias_edit.returnPressed.emit()
    assert accepted_calls == 1

    dialog.width_edit.returnPressed.emit()
    assert accepted_calls == 2


@patch('ui.main_window.main_window_actions.QProgressDialog')
@patch('ui.main_window.main_window_actions.AliasUpdateWorker')
def test_edit_tag_alias_progress_dialog_modality(mock_worker_class, mock_progress_dialog_class, mock_mw):
    from ui.main_window.main_window_actions import MainWindowActions
    from PyQt6.QtCore import Qt
    
    mock_progress_dialog = MagicMock()
    mock_progress_dialog_class.return_value = mock_progress_dialog
    
    mock_worker = MagicMock()
    mock_worker_class.return_value = mock_worker
    
    # We create a dummy class for mw to bypass is_test check which filters "Mock" in class name
    class RealMainWindowLike:
        def __init__(self):
            self.default_tag_mappings = {"{OldAlias}": "{OldTag}"}
            self.data_store = MagicMock()
            self.data_store.edited_data = {(0, 0): "Some {OldAlias} text"}
            self.data_store.data = []
            self.data_store.edited_file_data = []
            self.font_map_overrides = {}
            self.active_game_plugin = None
            self.settings_manager = MagicMock()
            self.issue_scan_handler = MagicMock()
            self.helper = MagicMock()
            self.ui_updater = MagicMock()
            self.text_operation_handler = MagicMock()
            
    fake_mw = RealMainWindowLike()
    actions = MainWindowActions(fake_mw)
    
    # Patch TagAliasDialog so it returns accepted new alias
    with patch('ui.main_window.main_window_actions.TagAliasDialog') as mock_dialog_class, \
         patch('PyQt6.QtWidgets.QApplication.instance') as mock_app_instance:
         
        from PyQt6.QtWidgets import QApplication
        mock_app = MagicMock(spec=QApplication)
        mock_app_instance.return_value = mock_app
        
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = 1  # Accepted
        mock_dialog.get_data.return_value = ("{NewAlias}", None)
        mock_dialog_class.return_value = mock_dialog
        
        actions.edit_tag_alias("{OldAlias}", "{OldTag}")
        
    mock_progress_dialog.setWindowModality.assert_called_with(Qt.WindowModality.WindowModal)


