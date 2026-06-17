# tests/test_dialogs/test_ai_translation_comparison_dialog.py
import pytest
from dialogs.ai_translation_comparison_dialog import AITranslationComparisonDialog
from PyQt6.QtCore import Qt
from unittest.mock import MagicMock, patch

def test_AITranslationComparisonDialog_init(qapp):
    translation_details = {
        0: [(0, "New Line 1"), (1, "New Line 2")]
    }
    previous_translations = {
        0: [(0, "Old Line 1"), (1, "Old Line 2")]
    }
    
    dialog = AITranslationComparisonDialog(None, translation_details, previous_translations)
    
    assert dialog.windowTitle() == "AI Translation Comparison"
    assert dialog.table_widget.rowCount() == 2
    assert dialog.table_widget.columnCount() == 3
    
    # Check table content
    assert dialog.table_widget.item(0, 0).text() == "Block 1\nLine 1"
    assert dialog.table_widget.item(0, 1).text() == "Old Line 1"
    assert dialog.table_widget.item(0, 2).text() == "New Line 1"
    
    assert dialog.table_widget.item(1, 0).text() == "Block 1\nLine 2"
    assert dialog.table_widget.item(1, 1).text() == "Old Line 2"
    assert dialog.table_widget.item(1, 2).text() == "New Line 2"
    
    dialog.accept()

def test_AITranslationComparisonDialog_empty_behavior(qapp):
    # Ensure no crashes on empty/missing matching rows
    dialog = AITranslationComparisonDialog(None, {}, {})
    assert dialog.table_widget.rowCount() == 0
    dialog.accept()

def test_AITranslationComparisonDialog_cell_clicks(qapp):
    translation_details = {
        0: [(0, "New Line 1")]
    }
    previous_translations = {
        0: [(0, "Old Line 1")]
    }
    
    # Mock MainWindow
    mock_mw = MagicMock()
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_category_name = None
    mock_mw.data_store.current_chapter_id = None
    mock_mw.data_processor.get_current_string_text.return_value = ("Old Line 1", "data")
    
    dialog = AITranslationComparisonDialog(mock_mw, translation_details, previous_translations)
    
    # Verify metadata and highlights
    assert dialog.row_metadata[0]["current_choice"] == "new"
    
    # Click on Column 1 (Old Translation) to revert
    dialog._on_cell_clicked(0, 1)
    assert dialog.row_metadata[0]["current_choice"] == "old"
    mock_mw.data_processor.update_edited_data.assert_not_called()
    
    # Click on Column 2 (New Translation) to apply again
    mock_mw.data_processor.update_edited_data.reset_mock()
    dialog._on_cell_clicked(0, 2)
    assert dialog.row_metadata[0]["current_choice"] == "new"
    mock_mw.data_processor.update_edited_data.assert_not_called()
    
    # DB update should happen when accepted
    dialog.accept()
    mock_mw.data_processor.update_edited_data.assert_called_with(0, 0, "New Line 1", action_type="TRANSLATE", skip_ui_refresh=True)

def test_AITranslationComparisonDialog_item_changed(qapp):
    translation_details = {
        0: [(0, "New Line 1")]
    }
    previous_translations = {
        0: [(0, "Old Line 1")]
    }
    
    mock_mw = MagicMock()
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_category_name = None
    mock_mw.data_store.current_chapter_id = None
    mock_mw.data_processor.get_current_string_text.return_value = ("Old Line 1", "data")
    
    dialog = AITranslationComparisonDialog(mock_mw, translation_details, previous_translations)
    
    # Simulate editing the item in column 2
    item = dialog.table_widget.item(0, 2)
    item.setText("Manually Edited Text")
    dialog._on_item_changed(item)
    
    assert dialog.row_metadata[0]["new_text"] == "Manually Edited Text"
    assert dialog.row_metadata[0]["current_choice"] == "new"
    mock_mw.data_processor.update_edited_data.assert_not_called()
    
    # DB update should happen when accepted
    dialog.accept()
    mock_mw.data_processor.update_edited_data.assert_called_with(0, 0, "Manually Edited Text", action_type="TRANSLATE", skip_ui_refresh=True)

def test_AITranslationComparisonDialog_variation_chosen(qapp):
    translation_details = {
        0: [(0, "New Line 1")]
    }
    previous_translations = {
        0: [(0, "Old Line 1")]
    }
    
    mock_mw = MagicMock()
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_category_name = None
    mock_mw.data_store.current_chapter_id = None
    mock_mw.translation_handler._format_and_wrap_translation = lambda text, b, s: text
    mock_mw.data_processor.get_current_string_text.return_value = ("Old Line 1", "data")
    
    dialog = AITranslationComparisonDialog(mock_mw, translation_details, previous_translations)
    
    # Simulate variations callback
    dialog._on_variation_chosen(0, "AI Chosen Variation")
    
    assert dialog.row_metadata[0]["new_text"] == "AI Chosen Variation"
    assert dialog.row_metadata[0]["current_choice"] == "new"
    assert dialog.table_widget.item(0, 2).text() == "AI Chosen Variation"
    mock_mw.data_processor.update_edited_data.assert_not_called()
    
    # DB update should happen when accepted
    dialog.accept()
    mock_mw.data_processor.update_edited_data.assert_called_with(0, 0, "AI Chosen Variation", action_type="TRANSLATE", skip_ui_refresh=True)

