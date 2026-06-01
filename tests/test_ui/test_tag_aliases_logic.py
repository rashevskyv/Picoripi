import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QMessageBox
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


@patch('ui.main_window.main_window_actions.QMessageBox.question', return_value=QMessageBox.Yes)
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
    mock_dialog.exec_.return_value = 1  # QDialog.Accepted
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
