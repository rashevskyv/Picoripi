import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtCore import Qt
from handlers.search_handler import SearchHandler

@pytest.fixture
def search_handler(mock_mw):
    mock_mw.ui_updater = MagicMock()
    mock_mw.show_multiple_spaces_as_dots = False
    mock_mw.newline_display_symbol = ""
    mock_mw.search_match_block_indices = set()
    mock_mw.list_selection_handler = MagicMock()
    mock_mw.data = [["apple", "banana", "apple"]]
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    return SearchHandler(mock_mw, MagicMock(), mock_mw.ui_updater)

def test_SearchHandler_init(search_handler, mock_mw):
    assert search_handler.mw == mock_mw
    assert search_handler.current_query == ""

def test_SearchHandler_get_current_search_params(search_handler):
    search_handler.current_query = "test"
    search_handler.is_case_sensitive = True
    assert search_handler.get_current_search_params() == ("test", True, False, True, False)

def test_SearchHandler_get_text_for_search(search_handler, mock_mw):
    mock_mw.data = [["original text"]]
    search_handler.data_processor.get_current_string_text.return_value = ("edited text", False)
    assert search_handler._get_text_for_search(0, 0, True, False) == "original text"
    assert search_handler._get_text_for_search(0, 0, False, False) == "edited text"

def test_SearchHandler_reset_search(search_handler, mock_mw):
    mock_mw.search_panel_widget = MagicMock()
    search_handler.reset_search("query", True, True, True)
    assert search_handler.current_query == "query"
    assert search_handler.last_found_block == -1
    mock_mw.search_panel_widget.clear_status.assert_called_once()

def test_SearchHandler_find_in_text(search_handler):
    assert search_handler._find_in_text("hello world", "world", 0, True) == 6
    assert search_handler._find_in_text("hello world", "WORLD", 0, False) == 6

def test_SearchHandler_find_nth_occurrence_in_display_text(search_handler):
    text = "test apple test"
    pos, length = search_handler._find_nth_occurrence_in_display_text(text, "test", 2, True)
    assert pos == 11
    assert length == 4

def test_SearchHandler_calculate_qtextblock_and_pos_in_block(search_handler):
    text = "line1\nline2\nline3"
    q_idx, pos = search_handler._calculate_qtextblock_and_pos_in_block(text, 8)
    assert q_idx == 1
    assert pos == 2

def test_SearchHandler_clear_all_search_highlights(search_handler, mock_mw):
    for ed_name in ['preview_text_edit', 'original_text_edit', 'edited_text_edit']:
        editor = MagicMock()
        setattr(mock_mw, ed_name, editor)
    search_handler.clear_all_search_highlights()
    mock_mw.preview_text_edit.highlightManager.clear_search_match_highlights.assert_called_once()

@patch('handlers.search_handler.SearchHandler._navigate_to_match')
def test_SearchHandler_find_next(mock_nav, search_handler, mock_mw):
    mock_mw.data = [["apple", "banana"]]
    search_handler.data_processor.get_current_string_text.side_effect = lambda b, s: (mock_mw.data[b][s], False)
    mock_mw.search_panel_widget = MagicMock()
    assert search_handler.find_next("banana", False, False, False) is True
    assert search_handler.last_found_string == 1

@patch('handlers.search_handler.SearchHandler._navigate_to_match')
def test_SearchHandler_find_previous(mock_nav, search_handler, mock_mw):
    mock_mw.data = [["apple", "banana", "cherry"]]
    search_handler.data_processor.get_current_string_text.side_effect = lambda b, s: (mock_mw.data[b][s], False)
    mock_mw.search_panel_widget = MagicMock()
    search_handler.last_found_block = 0
    search_handler.last_found_string = 2
    assert search_handler.find_previous("banana", False, False, False) is True
    assert search_handler.last_found_string == 1

def test_SearchHandler_navigate_to_match_precise(search_handler, mock_mw):
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_mw.block_list_widget = MagicMock()
    for ed_name in ['preview_text_edit', 'original_text_edit', 'edited_text_edit']:
        editor = MagicMock()
        editor.objectName.return_value = ed_name
        doc = editor.document.return_value
        doc.blockCount.return_value = 1
        block = doc.findBlockByNumber.return_value
        block.isValid.return_value = True
        block.position.return_value = 0
        setattr(mock_mw, ed_name, editor)
    
    with patch.object(search_handler, '_get_text_for_search', return_value="apple pie"):
        with patch.object(search_handler, '_calculate_qtextblock_and_pos_in_block', return_value=(0, 0)):
            with patch.object(search_handler, '_find_nth_occurrence_in_display_text', return_value=(0, 5)):
                with patch('PyQt5.QtWidgets.QApplication.processEvents'):
                    with patch('handlers.search_handler.QTextCursor'):
                        with patch('handlers.search_handler.QTreeWidgetItemIterator'):
                            search_handler._navigate_to_match(0, 0, 0, 5, False)
    
    mock_mw.preview_text_edit.highlightManager.add_search_match_highlight.assert_called()

def test_SearchHandler_navigate_to_match_tagless(search_handler, mock_mw):
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    for ed_name in ['preview_text_edit', 'original_text_edit', 'edited_text_edit']:
        editor = MagicMock()
        editor.objectName.return_value = ed_name
        doc = editor.document.return_value
        doc.blockCount.return_value = 1
        block = doc.findBlockByNumber.return_value
        block.isValid.return_value = True
        block.text.return_value = "apple pie"
        block.position.return_value = 0
        setattr(mock_mw, ed_name, editor)
    
    with patch('handlers.search_handler.prepare_text_for_tagless_search', return_value="apple"):
        with patch('handlers.search_handler.convert_raw_to_display_text', return_value="apple"):
            with patch('PyQt5.QtWidgets.QApplication.processEvents'):
                with patch('handlers.search_handler.QTextCursor'):
                    with patch('handlers.search_handler.QTreeWidgetItemIterator'):
                        search_handler._navigate_to_match(0, 0, 0, 5, True)
                        
    mock_mw.preview_text_edit.highlightManager.add_search_match_highlight.assert_called()