class MockHighlighter:
    def __init__(self, doc, main_window_ref=None, editor_widget_ref=None):
        self.doc = doc
        self.mw = main_window_ref
        self._editor_widget_ref = editor_widget_ref
        self._glossary_manager = None
        self._spellchecker_enabled = False
        if editor_widget_ref:
            editor_widget_ref.highlighter = self
    def set_glossary_manager(self, gm):
        self._glossary_manager = gm
    def set_spellchecker_enabled(self, enabled):
        self._spellchecker_enabled = enabled

def test_MultilineItemDelegate_highlighter_setup(qapp):
    from dialogs.ai_translation_comparison_dialog import MultilineItemDelegate
    from PyQt6.QtWidgets import QTableWidget, QDialog
    
    mock_mw = MagicMock()
    mock_mw.spellchecker_enabled = True
    mock_mw.translation_handler._glossary_manager = "mock_glossary_manager"
    
    dialog = QDialog()
    dialog.mw = mock_mw
    
    delegate = MultilineItemDelegate(dialog)
    table = QTableWidget(1, 3, parent=dialog)
    
    # We patch JsonTagHighlighter with our MockHighlighter to avoid full QSyntaxHighlighter initialization errors in isolation
    with patch("utils.syntax_highlighter.JsonTagHighlighter", MockHighlighter):
        editor = delegate.createEditor(table, None, table.model().index(0, 2))
        
        assert editor.objectName() == "comparison_editor_text_edit"
        assert hasattr(editor, "highlighter")
        assert editor.highlighter._glossary_manager == "mock_glossary_manager"
        assert editor.highlighter._spellchecker_enabled is True

def test_MultilineItemDelegate_events(qapp):
    from dialogs.ai_translation_comparison_dialog import MultilineItemDelegate
    from PyQt6.QtWidgets import QTextEdit
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QKeyEvent
    
    delegate = MultilineItemDelegate(None)
    
    editor = QTextEdit()
    
    # Mock signals
    delegate.commitData = MagicMock()
    delegate.closeEditor = MagicMock()
    
    # Test KeyPress Ctrl+Enter
    event_ctrl_enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    res = delegate.eventFilter(editor, event_ctrl_enter)
    assert res is True
    delegate.commitData.emit.assert_called_once_with(editor)
    delegate.closeEditor.emit.assert_called_once_with(editor)
    
    # Reset mocks
    delegate.commitData.reset_mock()
    delegate.closeEditor.reset_mock()
    
    # Test KeyPress Escape
    event_escape = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    res = delegate.eventFilter(editor, event_escape)
    assert res is True
    delegate.commitData.emit.assert_not_called()
    delegate.closeEditor.emit.assert_called_once_with(editor)
    
    # Reset mocks
    delegate.commitData.reset_mock()
    delegate.closeEditor.reset_mock()
    
    # Test FocusOut
    event_focus_out = QEvent(QEvent.Type.FocusOut)
    res = delegate.eventFilter(editor, event_focus_out)
    assert res is True
    delegate.commitData.emit.assert_called_once_with(editor)
    delegate.closeEditor.emit.assert_called_once_with(editor)


def test_AITranslationComparisonDialog_accept_reject(qapp):
    translation_details = {
        0: [(0, "New Line 1")]
    }
    previous_translations = {
        0: [(0, "Old Line 1")]
    }
    
    mock_mw = MagicMock()
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_category_name = None
    mock_mw.data_store.current_chapter_id = None
    mock_mw.data_processor.get_current_string_text.return_value = ("Old Line 1", "data")
    
    dialog = AITranslationComparisonDialog(mock_mw, translation_details, previous_translations)
    
    # Verify initial database states captured
    assert dialog.initial_database_states[(0, 0)] == "Old Line 1"
    
    # Test accept writes chosen changes
    mock_mw.data_processor.update_edited_data.reset_mock()
    dialog.accept()
    mock_mw.data_processor.update_edited_data.assert_called_with(0, 0, "New Line 1", action_type="TRANSLATE", skip_ui_refresh=True)
    
    # Test reject restores initial states
    dialog = AITranslationComparisonDialog(mock_mw, translation_details, previous_translations)
    mock_mw.data_processor.get_current_string_text.return_value = ("Changed Line 1", "data")
    mock_mw.data_processor.update_edited_data.reset_mock()
    dialog.reject()
    mock_mw.data_processor.update_edited_data.assert_called_with(0, 0, "Old Line 1", action_type="TRANSLATE", skip_ui_refresh=True)

