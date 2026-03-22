import pytest
from PyQt5.QtWidgets import QApplication, QMainWindow, QPlainTextEdit
from PyQt5.QtGui import QPainter, QImage, QPaintEvent
from PyQt5.QtCore import QRect, Qt
from unittest.mock import MagicMock

from components.editor.line_number_area_paint_logic import LNETLineNumberAreaPaintLogic

@pytest.fixture
def paint_logic_setup():
    app = QApplication.instance() or QApplication([])
    
    mw = QMainWindow()
    # Mock data store instead of placing props directly on MW
    mw.data_store = MagicMock()
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 1
    mw.data_store.displayed_string_indices = [0, 1, 2]
    mw.data_store.edited_data = {(0, 1): {}}
    
    mw.string_metadata = {}
    mw.current_game_rules = MagicMock()
    mw.current_game_rules.get_problem_definitions.return_value = {}
    mw.theme = "light"
    mw.detection_enabled = {}
    mw.font_map = None
    mw.problems_per_subline = {}
    
    editor = QPlainTextEdit()
    editor.setObjectName("preview_text_edit")
    editor.setPlainText("Line 1\nLine 2\nLine 3")
    
    # Needs to have some line number area properties mocked
    editor.lineNumberAreaWidth = MagicMock(return_value=50)
    editor.preview_indicator_area_width = 10
    editor.lineNumberArea = MagicMock()
    editor.lineNumberArea.odd_line_background = Qt.white
    editor.lineNumberArea.even_line_background = Qt.gray
    editor.lineNumberArea.number_color = Qt.black
    
    helpers = MagicMock()
    
    logic = LNETLineNumberAreaPaintLogic(editor, helpers, mw)
    return logic, editor, mw

def test_line_number_area_paint_logic_no_attribute_errors(paint_logic_setup):
    logic, editor, mw = paint_logic_setup
    
    # Create a dummy paint event and device
    image = QImage(100, 100, QImage.Format_ARGB32)
    event = QPaintEvent(QRect(0, 0, 100, 100))
    
    # This should not raise AttributeError on 'current_block_idx'
    try:
        logic.execute_paint_event(event, image)
    except AttributeError as e:
        pytest.fail(f"AttributeError raised unexpectedly: {e}")
