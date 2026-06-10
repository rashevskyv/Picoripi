import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from components.editor.line_numbered_text_edit import LineNumberedTextEdit

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def mock_mw():
    mw = MagicMock()
    mw.data_store = MagicMock()
    # Mock displayed_string_indices mapping visual index [0, 1] to database indices [10, 20]
    mw.data_store.displayed_string_indices = [10, 20]
    mw.string_settings_handler = MagicMock()
    return mw

def test_handle_mass_set_width_with_displayed_string_indices(app, mock_mw):
    editor = LineNumberedTextEdit(None)
    editor.window = MagicMock(return_value=mock_mw)
    editor.get_selected_lines = MagicMock(return_value=[0, 1])
    
    with patch('components.editor.line_numbered_text_edit.MassWidthDialog') as MockDialog:
        mock_dialog = MockDialog.return_value
        mock_dialog.exec.return_value = True
        mock_dialog.is_auto_width.return_value = False
        mock_dialog.get_width.return_value = 180
        
        # Act
        editor.handle_mass_set_width()
        
        # Assert
        # The visual line indices [0, 1] should have been mapped to real indices [10, 20]
        mock_mw.string_settings_handler.apply_width_to_lines.assert_called_once_with([10, 20], 180)

def test_handle_mass_set_width_with_auto_width(app, mock_mw):
    editor = LineNumberedTextEdit(None)
    editor.window = MagicMock(return_value=mock_mw)
    editor.get_selected_lines = MagicMock(return_value=[0, 1])
    
    with patch('components.editor.line_numbered_text_edit.MassWidthDialog') as MockDialog:
        mock_dialog = MockDialog.return_value
        mock_dialog.exec.return_value = True
        mock_dialog.is_auto_width.return_value = True
        
        # Act
        editor.handle_mass_set_width()
        
        # Assert
        mock_mw.string_settings_handler.apply_auto_width_from_original_to_lines.assert_called_once_with([10, 20])

def test_handle_mass_set_font_with_displayed_string_indices(app, mock_mw):
    editor = LineNumberedTextEdit(None)
    editor.window = MagicMock(return_value=mock_mw)
    editor.get_selected_lines = MagicMock(return_value=[0, 1])
    
    with patch('components.editor.line_numbered_text_edit.MassFontDialog') as MockDialog:
        mock_dialog = MockDialog.return_value
        mock_dialog.exec.return_value = True
        mock_dialog.get_selected_font.return_value = "custom_font.bfn"
        
        # Act
        editor.handle_mass_set_font()
        
        # Assert
        # The visual line indices [0, 1] should have been mapped to real indices [10, 20]
        mock_mw.string_settings_handler.apply_font_to_lines.assert_called_once_with([10, 20], "custom_font.bfn")
