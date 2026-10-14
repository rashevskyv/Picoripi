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

class _FakeCursor:
    def __init__(self):
        self._position = 0

    def setPosition(self, position):
        self._position = position

    def position(self):
        return self._position


class _FakeEditor:
    """Stands in for the original text editor: records the cursor positions set in it."""

    def __init__(self, block):
        self._block = block
        self.cursor_positions = []

    def document(self):
        return self

    def findBlockByNumber(self, _number):
        return self._block

    def textCursor(self):
        return _FakeCursor()

    def setTextCursor(self, cursor):
        self.cursor_positions.append(cursor.position())

    def ensureCursorVisible(self):
        pass


def test_TextAnalysisHandler_activate_entry(handler, mock_mw):
    mock_mw.block_list_widget = MagicMock()
    mock_mw.list_selection_handler = MagicMock()
    mock_block = MagicMock()
    mock_block.isValid.return_value = True
    mock_block.position.return_value = 50
    editor = _FakeEditor(mock_block)
    mock_mw.original_text_edit = editor
    mock_mw.data_store.current_block_idx = 0

    entry = {"block_idx": 0, "string_idx": 1, "line_idx": 0}
    handler._activate_entry(entry)

    mock_mw.block_list_widget.select_block_by_index.assert_called_with(0)
    mock_mw.list_selection_handler.select_string_by_absolute_index.assert_called_with(1)
    assert editor.cursor_positions == [50]

def test_TextAnalysisHandler_analyze_no_data(handler, mock_mw):
    shown = []
    mock_mw.data = []
    with patch('PyQt6.QtWidgets.QMessageBox.information', new=lambda *args: shown.append(args)):
        handler.analyze_original_text()
    assert shown == [(mock_mw, "Original Text Analysis", "No original data loaded. Please load a file first.")]

def test_TextAnalysisHandler_analyze_no_font_maps(handler, mock_mw):
    warnings = []
    mock_mw.all_font_maps = {}
    with patch('PyQt6.QtWidgets.QMessageBox.warning', new=lambda *args: warnings.append(args)):
        handler.analyze_original_text()
    assert warnings == [(mock_mw, "Original Text Analysis", "No font maps loaded for the current plugin.")]

def test_TextAnalysisHandler_activate_entry_invalid(handler):
    # Should just return early without error
    handler._activate_entry({"block_idx": None})
    handler._activate_entry({"block_idx": "invalid"})
