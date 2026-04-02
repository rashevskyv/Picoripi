import pytest
from unittest.mock import MagicMock
from PyQt5.QtGui import QPainter, QColor, QPaintEvent
from PyQt5.QtCore import QRect, Qt
from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from components.editor.line_number_area_paint_logic import LNETLineNumberAreaPaintLogic

import pytest
from unittest.mock import MagicMock
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import QRect, Qt
from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from components.editor.line_number_area_paint_logic import LNETLineNumberAreaPaintLogic

class MockPainterRecorder:
    def __init__(self):
        self.rects_filled = []

    def setFont(self, font): pass
    def fillRect(self, *args):
        if len(args) == 2:
            self.rects_filled.append((args[0], args[1]))
        elif len(args) == 5:
            # x, y, w, h, color
            self.rects_filled.append((QRect(args[0], args[1], args[2], args[3]), args[4]))
    def setPen(self, *args): pass
    def drawText(self, *args): pass
    def end(self): pass
    def fontMetrics(self): return MagicMock()

def test_paint_preview_warning_stripes(monkeypatch):
    from PyQt5.QtWidgets import QMainWindow
    editor = LineNumberedTextEdit(parent=None)
    editor.setObjectName("preview_text_edit")
    editor.setPlainText("Line 1")
    editor.preview_indicator_area_width = 15 # Required for extra_part_width
    
    mock_mw = MagicMock(spec=QMainWindow)
    mock_mw.data_store = MagicMock()
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = -1
    mock_mw.data_store.displayed_string_indices = [5] # Real idx is 5
    
    # In preview_text_edit, problems should be checked for the whole string.
    # Currently the bug checks for subline == preview line index
    mock_mw.data_store.problems_per_subline = {
        (0, 5, 0): {"dummy_problem_id"} 
    }
    
    mock_rules = MagicMock()
    mock_rules.get_problem_definitions.return_value = {
        "dummy_problem_id": {"priority": 1, "color": Qt.red}
    }
    mock_mw.current_game_rules = mock_rules
    mock_mw.detection_enabled = {"dummy_problem_id": True}
    
    helpers = MagicMock()
    
    paint_logic = LNETLineNumberAreaPaintLogic(editor, helpers, mock_mw)
    
    mock_painter_device = MagicMock()
    mock_event = MagicMock(rect=lambda: QRect(0, 0, 100, 100))
    
    recorder = MockPainterRecorder()
    monkeypatch.setattr("components.editor.line_number_area_paint_logic.QPainter", lambda *a: recorder)
    
    paint_logic.execute_paint_event(mock_event, mock_painter_device)
    
    # Verify that a red stripe (QColor(Qt.red) with alpha 220) was drawn
    found_red_stripe = False
    for rect, color in recorder.rects_filled:
        if isinstance(color, QColor) and color.name() == QColor(Qt.red).name() and color.alpha() == 220:
            found_red_stripe = True
            break
            
    if not found_red_stripe:
        print("\nRectangles filled:")
        for r, c in recorder.rects_filled:
            color_str = f"{c.name()} alpha={c.alpha()}" if isinstance(c, QColor) else str(c)
            print(f"Rect: {r}, Color: {color_str}")
            
    assert found_red_stripe, "Warning stripe was not drawn for preview line!"
