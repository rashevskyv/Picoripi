import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication, QMainWindow, QPlainTextEdit
from PyQt5.QtCore import Qt, QPoint

from components.editor.lnet_tooltips import LNETTooltipLogic


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _make_mw_with_problems():
    """Create a MainWindow where problems_per_subline/edited_data/string_metadata
    are ONLY on data_store (as per post-refactor architecture), NOT directly on mw."""
    mw = QMainWindow()

    mw.data_store = MagicMock()
    mw.data_store.current_block_idx = 0
    mw.data_store.current_string_idx = 1
    mw.data_store.displayed_string_indices = [1]
    # These must be on data_store, NOT on mw directly
    mw.data_store.problems_per_subline = {(0, 1, 0): {"PROBLEM_WIDTH"}}
    mw.data_store.edited_data = {(0, 1): {}}
    mw.data_store.string_metadata = {}

    # current_game_rules stays on mw directly
    mw.current_game_rules = MagicMock()
    mw.current_game_rules.get_problem_definitions.return_value = {
        "PROBLEM_WIDTH": {"name": "Width exceeded", "description": "Line is too wide", "priority": 1}
    }
    mw.detection_enabled = {"PROBLEM_WIDTH": True}

    # Verify the post-refactor invariant: these attrs must NOT be on mw directly
    assert not hasattr(mw, 'problems_per_subline'), (
        "problems_per_subline should NOT be on MainWindow after refactor"
    )
    assert not hasattr(mw, 'edited_data'), (
        "edited_data should NOT be on MainWindow after refactor"
    )
    return mw


@pytest.fixture
def editor_tooltip_setup(app):
    mw = _make_mw_with_problems()

    editor = QPlainTextEdit()
    editor.setObjectName("edited_text_edit")
    editor.setPlainText("Line 1")
    editor.show()  # needs to be visible so cursorForPosition works

    logic = LNETTooltipLogic(editor)
    return logic, editor, mw


def test_tooltip_returns_warning_for_editor(app):
    """
    REGRESSION TEST: Tooltip logic must read problems_per_subline from data_store.

    Before fix: getattr(main_window, 'problems_per_subline', {}) returns {} because
    the attribute was moved to data_store during refactoring.
    Therefore tooltip is None even when there ARE problems.

    After fix: problems are read from main_window.data_store.problems_per_subline
    and the tooltip correctly describes 'Width exceeded'.
    """
    mw = _make_mw_with_problems()
    editor = QPlainTextEdit()
    editor.setObjectName("edited_text_edit")
    editor.setPlainText("This is line one")
    editor.show()

    # Override editor.window() to return our mw
    editor.window = lambda: mw

    logic = LNETTooltipLogic(editor)
    pos = QPoint(5, 5)
    tooltip = logic.find_warning_tooltip_at(pos)

    assert tooltip is not None, (
        "Tooltip was None! This means problems_per_subline was not read from data_store. "
        "Check 'getattr(main_window, problems_per_subline)' calls in lnet_tooltips.py — "
        "they must use 'main_window.data_store.problems_per_subline' instead."
    )
    assert "Width exceeded" in tooltip, (
        f"Expected 'Width exceeded' in tooltip, got: {tooltip!r}"
    )


def test_tooltip_unsaved_indicator_uses_data_store(app):
    """
    REGRESSION TEST: Unsaved indicator (*) in tooltip must read edited_data from data_store.
    Before fix: getattr(mw, 'edited_data', {}) returns {} → no unsaved indicator shown.
    """
    mw = _make_mw_with_problems()
    editor = QPlainTextEdit()
    editor.setObjectName("edited_text_edit")
    editor.setPlainText("This is line one")
    editor.show()
    editor.window = lambda: mw

    logic = LNETTooltipLogic(editor)
    pos = QPoint(5, 5)
    tooltip = logic.find_warning_tooltip_at(pos)

    assert tooltip is not None, "Tooltip was None — problem not shown at all"
    assert "Unsaved" in tooltip, (
        f"Expected 'Unsaved' in tooltip (edited_data has (0,1)), got: {tooltip!r}. "
        "Check 'getattr(mw, edited_data)' → should be 'mw.data_store.edited_data'."
    )
