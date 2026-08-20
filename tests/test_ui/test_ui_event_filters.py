import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QComboBox, QCompleter, QLineEdit, QWidget
from PyQt6.QtTest import QTest
from ui.ui_event_filters import MainWindowEventFilter, TextEditEventFilter
from ui.builders.layout_builder import (
    ClickableLabel,
    NavigableLabel,
    configure_speaker_autocomplete,
)
from ui.main_window.main_window_event_handler import MainWindowEventHandler


def test_story_navigation_double_click_is_owned_by_label(qtbot):
    label = NavigableLabel("Chapter:")
    qtbot.addWidget(label)
    received = []
    label.doubleClicked.connect(lambda: received.append(True))
    label.show()

    QTest.mouseDClick(label, Qt.MouseButton.LeftButton)

    assert received == [True]


def test_original_width_value_emits_single_click(qtbot):
    label = ClickableLabel("128 px")
    qtbot.addWidget(label)
    received = []
    label.clicked.connect(lambda: received.append(True))
    label.show()

    QTest.mouseClick(label, Qt.MouseButton.LeftButton)

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


def test_speaker_click_selects_all_existing_text(qapp, qtbot):
    mw = QWidget()
    mw.speaker_combobox = QComboBox(mw)
    mw.speaker_combobox.setEditable(True)
    mw.speaker_combobox.setCurrentText("System")
    line_edit = mw.speaker_combobox.lineEdit()
    filter_obj = MainWindowEventFilter(mw)
    line_edit.installEventFilter(filter_obj)
    mw.show()

    QTest.mouseClick(line_edit, Qt.MouseButton.LeftButton)
    qtbot.wait(10)

    assert line_edit.selectedText() == "System"


def test_speaker_autocomplete_is_prefix_based_and_case_insensitive(qapp):
    combo = QComboBox()
    combo.setEditable(True)
    combo.addItems(["Fado", "Fyer", "Fia", "Fili", "Midna"])

    configure_speaker_autocomplete(combo)

    completer = combo.completer()
    assert completer.caseSensitivity() == Qt.CaseSensitivity.CaseInsensitive
    assert completer.filterMode() == Qt.MatchFlag.MatchStartsWith
    assert completer.completionMode() == QCompleter.CompletionMode.PopupCompletion
    completer.setCompletionPrefix("fi")
    matches = [
        completer.completionModel().index(row, 0).data()
        for row in range(completer.completionCount())
    ]
    assert matches == ["Fia", "Fili"]


@pytest.mark.parametrize(
    ("placeholder", "marked"),
    [
        ("Search raw script", False),
        ("Find...", False),
        ("Filter entries", False),
        ("Type a term or translation...", True),
    ],
)
def test_all_search_fields_select_existing_text_on_click(
    qapp, qtbot, placeholder, marked
):
    mw = QWidget()
    search = QLineEdit(mw)
    search.setPlaceholderText(placeholder)
    search.setText("Midna")
    if marked:
        search.setProperty("selectAllOnClick", True)
    filter_obj = MainWindowEventFilter(mw)
    search.installEventFilter(filter_obj)
    qtbot.addWidget(mw)
    mw.show()
    mw.activateWindow()

    QTest.mouseClick(search, Qt.MouseButton.LeftButton)
    qtbot.wait(50)

    assert search.selectedText() == "Midna"


def test_speaker_enter_commits_only_first_qcombobox_signal(qapp):
    mw = QWidget()
    mw.speaker_combobox = QComboBox(mw)
    mw.speaker_combobox.setEditable(True)
    mw.speaker_combobox.setCurrentText("System")
    mw.list_selection_handler = MagicMock()
    handler = MainWindowEventHandler(mw)
    pending_timer_callbacks = []

    def save_and_rebuild(_value):
        # Reproduces the tree refresh selecting the next remaining None row.
        mw.speaker_combobox.setCurrentText("None")

    mw.list_selection_handler.save_speaker_for_current_string.side_effect = save_and_rebuild
    with patch(
        "ui.main_window.main_window_event_handler.QTimer.singleShot",
        side_effect=lambda _delay, callback: pending_timer_callbacks.append(callback),
    ):
        handler._commit_speaker_selection(0)  # activated: System
        handler._commit_speaker_selection()   # returnPressed: now reads None without guard

    mw.list_selection_handler.save_speaker_for_current_string.assert_called_once_with(
        "System"
    )
    pending_timer_callbacks[0]()
    assert not mw.speaker_combobox._speaker_commit_pending


def test_clicking_speaker_suggestion_does_not_commit_only_enter_does(qapp):
    mw = QWidget()
    mw.speaker_combobox = QComboBox(mw)
    mw.speaker_combobox.setEditable(True)
    mw.speaker_combobox.addItems(["None", "Fado", "Fyer"])
    mw.list_selection_handler = MagicMock()
    handler = MainWindowEventHandler(mw)

    handler._connect_speaker_combobox()

    # Selecting a suggestion (fires `activated`) fills the field but must not save.
    mw.speaker_combobox.setCurrentIndex(1)
    mw.speaker_combobox.activated.emit(1)
    mw.list_selection_handler.save_speaker_for_current_string.assert_not_called()

    # Only Enter (returnPressed) commits.
    mw.speaker_combobox.lineEdit().returnPressed.emit()
    mw.list_selection_handler.save_speaker_for_current_string.assert_called_once_with(
        "Fado"
    )


def test_speaker_commit_reuses_existing_name_ignoring_case(qapp):
    mw = QWidget()
    mw.speaker_combobox = QComboBox(mw)
    mw.speaker_combobox.setEditable(True)
    mw.speaker_combobox.addItems(["None", "Fado", "Fyer"])
    mw.speaker_combobox.setCurrentText("fado")
    mw.list_selection_handler = MagicMock()
    handler = MainWindowEventHandler(mw)

    handler._commit_speaker_selection()

    mw.list_selection_handler.save_speaker_for_current_string.assert_called_once_with(
        "Fado"
    )
    assert mw.speaker_combobox.currentText() == "Fado"
