import pytest
from unittest.mock import MagicMock
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QComboBox, QWidget
from PyQt6.QtTest import QTest
from ui.ui_event_filters import MainWindowEventFilter, TextEditEventFilter
from ui.builders.layout_builder import NavigableLabel


def test_story_navigation_double_click_is_owned_by_label(qtbot):
    label = NavigableLabel("Chapter:")
    qtbot.addWidget(label)
    received = []
    label.doubleClicked.connect(lambda: received.append(True))
    label.show()

    QTest.mouseDClick(label, Qt.MouseButton.LeftButton)

    assert received == [True]

def test_TextEditEventFilter_alt_up_down_skips_empty(mock_mw):
    # Setup mock data: 5 strings, indices 0-4
    # String 0: has text
    # String 1: empty
    # String 2: empty
    # String 3: has text (visible tag)
    # String 4: empty
    mock_mw.data_store.current_block_idx = 0
    mock_mw.data_store.current_string_idx = 0
    
    # Mock displayed indices (we are at 0, moving down should skip 1 and 2, and go to 3)
    mock_mw.data_store.displayed_string_indices = [0, 1, 2, 3, 4]
    
    # Mock get_current_string_text returning text for indices
    # We want index 0 to have "Hello", index 1 and 2 to be empty, 3 to have "{(X)}", 4 to be empty
    def mock_get_current_string_text(b, s):
        if s == 0:
            return "Hello", "edited"
        elif s in (1, 2):
            return "", "edited"
        elif s == 3:
            return "{(X)}", "edited"
        else:
            return "", "edited"
            
    mock_mw.data_processor.get_current_string_text.side_effect = mock_get_current_string_text
    
    # Mock list_selection_handler methods
    handler_mock = MagicMock()
    handler_mock._get_displayed_indices.return_value = [0, 1, 2, 3, 4]
    mock_mw.list_selection_handler = handler_mock
    
    filter_obj = TextEditEventFilter(mock_mw)
    
    # 1. Test Alt+Down from 0. It should skip 1, 2 and go to 3.
    event_down = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    res = filter_obj.eventFilter(mock_mw.preview_text_edit, event_down)
    
    assert res is True
    # Verify string_selected_from_preview was called with preview index 3
    handler_mock.string_selected_from_preview.assert_called_once_with(3)
    
    # Reset mock
    handler_mock.reset_mock()
    
    # 2. Test Alt+Up from 3. It should skip 2, 1 and go to 0.
    mock_mw.data_store.current_string_idx = 3
    event_up = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
    res_up = filter_obj.eventFilter(mock_mw.preview_text_edit, event_up)
    
    assert res_up is True
    handler_mock.string_selected_from_preview.assert_called_once_with(0)

def test_MainWindowEventFilter_routes_speaker_line_edit_undo_to_app_action(qapp):
    mw = QWidget()
    mw.speaker_combobox = QComboBox(mw)
    mw.speaker_combobox.setEditable(True)
    mw.undo_typing_action = MagicMock()
    mw.redo_typing_action = MagicMock()

    filter_obj = MainWindowEventFilter(mw)
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)

    assert filter_obj.eventFilter(mw.speaker_combobox.lineEdit(), event) is True
    mw.undo_typing_action.trigger.assert_called_once()
    mw.redo_typing_action.trigger.assert_not_called()

def test_MainWindowEventFilter_routes_speaker_popup_redo_to_app_action(qapp):
    mw = QWidget()
    mw.speaker_combobox = QComboBox(mw)
    mw.speaker_combobox.setEditable(True)
    mw.speaker_combobox.addItems(["Hero", "Villain"])
    mw.undo_typing_action = MagicMock()
    mw.redo_typing_action = MagicMock()

    filter_obj = MainWindowEventFilter(mw)
    modifiers = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Z, modifiers)

    assert filter_obj.eventFilter(mw.speaker_combobox.view().viewport(), event) is True
    mw.redo_typing_action.trigger.assert_called_once()
    mw.undo_typing_action.trigger.assert_not_called()
