import pytest
from unittest.mock import MagicMock, patch
from handlers.text_operation_handler import TextOperationHandler

@pytest.fixture
def handler(mock_mw):
    mock_mw.ui_updater = MagicMock()
    mock_mw.data_processor = MagicMock()
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_mw.is_loading_data = False
    mock_mw.is_programmatically_changing_text = False
    mock_mw.edited_text_edit = MagicMock()
    mock_mw.preview_text_edit = MagicMock()
    mock_mw.preview_text_edit.document.return_value.blockCount.return_value = 10
    mock_mw.problems_per_subline = {}
    mock_mw.current_game_rules = MagicMock()
    mock_mw.edited_data = {}
    mock_mw.edited_sublines = set()
    mock_mw.string_metadata = {}
    mock_mw.line_width_warning_threshold_pixels = 200
    mock_mw.helper = MagicMock()
    mock_mw.statusBar = MagicMock()
    mock_mw.EDITOR_PLAYER_TAG = "[PLAYER]"
    mock_mw.data = [["original"]]
    mock_mw.before_paste_edited_data_snapshot = {}
    
    # Setup DataProcessor mocks
    mock_mw.data_processor.get_current_string_text.return_value = ("current", False)
    mock_mw.data_processor._get_string_from_source.return_value = "original"
    mock_mw.data_processor.update_edited_data.return_value = True
    
    # Default behavior for game rules
    mock_mw.current_game_rules.convert_editor_text_to_data.side_effect = lambda x: x
    mock_mw.current_game_rules.autofix_data_string.return_value = ("fixed", True)
    mock_mw.current_game_rules.get_text_representation_for_editor.side_effect = lambda x: x
    mock_mw.current_game_rules.process_pasted_segment.return_value = ("processed", None, None)
    
    # Mock text document
    mock_doc = MagicMock()
    mock_doc.characterCount.return_value = 10
    mock_mw.edited_text_edit.document.return_value = mock_doc
    
    # Mock text cursor
    mock_cursor = MagicMock()
    mock_cursor.position.return_value = 5
    mock_mw.edited_text_edit.textCursor.return_value = mock_cursor
    
    h = TextOperationHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)
    return h

def test_TextOperationHandler_init(handler, mock_mw):
    assert handler.mw == mock_mw

@patch('handlers.text_operation_handler.convert_dots_to_spaces_from_editor', side_effect=lambda x: x)
def test_TextOperationHandler_text_edited(mock_conv, handler, mock_mw):
    mock_mw.edited_text_edit.toPlainText.return_value = "new text"
    
    handler.text_edited()
    
    mock_mw.data_processor.update_edited_data.assert_called_with(0, 0, "new text")
    mock_mw.ui_updater.update_title.assert_called()

@patch('PyQt5.QtWidgets.QApplication.clipboard')
@patch('re.split', return_value=["line1"])
def test_TextOperationHandler_paste_block_text(mock_split, mock_clipboard, handler, mock_mw):
    mock_clipboard.return_value.text.return_value = "line1"
    
    handler.paste_block_text()
    
    mock_mw.data_processor.update_edited_data.assert_called_with(0, 0, "processed")

def test_TextOperationHandler_revert_single_line(handler, mock_mw):
    handler.revert_single_line(0)
    
    mock_mw.data_processor.update_edited_data.assert_called_with(0, 0, "original", action_type="REVERT")
    mock_mw.ui_updater.update_text_views.assert_called()

@patch('handlers.text_operation_handler.convert_dots_to_spaces_from_editor', side_effect=lambda x: x)
@patch('handlers.text_operation_handler.QTextCursor')
def test_TextOperationHandler_auto_fix_current_string(mock_cursor_cls, mock_conv, handler, mock_mw):
    mock_mw.edited_text_edit.toPlainText.side_effect = ["bad text", "fixed", "fixed", "fixed"]
    
    handler.auto_fix_current_string()
    
    mock_mw.data_processor.update_edited_data.assert_any_call(0, 0, "fixed")

def test_TextOperationHandler_rescan_issues_for_current_string(handler, mock_mw):
    # Mock analyzer to return a problem
    analyzer = MagicMock()
    mock_mw.current_game_rules.problem_analyzer = analyzer
    analyzer.analyze_data_string.return_value = [{"PROB"}]
    
    handler._rescan_issues_for_current_string(0, 0, "test")
    
    # Verify problems_per_subline update
    assert (0, 0, 0) in mock_mw.problems_per_subline
    assert mock_mw.problems_per_subline[(0, 0, 0)] == {"PROB"}

