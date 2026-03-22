import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtWidgets import QApplication, QMainWindow, QPlainTextEdit
from PyQt5.QtGui import QImage, QPaintEvent
from PyQt5.QtCore import QRect, Qt

from components.editor.line_number_area_paint_logic import LNETLineNumberAreaPaintLogic


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def mw_with_problems(app):
    """MainWindow that has problems_per_subline set in data_store."""
    mw = QMainWindow()
    mw.data_store = MagicMock()
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 0
    mw.data_store.displayed_string_indices = [0]
    mw.data_store.edited_data = {}
    # problems_per_subline is in data_store, NOT directly on mw
    mw.data_store.problems_per_subline = {(0, 0, 0): {"PROBLEM_WIDTH"}}
    mw.data_store.string_metadata = {}

    mw.current_game_rules = MagicMock()
    mw.current_game_rules.get_problem_definitions.return_value = {
        "PROBLEM_WIDTH": {"priority": 1, "color": "#FF0000"}
    }
    mw.theme = "light"
    mw.detection_enabled = {"PROBLEM_WIDTH": True}
    mw.font_map = None
    return mw


@pytest.fixture
def editor_setup(mw_with_problems):
    mw = mw_with_problems
    editor = QPlainTextEdit()
    editor.setObjectName("edited_text_edit")
    editor.setPlainText("Line 1")

    editor.lineNumberAreaWidth = MagicMock(return_value=60)
    editor.pixel_width_display_area_width = 0

    editor.lineNumberArea = MagicMock()
    editor.lineNumberArea.odd_line_background = Qt.white
    editor.lineNumberArea.even_line_background = Qt.lightGray
    editor.lineNumberArea.number_color = Qt.black
    editor.lineNumberArea.preview_indicator_width = 4
    editor.lineNumberArea.preview_indicator_spacing = 2

    helpers = MagicMock()
    logic = LNETLineNumberAreaPaintLogic(editor, helpers, mw)
    return logic, editor, mw


def test_no_attribute_error_on_paint(editor_setup):
    """Basic: no AttributeError when painting."""
    logic, editor, mw = editor_setup
    image = QImage(100, 100, QImage.Format_ARGB32)
    event = QPaintEvent(QRect(0, 0, 100, 100))
    try:
        logic.execute_paint_event(event, image)
    except AttributeError as e:
        pytest.fail(f"AttributeError: {e}")


def test_problems_per_subline_is_read_from_data_store(editor_setup):
    """
    REGRESSION TEST: problems_per_subline must be read from data_store,
    not directly from main_window. If it reads from mw directly (old code),
    hasattr(mw, 'problems_per_subline') returns False and problems are ignored,
    causing warning indicators to never appear in the editor.

    This test verifies that the paint logic reads problems from data_store
    and properly considers them when painting.
    """
    logic, editor, mw = editor_setup

    # Verify problems are NOT directly on mw (simulating post-refactor state)
    assert not hasattr(mw, 'problems_per_subline'), (
        "problems_per_subline should NOT be directly on MainWindow after refactor"
    )
    # But they ARE on data_store
    assert hasattr(mw.data_store, 'problems_per_subline'), (
        "problems_per_subline should be in data_store"
    )
    assert (0, 0, 0) in mw.data_store.problems_per_subline, (
        "Test setup problem: expected key (0,0,0) in data_store.problems_per_subline"
    )

    # Patch QPainter.fillRect to track if a problem background color was ever painted
    filled_rects = []

    image = QImage(200, 100, QImage.Format_ARGB32)
    event = QPaintEvent(QRect(0, 0, 200, 100))

    from PyQt5.QtGui import QPainter, QColor
    original_fill = QPainter.fillRect

    def tracking_fill(self_, *args):
        """Track calls to fillRect to detect if problem color was used."""
        if len(args) >= 2:
            color_arg = args[-1]
            if isinstance(color_arg, QColor) and color_arg.red() > 200 and color_arg.green() < 100:
                # This looks like our #FF0000 problem color (or close to it)
                filled_rects.append(args)
        return original_fill(self_, *args)

    with patch.object(QPainter, 'fillRect', tracking_fill):
        logic.execute_paint_event(event, image)

    assert len(filled_rects) > 0, (
        "No problem color was painted! This means problems_per_subline was not read from data_store. "
        "Likely cause: hasattr(main_window_ref, 'problems_per_subline') returns False because "
        "this attribute was moved to data_store during refactoring."
    )
