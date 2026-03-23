import pytest
from unittest.mock import MagicMock, patch
from handlers.issue_scan_handler import IssueScanHandler

@pytest.fixture
def handler(mock_mw):
    mock_mw.ui_updater = MagicMock()
    mock_mw.data_processor = MagicMock()
    mock_mw.current_game_rules = MagicMock()
    mock_mw.data = [["line1\nline2"]]
    mock_mw.problems_per_subline = {}
    mock_mw.string_metadata = {}
    mock_mw.line_width_warning_threshold_pixels = 200
    mock_mw.helper = MagicMock()
    
    return IssueScanHandler(mock_mw, mock_mw.data_processor, mock_mw.ui_updater)

def test_IssueScanHandler_init(handler, mock_mw):
    assert handler.mw == mock_mw

def test_IssueScanHandler_perform_issues_scan_for_block(handler, mock_mw):
    # Setup analyzer
    analyzer = MagicMock()
    mock_mw.current_game_rules.problem_analyzer = analyzer
    # Mock analyze_data_string to return one problem in first subline
    analyzer.analyze_data_string.return_value = [{"TOO_LONG"}]
    
    mock_mw.data_processor.get_current_string_text.return_value = ("line1\nline2", False)
    
    handler._perform_issues_scan_for_block(0)
    
    assert (0, 0, 0) in mock_mw.problems_per_subline
    assert mock_mw.problems_per_subline[(0, 0, 0)] == {"TOO_LONG"}

def test_IssueScanHandler_perform_issues_scan_for_block_sublines(handler, mock_mw):
    # Setup analyzer with analyze_subline instead
    analyzer = MagicMock()
    del analyzer.analyze_data_string # Force use of analyze_subline
    mock_mw.current_game_rules.problem_analyzer = analyzer
    analyzer.analyze_subline.side_effect = [{"PROB1"}, set()]
    
    mock_mw.data_processor.get_current_string_text.return_value = ("line1\nline2", False)
    
    handler._perform_issues_scan_for_block(0)
    
    assert (0, 0, 0) in mock_mw.problems_per_subline
    assert (0, 0, 1) not in mock_mw.problems_per_subline

def test_IssueScanHandler_initial_silent_scan(handler, mock_mw, qapp):
    with patch.object(handler, '_perform_issues_scan_for_block') as mock_scan:
        handler._perform_initial_silent_scan_all_issues()
        # The scan is now async (QTimer), so process events to drain the queue
        qapp.processEvents()
        mock_scan.assert_called_with(0)

@patch('PyQt5.QtWidgets.QMessageBox.information')
def test_IssueScanHandler_rescan_issues_for_single_block(mock_msg, handler, mock_mw):
    mock_mw.current_block_idx = 0
    with patch.object(handler, '_perform_issues_scan_for_block') as mock_scan:
        handler.rescan_issues_for_single_block()
        mock_scan.assert_called_with(0)
        handler.ui_updater.update_block_item_text_with_problem_count.assert_called_with(0)

@patch('PyQt5.QtWidgets.QMessageBox.information')
def test_IssueScanHandler_rescan_all_tags(mock_msg, handler, mock_mw):
    with patch.object(handler, '_perform_initial_silent_scan_all_issues') as mock_scan:
        handler.rescan_all_tags()
        mock_scan.assert_called_once()
        handler.ui_updater.populate_blocks.assert_called_once()