def test_TextOperationHandler_rescan_issues_subline(handler, mock_mw):
    analyzer = MagicMock()
    del analyzer.analyze_data_string # Force analyze_subline path
    analyzer.analyze_subline.return_value = {"PROB2"}
    mock_mw.current_game_rules.problem_analyzer = analyzer
    
    handler._rescan_issues_for_current_string(0, 0, "line1\nline2")
    assert mock_mw.problems_per_subline[(0, 0, 0)] == {"PROB2"}
    assert mock_mw.problems_per_subline[(0, 0, 1)] == {"PROB2"}

def test_TextOperationHandler_rescan_issues_no_rules(handler, mock_mw):
    mock_mw.current_game_rules = None
    handler._rescan_issues_for_current_string(0, 0, "test") # Should return early

def test_TextOperationHandler_update_preview_content(handler, mock_mw):
    mock_mw.data = [["str0", "str1"]]
    mock_mw.displayed_string_indices = [0, 1]
    mock_mw.current_game_rules.get_text_representation_for_preview.side_effect = lambda x: f"prev_{x}"
    
    handler._update_preview_content()
    
    mock_mw.preview_text_edit.setPlainText.assert_called_with("prev_current\nprev_current")
    mock_mw.preview_text_edit.highlightManager.clearAllProblemHighlights.assert_called_once()
    mock_mw.ui_updater._apply_highlights_for_block.assert_called_once_with(0)

def test_TextOperationHandler_text_edited_early_returns(handler, mock_mw):
    mock_mw.is_programmatically_changing_text = True
    handler.text_edited()
    mock_mw.data_processor.update_edited_data.assert_not_called()
    
    mock_mw.is_programmatically_changing_text = False
    mock_mw.current_block_idx = -1
    handler.text_edited()
    mock_mw.data_processor.update_edited_data.assert_not_called()
    
    mock_mw.current_block_idx = 0
    mock_mw.edited_text_edit = None
    handler.text_edited()
    mock_mw.data_processor.update_edited_data.assert_not_called()

@patch('handlers.text_operation_handler.QMessageBox')
def test_TextOperationHandler_paste_block_text_errors(mock_mbox, handler, mock_mw):
    mock_mw.current_block_idx = -1
    handler.paste_block_text()
    mock_mbox.warning.assert_called_once()
    
    mock_mw.current_block_idx = 0
    mock_mw.current_game_rules = None
    mock_mbox.reset_mock()
    handler.paste_block_text()
    mock_mbox.warning.assert_called_once()

@patch('handlers.text_operation_handler.QMessageBox')
def test_TextOperationHandler_calculate_width(mock_mbox, handler, mock_mw):
    mock_mw.current_block_idx = -1
    handler.calculate_width_for_data_line_action(0)
    mock_mbox.warning.assert_called_once()
    
    mock_mw.current_block_idx = 0
    mock_mw.font_map = None
    handler.data_processor.get_current_string_text.return_value = ("txt", "src")
    mock_mbox.reset_mock()
    handler.calculate_width_for_data_line_action(0)
    mock_mbox.warning.assert_called_once()
    
    mock_mw.font_map = {"a": 1}
    mock_mw.game_dialog_max_width_pixels = 100
    mock_mw.current_game_rules.get_problem_definitions.return_value = {"P": {"name": "Problem"}}
    mock_mw.helper.get_font_map_for_string.return_value = {}
    
    analyzer = MagicMock()
    analyzer._get_sublines_from_data_string.return_value = ["txt"]
    analyzer.analyze_data_string.return_value = [{"P"}]
    mock_mw.current_game_rules.problem_analyzer = analyzer
    
    with patch('handlers.text_operation_handler.QMessageBox') as mock_dlg:
        with patch('handlers.text_operation_handler.calculate_string_width', return_value=120):
            handler.calculate_width_for_data_line_action(0)
            mock_dlg.return_value.exec_.assert_called_once()

@patch('handlers.text_operation_handler.QMessageBox')
def test_TextOperationHandler_autofix_errors(mock_mbox, handler, mock_mw):
    mock_mw.current_block_idx = -1
    handler.auto_fix_current_string()
    mock_mbox.information.assert_called_once()
    
    mock_mw.current_block_idx = 0
    mock_mw.current_game_rules = None
    mock_mbox.reset_mock()
    handler.auto_fix_current_string()
    mock_mbox.warning.assert_called_once()
    
    mock_mw.current_game_rules = MagicMock()
    mock_mw.current_game_rules.convert_editor_text_to_data.return_value = "d"
    mock_mw.current_game_rules.autofix_data_string.return_value = ("d", False)
    
    mock_mbox.reset_mock()
    handler.auto_fix_current_string()
    # verify status bar updated instead of a change applied
    mock_mw.statusBar.showMessage.assert_called_with("Auto-fix: No changes made.", 2000)
