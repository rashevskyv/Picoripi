"""Tests for source_tab_widget and reference_text_edit UI."""
import pytest
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QSplitter
from PyQt6.QtCore import Qt
from ui.builders.layout_builder import LayoutBuilder
from components.editor.line_edit.widget import LineNumberedTextEdit
from core.data_store import AppDataStore


@pytest.fixture
def mock_window(qtbot):
    """Build a bare QMainWindow with necessary attributes for LayoutBuilder."""
    window = QMainWindow()
    qtbot.addWidget(window)
    window.data_store = AppDataStore()
    window.game_dialog_max_width_pixels = 300
    window.show_multiple_spaces_as_dots = False
    window.space_dot_color_hex = "#888888"
    window.newline_display_symbol = "¶"
    window.bottom_right_splitter = QSplitter(Qt.Orientation.Horizontal)
    window.data_processor = MagicMock()
    return window


def test_source_tab_widget_layout(mock_window):
    """Verify that _build_original_panel creates a QTabWidget with two tabs."""
    builder = LayoutBuilder(mock_window)
    builder._build_original_panel()

    assert hasattr(mock_window, "source_tab_widget")
    assert isinstance(mock_window.source_tab_widget, QTabWidget)
    assert mock_window.source_tab_widget.count() == 2
    assert "Original" in mock_window.source_tab_widget.tabText(0)
    assert "RU" in mock_window.source_tab_widget.tabText(1) or "Reference" in mock_window.source_tab_widget.tabText(1)

    assert hasattr(mock_window, "original_text_edit")
    assert isinstance(mock_window.original_text_edit, LineNumberedTextEdit)
    assert hasattr(mock_window, "reference_text_edit")
    assert isinstance(mock_window.reference_text_edit, LineNumberedTextEdit)


def test_update_text_views_populates_reference(mock_window):
    """Verify that update_text_views sets text on reference_text_edit."""
    from ui.updaters.text_views_mixin import TextViewsMixin

    class DummyUpdater(TextViewsMixin):
        def __init__(self, mw):
            self.mw = mw
            self.data_processor = mw.data_processor

    builder = LayoutBuilder(mock_window)
    builder._build_original_panel()
    mock_window.edited_text_edit = LineNumberedTextEdit(mock_window)

    updater = DummyUpdater(mock_window)

    mock_window.data_store.data = [["Hello world"]]
    mock_window.data_store.physical_block_idx = 0
    mock_window.data_store.current_string_idx = 0
    mock_window.data_store.reference_data = {(0, 0): "Привет мир"}

    mock_window.data_processor._get_string_from_source.return_value = "Hello world"
    mock_window.data_processor.get_current_string_text.return_value = ("Hello world", False)
    mock_window.current_game_rules = None

    updater._do_update_text_views(False, heavy=False)

    assert mock_window.original_text_edit.toPlainText() == "Hello world"
    assert mock_window.reference_text_edit.toPlainText() == "Привет мир"


def test_update_text_views_populates_multi_reference(mock_window):
    """Verify that update_text_views dynamically adds and populates tabs for all languages."""
    from ui.updaters.text_views_mixin import TextViewsMixin

    class DummyUpdater(TextViewsMixin):
        def __init__(self, mw):
            self.mw = mw
            self.data_processor = mw.data_processor

    builder = LayoutBuilder(mock_window)
    builder._build_original_panel()
    mock_window.edited_text_edit = LineNumberedTextEdit(mock_window)

    updater = DummyUpdater(mock_window)

    mock_window.data_store.data = [["Hello world"]]
    mock_window.data_store.physical_block_idx = 0
    mock_window.data_store.current_string_idx = 0
    mock_window.data_store.reference_languages_data = {
        "Russian (RU)": {(0, 0): "Привет мир"},
        "German (DE)": {(0, 0): "Hallo Welt"},
        "French (FR)": {(0, 0): "Bonjour le monde"},
    }
    mock_window.data_store.reference_data = {(0, 0): "Привет мир"}

    mock_window.data_processor._get_string_from_source.return_value = "Hello world"
    mock_window.data_processor.get_current_string_text.return_value = ("Hello world", False)
    mock_window.current_game_rules = None

    updater._do_update_text_views(False, heavy=False)

    assert mock_window.source_tab_widget.count() == 4
    assert mock_window.source_tab_widget.tabText(0) == "Original (EN)"
    assert "Russian (RU)" in mock_window.source_tab_widget.tabText(1)
    assert "German (DE)" in mock_window.source_tab_widget.tabText(2)
    assert "French (FR)" in mock_window.source_tab_widget.tabText(3)

    assert mock_window.reference_text_edits["German (DE)"].toPlainText() == "Hallo Welt"
    assert mock_window.reference_text_edits["French (FR)"].toPlainText() == "Bonjour le monde"
    assert mock_window.reference_text_edit.toPlainText() == "Привет мир"


def test_editor_headers_and_height_alignment(mock_window):
    """Verify that both panels are built with compact headers and synced heights."""
    builder = LayoutBuilder(mock_window)
    builder._build_original_panel()
    builder._build_middle_panel()
    builder._build_edited_panel()

    assert hasattr(mock_window, "left_header_container")
    assert hasattr(mock_window, "right_header_container")
    assert hasattr(mock_window, "header_sync_filter")

    # Verify that header_sync_filter accounts for tab bar height
    tab_bar_h = (
        mock_window.source_tab_widget.tabBar().sizeHint().height()
        if mock_window.source_tab_widget.tabBar()
        else 28
    )
    if tab_bar_h <= 0:
        tab_bar_h = 28

    # Simulate right header resize
    mock_window.right_header_container.resize(400, 80)
    mock_window.header_sync_filter._sync()

    # Left header height + tab bar height should match right header height
    expected_left_h = max(26, 80 - tab_bar_h)
    assert mock_window.left_header_container.height() == expected_left_h
