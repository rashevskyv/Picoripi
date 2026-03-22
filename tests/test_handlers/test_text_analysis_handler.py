import pytest
from unittest.mock import MagicMock, patch
from handlers.text_analysis_handler import TextAnalysisHandler

@pytest.fixture
def handler(mock_mw):
    mock_mw.ui_updater = MagicMock()
    mock_mw.data_processor = MagicMock()
    mock_mw.tools_menu = MagicMock()
    mock_mw.all_font_maps = {"font1": {"A": 10}}
    mock_mw.default_font_file = "font1"
    mock_mw.data = [["AAA", "A"]]
    mock_mw.line_width_warning_threshold_pixels = 100
    
    return TextAnalysisHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)

def test_TextAnalysisHandler_init(handler, mock_mw):
    assert handler.mw == mock_mw

@patch('handlers.text_analysis_handler.QAction')
def test_TextAnalysisHandler_ensure_menu_action(mock_qaction, handler, mock_mw):
    mock_action = mock_qaction.return_value
    handler.ensure_menu_action()
    mock_mw.tools_menu.addAction.assert_called_once_with(mock_action)
    assert handler._menu_action is not None

@patch('handlers.text_analysis_handler.OriginalTextAnalysisDialog')
@patch('handlers.text_analysis_handler.calculate_string_width', side_effect=lambda t, m, f: len(t) * 10)
def test_TextAnalysisHandler_analyze_original_text(mock_calc, mock_dialog_cls, handler, mock_mw):
    handler.analyze_original_text()
    
    mock_dialog = mock_dialog_cls.return_value
    args, kwargs = mock_dialog.show_entries.call_args
    top_entries = kwargs['precomputed_entries']
    
    assert len(top_entries) == 2
    assert top_entries[0]['text'] == "AAA"
    assert top_entries[0]['width_pixels'] == 30.0

def test_TextAnalysisHandler_activate_entry(handler, mock_mw):
    mock_mw.block_list_widget = MagicMock()
    mock_mw.list_selection_handler = MagicMock()
    mock_mw.original_text_edit = MagicMock()
    
    mock_block = MagicMock()
    mock_block.isValid.return_value = True
    mock_block.position.return_value = 50
    mock_mw.original_text_edit.document.return_value.findBlockByNumber.return_value = mock_block
    
    entry = {"block_idx": 0, "string_idx": 1, "line_idx": 0}
    handler._activate_entry(entry)
    
    mock_mw.block_list_widget.select_block_by_index.assert_called_with(0)
    mock_mw.list_selection_handler.string_selected_from_preview.assert_called_with(1)
    mock_mw.original_text_edit.setTextCursor.assert_called()

@patch('PyQt5.QtWidgets.QMessageBox.information')
def test_TextAnalysisHandler_analyze_no_data(mock_msg, handler, mock_mw):
    mock_mw.data = []
    handler.analyze_original_text()
    mock_msg.assert_called()

@patch('PyQt5.QtWidgets.QMessageBox.warning')
def test_TextAnalysisHandler_analyze_no_font_maps(mock_warn, handler, mock_mw):
    mock_mw.all_font_maps = {}
    handler.analyze_original_text()
    mock_warn.assert_called()

def test_TextAnalysisHandler_activate_entry_invalid(handler):
    # Should just return early without error
    handler._activate_entry({"block_idx": None})
    handler._activate_entry({"block_idx": "invalid"})
