"""
Regression tests for LNETTooltipLogic.

KEY PRINCIPLE: Tests must use a REAL widget hierarchy (editor embedded in QMainWindow)
and a REAL AppDataStore — NOT mocks. MagicMock returns a new MagicMock for any attribute,
hiding bugs where code accesses wrong attributes (e.g., mw.problems_per_subline instead of
mw.data_store.problems_per_subline). With real objects, AttributeError or wrong value is raised.
"""
import pytest
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QPoint

from core.data_store import AppDataStore
from components.editor.lnet_tooltips import LNETTooltipLogic
from components.editor.line_numbered_text_edit import LineNumberedTextEdit


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_real_main_window(app):
    """
    Create a real QMainWindow with a real AppDataStore,
    and embed a LineNumberedTextEdit into it.
    This tests the actual editor.window() call path.
    """
    mw = QMainWindow()
    # Real AppDataStore — no MagicMock!
    mw.data_store = AppDataStore()

    # These attributes stay directly on mw (not in data_store)
    mw.current_game_rules = None
    mw.detection_enabled = {}

    # Embed a real editor inside mw — ensures editor.window() == mw
    editor = LineNumberedTextEdit(parent=mw)
    editor.setObjectName("edited_text_edit")
    editor.setPlainText("Line 1\nLine 2")
    mw.setCentralWidget(editor)
    mw.show()

    return mw, editor


def test_tooltip_uses_real_data_store_problems(app):
    """
    REGRESSION: find_warning_tooltip_at must find problems from data_store.problems_per_subline.

    Before fix: getattr(mw, 'problems_per_subline', {}) → {} because mw has no such attr.
    After fix:  getattr(mw.data_store, 'problems_per_subline', {}) → real data.

    Uses a REAL widget hierarchy + REAL AppDataStore to catch attribute errors.
    """
    mw, editor = _make_real_main_window(app)

    # Set up real state in AppDataStore
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 1
    mw.data_store.problems_per_subline = {(0, 1, 0): {"PROBLEM_WIDTH"}}

    # Set up game rules on mw (not in data_store)
    from unittest.mock import MagicMock
    mw.current_game_rules = MagicMock()
    mw.current_game_rules.get_problem_definitions.return_value = {
        "PROBLEM_WIDTH": {"name": "Width exceeded", "description": "Line is too wide"}
    }
    mw.detection_enabled = {"PROBLEM_WIDTH": True}

    logic = LNETTooltipLogic(editor)
    # QPoint(5, 5) is inside the editor text area
    tooltip = logic.find_warning_tooltip_at(QPoint(5, 5))

    assert tooltip is not None, (
        "Tooltip was None despite problems_per_subline being set in data_store. "
        "Check lnet_tooltips.py — 'getattr(main_window, ...) must be 'getattr(main_window.data_store, ...)'"
    )
    assert "Width exceeded" in tooltip, f"Expected problem name in tooltip, got: {tooltip!r}"
    mw.close()


def test_tooltip_uses_real_data_store_edited_data(app):
    """
    REGRESSION: Unsaved-changes indicator (*) must read edited_data from data_store.

    Before fix: getattr(mw, 'edited_data', {}) → {} because mw has no such attr.
    After fix:  getattr(mw.data_store, 'edited_data', {}) → real {(0, 1): ...}
    """
    mw, editor = _make_real_main_window(app)

    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 1
    mw.data_store.edited_data = {(0, 1): ["some change"]}
    # No problems — only unsaved indicator
    mw.data_store.problems_per_subline = {}

    logic = LNETTooltipLogic(editor)
    tooltip = logic.find_warning_tooltip_at(QPoint(5, 5))

    assert tooltip is not None, (
        "Tooltip was None despite edited_data having (0,1) in data_store. "
        "Check 'getattr(mw, edited_data)' → should be 'getattr(mw.data_store, edited_data)'"
    )
    assert "Unsaved" in tooltip, f"Expected 'Unsaved' in tooltip, got: {tooltip!r}"
    mw.close()


def test_tooltip_returns_none_when_no_problems(app):
    """Sanity check: no tooltip when no problems and no unsaved changes."""
    mw, editor = _make_real_main_window(app)

    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 1
    mw.data_store.problems_per_subline = {}
    mw.data_store.edited_data = {}

    logic = LNETTooltipLogic(editor)
    tooltip = logic.find_warning_tooltip_at(QPoint(5, 5))
    assert tooltip is None, f"Expected None when no problems, got: {tooltip!r}"
    mw.close()