def test_AITranslationComparisonDialog_double_click(qapp):
    translation_details = {
        0: [(0, "New Line 1")]
    }
    previous_translations = {
        0: [(0, "Old Line 1")]
    }
    
    mock_mw = MagicMock()
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_category_name = None
    mock_mw.data_store.current_chapter_id = None
    mock_mw.data_processor.get_current_string_text.return_value = ("Old Line 1", "data")
    
    dialog = AITranslationComparisonDialog(mock_mw, translation_details, previous_translations)
    
    # Double click on Column 0 (Location)
    dialog._on_cell_double_clicked(0, 0)
    mock_mw.translation_handler.ui_handler._activate_entry.assert_called_with({
        "block_idx": 0,
        "string_idx": 0
    })
    
    # Double click on Column 1 (Old Translation)
    mock_mw.translation_handler.ui_handler._activate_entry.reset_mock()
    dialog._on_cell_double_clicked(0, 1)
    mock_mw.translation_handler.ui_handler._activate_entry.assert_called_with({
        "block_idx": 0,
        "string_idx": 0
    })
    
    # Double click on Column 2 should NOT navigate
    mock_mw.translation_handler.ui_handler._activate_entry.reset_mock()
    dialog._on_cell_double_clicked(0, 2)
    mock_mw.translation_handler.ui_handler._activate_entry.assert_not_called()


def test_AITranslationComparisonDialog_single_click_location(qapp):
    translation_details = {
        0: [(0, "New Line 1")]
    }
    previous_translations = {
        0: [(0, "Old Line 1")]
    }
    
    mock_mw = MagicMock()
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_processor.get_current_string_text.return_value = ("Old Line 1", "data")
    
    dialog = AITranslationComparisonDialog(mock_mw, translation_details, previous_translations)
    
    # Single click on Column 0 (Location)
    dialog._on_cell_clicked(0, 0)
    mock_mw.translation_handler.ui_handler._activate_entry.assert_called_with({
        "block_idx": 0,
        "string_idx": 0
    })
    
    # Single click on Column 1 should update choice instead of navigation
    mock_mw.translation_handler.ui_handler._activate_entry.reset_mock()
    dialog._on_cell_clicked(0, 1)
    mock_mw.translation_handler.ui_handler._activate_entry.assert_not_called()
    assert dialog.row_metadata[0]["current_choice"] == "old"


def test_AITranslationComparisonDialog_undo_redo(qapp):
    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtCore import QEvent
    
    translation_details = {
        0: [(0, "New Line 1")]
    }
    previous_translations = {
        0: [(0, "Old Line 1")]
    }
    
    mock_mw = MagicMock()
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_category_name = None
    mock_mw.data_store.current_chapter_id = None
    mock_mw.data_processor.get_current_string_text.return_value = ("Old Line 1", "data")
    
    dialog = AITranslationComparisonDialog(mock_mw, translation_details, previous_translations)
    
    # 1. Test initial states
    assert len(dialog.undo_stack) == 0
    assert len(dialog.redo_stack) == 0
    assert dialog.row_metadata[0]["current_choice"] == "new"
    
    # 2. Trigger cell click (change choice from "new" to "old")
    # This should save state to undo stack
    dialog._on_cell_clicked(0, 1)
    assert len(dialog.undo_stack) == 1
    assert len(dialog.redo_stack) == 0
    assert dialog.row_metadata[0]["current_choice"] == "old"
    
    # 3. Perform undo
    dialog.undo()
    assert len(dialog.undo_stack) == 0
    assert len(dialog.redo_stack) == 1
    assert dialog.row_metadata[0]["current_choice"] == "new"
    
    # 4. Perform redo
    dialog.redo()
    assert len(dialog.undo_stack) == 1
    assert len(dialog.redo_stack) == 0
    assert dialog.row_metadata[0]["current_choice"] == "old"
    
    # 5. Test keyPressEvent Ctrl+Z
    # Revert to "new" so we can undo again
    dialog.undo()
    assert dialog.row_metadata[0]["current_choice"] == "new"
    # Click again to push to undo_stack
    dialog._on_cell_clicked(0, 1)
    assert dialog.row_metadata[0]["current_choice"] == "old"
    
    # Send Ctrl+Z event
    event_undo = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    dialog.keyPressEvent(event_undo)
    assert event_undo.isAccepted()
    assert dialog.row_metadata[0]["current_choice"] == "new"
    
    # Send Ctrl+Y event
    event_redo = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    dialog.keyPressEvent(event_redo)
    assert event_redo.isAccepted()
    assert dialog.row_metadata[0]["current_choice"] == "old"
    
    # Send random key event, should not trigger undo/redo or be accepted by custom handler
    event_other = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
    dialog.keyPressEvent(event_other)
    assert not event_other.isAccepted()



