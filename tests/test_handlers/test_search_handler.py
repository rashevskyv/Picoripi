import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
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
    assert search_handler._find_in_text("hello world", "world", 0, True) == (6, 5)
    # Under smart search rules, "WORLD" contains uppercase letters so it is matched case-sensitively, returning (-1, 0) against lowercase "world"
    assert search_handler._find_in_text("hello world", "WORLD", 0, False) == (-1, 0)
    assert search_handler._find_in_text("hello world", "world", 0, False) == (6, 5)

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

class _RecordingHighlights:
    """Highlight manager stand-in: records the search highlight calls of one editor into a shared log."""

    def __init__(self, editor_name, log):
        self._editor_name = editor_name
        self._log = log

    def clear_search_match_highlights(self):
        self._log.append((self._editor_name, "clear"))

    def add_search_match_highlight(self, *args):
        self._log.append((self._editor_name, "add", args))


def test_SearchHandler_clear_all_search_highlights(search_handler, mock_mw):
    log = []
    for ed_name in ['preview_text_edit', 'original_text_edit', 'edited_text_edit']:
        editor = MagicMock()
        editor.highlightManager = _RecordingHighlights(ed_name, log)
        setattr(mock_mw, ed_name, editor)
    search_handler.clear_all_search_highlights()
    assert sorted(log) == [
        ('edited_text_edit', 'clear'),
        ('original_text_edit', 'clear'),
        ('preview_text_edit', 'clear'),
    ]

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
    log = []
    for ed_name in ['preview_text_edit', 'original_text_edit', 'edited_text_edit']:
        editor = MagicMock()
        editor.objectName.return_value = ed_name
        editor.highlightManager = _RecordingHighlights(ed_name, log)
        doc = editor.document.return_value
        doc.blockCount.return_value = 1
        block = doc.findBlockByNumber.return_value
        block.isValid.return_value = True
        block.position.return_value = 0
        setattr(mock_mw, ed_name, editor)

    with patch.object(search_handler, '_get_text_for_search', return_value="apple pie"):
        with patch.object(search_handler, '_calculate_qtextblock_and_pos_in_block', return_value=(0, 0)):
            with patch.object(search_handler, '_find_nth_occurrence_in_display_text', return_value=(0, 5)):
                with patch('PyQt6.QtWidgets.QApplication.processEvents'):
                    with patch('handlers.search_handler.QTextCursor'):
                        with patch('handlers.search_handler.QTreeWidgetItemIterator'):
                            search_handler._navigate_to_match(0, 0, 0, 5, False)

    assert ('preview_text_edit', 'add', (0, 0, 5)) in log

def test_SearchHandler_navigate_to_match_tagless(search_handler, mock_mw):
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    log = []
    for ed_name in ['preview_text_edit', 'original_text_edit', 'edited_text_edit']:
        editor = MagicMock()
        editor.objectName.return_value = ed_name
        editor.highlightManager = _RecordingHighlights(ed_name, log)
        doc = editor.document.return_value
        doc.blockCount.return_value = 1
        block = doc.findBlockByNumber.return_value
        block.isValid.return_value = True
        block.text.return_value = "apple pie"
        block.position.return_value = 0
        setattr(mock_mw, ed_name, editor)

    with patch('handlers.search_handler.prepare_text_for_tagless_search', return_value="apple"):
        with patch('handlers.search_handler.convert_raw_to_display_text', return_value="apple"):
            with patch('PyQt6.QtWidgets.QApplication.processEvents'):
                with patch('handlers.search_handler.QTextCursor'):
                    with patch('handlers.search_handler.QTreeWidgetItemIterator'):
                        search_handler._navigate_to_match(0, 0, 0, 5, True)

    assert ('preview_text_edit', 'add', (0, 0, 5)) in log


def test_SearchHandler_integration_navigate_between_blocks(search_handler, mock_mw):
    mock_mw.data = [["apple"], ["banana"]]
    mock_mw.data_store.data = [["apple"], ["banana"]]
    mock_mw.current_block_idx = 0
    mock_mw.current_string_idx = 0
    mock_mw.block_list_widget = MagicMock()
    mock_mw.list_selection_handler._get_displayed_indices.return_value = [0]
    search_handler.data_processor.get_current_string_text.side_effect = lambda b, s: (mock_mw.data[b][s], False)
    
    for ed_name in ['preview_text_edit', 'original_text_edit', 'edited_text_edit']:
        editor = MagicMock()
        editor.objectName.return_value = ed_name
        doc = editor.document.return_value
        doc.blockCount.return_value = 1
        block = doc.findBlockByNumber.return_value
        block.isValid.return_value = True
        block.text.return_value = "banana"
        block.position.return_value = 0
        setattr(mock_mw, ed_name, editor)

    # Set up items in block list widget
    item1 = MagicMock()
    item1.data.side_effect = lambda col, role: 1 if role == Qt.ItemDataRole.UserRole else None
    
    class FakeIterator:
        def __init__(self, widget):
            self.items = [item1]
            self.idx = 0
        def value(self):
            if self.idx < len(self.items):
                return self.items[self.idx]
            return None
        def __iadd__(self, steps):
            self.idx += steps
            return self
            
    with patch('handlers.search_handler.QTreeWidgetItemIterator', FakeIterator):
        with patch('handlers.search_handler.QTextCursor'):
            # Find next banana
            found = search_handler.find_next("banana", False, False, False)
            assert found is True
            assert search_handler.last_found_block == 1
            assert search_handler.last_found_string == 0
            
            # Verify block change was triggered
            mock_mw.block_list_widget.setCurrentItem.assert_called_with(item1)
            mock_mw.list_selection_handler.select_string_by_absolute_index.assert_called_with(0)
            
            # Verify highlights were applied with correct arguments (0, 0, 6 for "banana")
            mock_mw.preview_text_edit.highlightManager.add_search_match_highlight.assert_called_with(0, 0, 6)
            mock_mw.original_text_edit.highlightManager.add_search_match_highlight.assert_called_with(0, 0, 6)
            mock_mw.edited_text_edit.highlightManager.add_search_match_highlight.assert_called_with(0, 0, 6)

