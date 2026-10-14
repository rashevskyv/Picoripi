from utils import app_mode
from components.ai_status_dialog import AIStatusDialog

def test_AIStatusDialog_init(qapp):
    dialog = AIStatusDialog()
    assert dialog.detail_label is not None
    assert dialog.detail_label.isHidden() is True
    assert dialog.progress_bar is not None
    assert dialog.progress_bar.isHidden() is True

def test_AIStatusDialog_set_detail_text(qapp):
    dialog = AIStatusDialog()
    
    # Empty text hides the label
    dialog.set_detail_text("")
    assert dialog.detail_label.isHidden() is True
    
    # Valid text shows the label with text
    dialog.set_detail_text("Chapter 1 | File: a.bmg | Line: 5")
    assert dialog.detail_label.isHidden() is False
    assert dialog.detail_label.text() == "Chapter 1 | File: a.bmg | Line: 5"
    
    # Empty text hides it again
    dialog.set_detail_text("")
    assert dialog.detail_label.isHidden() is True

def test_AIStatusDialog_setup_progress_bar(qapp):
    dialog = AIStatusDialog()
    dialog.setup_progress_bar(50, 10)
    
    assert dialog.progress_bar.isHidden() is False
    assert dialog.progress_bar.minimum() == 0
    assert dialog.progress_bar.maximum() == 50
    assert dialog.progress_bar.value() == 10
    assert dialog.progress_bar.format() == "%p% (%v/%m chunks)"

def test_AIStatusDialog_start_and_finish(qapp):
    dialog = AIStatusDialog()
    
    # Setup some pre-existing detail text to make label visible
    dialog.set_detail_text("Arbitrary context")
    assert dialog.detail_label.isHidden() is False
    
    # Start operation (should clear and hide detail label)
    dialog.start("AI Translate Block", is_chunked=True)
    assert dialog.windowTitle() == "AI Translate Block"
    assert dialog.detail_label.isHidden() is True
    assert dialog.detail_label.text() == ""
    assert dialog.progress_bar.format() == "%p% (%v/%m chunks)"
    
    # Set text during operation
    dialog.set_detail_text("Processing row 12")
    assert dialog.detail_label.isHidden() is False
    
    # Finish operation (should clear and hide detail label again)
    dialog.finish()
    assert dialog.detail_label.isHidden() is True
    assert dialog.detail_label.text() == ""


def test_AIStatusDialog_model_name_can_be_set_after_start(qapp):
    dialog = AIStatusDialog()

    dialog.start("Continue from marked examples")
    assert dialog.subtitle_label.isHidden() is True

    dialog.set_model_name("gemini-3.5-flash")

    assert dialog.subtitle_label.isHidden() is False
    assert dialog.subtitle_label.text() == "Model: gemini-3.5-flash"


def test_AIStatusDialog_modeless_and_sleep_checkboxes(qapp):
    dialog = AIStatusDialog()
    assert dialog.isModal() is True
    assert dialog.prevent_sleep_checkbox is not None
    assert dialog.prevent_sleep_checkbox.isChecked() is True
    assert dialog.sleep_after_checkbox is not None
    assert dialog.sleep_after_checkbox.isChecked() is False


def test_AIStatusDialog_bottom_controls_layout(qapp):
    dialog = AIStatusDialog()
    dialog.show()
    try:
        cb1 = dialog.prevent_sleep_checkbox
        cb2 = dialog.sleep_after_checkbox
        bbox = dialog.button_box

        # Checkboxes should be stacked vertically on the left
        assert cb1.y() < cb2.y()
        assert cb1.x() == cb2.x()

        # Cancel button / button_box should be to the right of the checkboxes
        assert bbox.x() > cb1.x()
        assert bbox.x() >= cb1.x() + cb1.width()

        # Button box should be vertically aligned with the checkboxes section
        assert bbox.y() >= cb1.y()
        assert bbox.y() + bbox.height() <= cb2.y() + cb2.height() + 5
    finally:
        dialog.close()



from unittest.mock import patch, ANY

def test_AIStatusDialog_sleep_handling(qapp, monkeypatch):
    sleep_log = []
    monkeypatch.setattr('components.ai_status_dialog.prevent_sleep', lambda: sleep_log.append('prevent'))
    monkeypatch.setattr('components.ai_status_dialog.restore_sleep', lambda: sleep_log.append('restore'))
    dialog = AIStatusDialog()
    try:
        # 1. Start with prevent sleep active
        dialog.prevent_sleep_checkbox.setChecked(True)
        dialog.start("Test title")
        assert sleep_log == ['prevent']

        # 2. Toggle prevent sleep checkbox while visible
        dialog.prevent_sleep_checkbox.setChecked(False)
        assert sleep_log == ['prevent', 'restore']

        dialog.prevent_sleep_checkbox.setChecked(True)
        assert sleep_log == ['prevent', 'restore', 'prevent']

        # 3. Finish, should call restore_sleep
        dialog.finish()
        assert sleep_log == ['prevent', 'restore', 'prevent', 'restore']

        # 4. Finish with sleep_after checked
        dialog.sleep_after_checkbox.setChecked(True)
        with patch('core.auto_sleep_manager.AutoSleepManager.schedule_sleep') as mock_schedule:
            dialog.finish(success=True)
            mock_schedule.assert_called_once_with(
                task_name="Test title",
                delay_seconds=ANY,
                parent_widget=ANY
            )
    finally:
        # A failed step must not leave a running dialog: its close would ask the user.
        dialog.finish(success=False, show_popup=False)


def test_AIStatusDialog_cancel_prevents_sleep(qapp):
    from PyQt6.QtWidgets import QMessageBox
    dialog = AIStatusDialog()
    dialog.sleep_after_checkbox.setChecked(True)
    
    # Start operation
    dialog.start("Test")
    assert dialog.user_cancelled is False
    
    # Simulate user cancel with confirmation
    with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
        dialog.on_cancel()
    assert dialog.user_cancelled is True
    
    # Finish operation and verify schedule_sleep was NOT called
    with patch('core.auto_sleep_manager.AutoSleepManager.schedule_sleep') as mock_schedule:
        dialog.finish(success=True)
        mock_schedule.assert_not_called()

class _Signal:
    """Accepts slot connections; these tests never emit it."""

    def connect(self, _slot):
        pass


class _FakePopup:
    """Stands in for a popup dialog: keeps how it was built and whether it was shown."""

    def __init__(self, parent, translation_details, previous_translations=None):
        self.built_with = (parent, translation_details, previous_translations)
        self.shown = False
        self.destroyed = _Signal()

    def setAttribute(self, *_args):
        pass

    def show(self):
        self.shown = True


def _popup_factory(built):
    """Return a callable that builds a _FakePopup and records it in built."""
    def build(parent, translation_details, previous_translations=None):
        popup = _FakePopup(parent, translation_details, previous_translations)
        built.append(popup)
        return popup
    return build


def test_AIStatusDialog_finish_triggers_comparison(qapp):
    dialog = AIStatusDialog()

    translation_details = {
        0: [(0, "new1"), (1, "new2")]
    }
    previous_translations = {
        0: [(0, "old1"), (1, "old2")]
    }

    was_headless = app_mode.headless

    try:
        # 1. More than 1 line re-translated -> AITranslationComparisonDialog
        app_mode.headless = False
        comparison_built, result_built = [], []
        with patch('dialogs.ai_translation_comparison_dialog.AITranslationComparisonDialog', new=_popup_factory(comparison_built)), \
             patch('dialogs.ai_translation_result_dialog.AITranslationResultDialog', new=_popup_factory(result_built)):
            dialog.finish(success=True, show_popup=True, translation_details=translation_details, previous_translations=previous_translations)

        assert [p.built_with for p in comparison_built] == [(dialog, translation_details, previous_translations)]
        assert [p.shown for p in comparison_built] == [True]
        assert result_built == []

        # 2. Only 1 line re-translated -> AITranslationComparisonDialog
        single_prev = {
            0: [(0, "old1")]
        }

        app_mode.headless = False
        comparison_built, result_built = [], []
        with patch('dialogs.ai_translation_comparison_dialog.AITranslationComparisonDialog', new=_popup_factory(comparison_built)), \
             patch('dialogs.ai_translation_result_dialog.AITranslationResultDialog', new=_popup_factory(result_built)):
            dialog.finish(success=True, show_popup=True, translation_details=translation_details, previous_translations=single_prev)

        assert [p.built_with for p in comparison_built] == [(dialog, translation_details, single_prev)]
        assert [p.shown for p in comparison_built] == [True]
        assert result_built == []
    finally:
        app_mode.headless = was_headless


def test_AIStatusDialog_captures_active_source_window(qapp):
    from PyQt6.QtWidgets import QMainWindow
    win = QMainWindow()
    win.show()
    qapp.setActiveWindow(win)

    dialog = AIStatusDialog()
    dialog.start("Test Active Capture")
    assert dialog.source_window == win
    dialog.finish(show_popup=False)
    win.close()


def test_AIStatusDialog_captures_focused_child_window(qapp):
    from PyQt6.QtWidgets import QMainWindow, QTextEdit
    win = QMainWindow()
    child = QTextEdit(win)
    win.show()
    child.setFocus()
    qapp.setActiveWindow(win)

    dialog = AIStatusDialog()
    dialog.start("Test Child Capture")
    assert dialog.source_window == win
    dialog.finish(show_popup=False)
    win.close()


def test_AIStatusDialog_explicit_source_window(qapp):
    from PyQt6.QtWidgets import QWidget
    win = QWidget()
    win.show()

    dialog = AIStatusDialog()
    dialog.start("Test Explicit", source_window=win)
    assert dialog.source_window == win
    dialog.finish(show_popup=False)
    win.close()


def _record_activation(window):
    """Replace raise_ and activateWindow with recorders; return the calls in order."""
    events = []
    window.raise_ = lambda: events.append("raise")
    window.activateWindow = lambda: events.append("activate")
    return events


def test_AIStatusDialog_finish_without_popup_activates_source(qapp):
    from PyQt6.QtWidgets import QWidget
    win = QWidget()
    win.show()
    events = _record_activation(win)

    dialog = AIStatusDialog()
    dialog.start("Test Return", source_window=win)
    dialog.finish(show_popup=False)

    assert events == ["raise", "activate"]
    win.close()


def test_AIStatusDialog_finish_in_pytest_activates_source(qapp):
    from PyQt6.QtWidgets import QWidget
    win = QWidget()
    win.show()
    events = _record_activation(win)

    dialog = AIStatusDialog()
    dialog.start("Test Pytest Fallback", source_window=win)
    # Headless: the popup is suppressed and the source is activated directly
    dialog.finish(success=True, show_popup=True)

    assert events == ["raise", "activate"]
    win.close()


def test_AIStatusDialog_cancel_and_reject_activates_source(qapp):
    from PyQt6.QtWidgets import QWidget, QMessageBox
    from unittest.mock import patch
    win = QWidget()
    win.show()
    events = _record_activation(win)

    dialog = AIStatusDialog()
    dialog.start("Test Cancel Return", source_window=win)
    with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
        dialog.on_cancel()
    assert events == []
    dialog.finish(success=False, show_popup=False)

    assert events == ["raise", "activate"]
    win.close()


def test_AIStatusDialog_reject_when_not_running_activates_source(qapp):
    from PyQt6.QtWidgets import QWidget
    win = QWidget()
    win.show()
    events = _record_activation(win)

    dialog = AIStatusDialog()
    dialog.source_window = win
    dialog.reject()

    assert events == ["raise", "activate"]
    win.close()


def test_AIStatusDialog_deleted_source_window_safe(qapp):
    from PyQt6.QtWidgets import QWidget
    from PyQt6 import sip
    win = QWidget()
    win.show()

    dialog = AIStatusDialog()
    dialog.start("Test Deleted", source_window=win)
    assert dialog.source_window == win

    # Delete C++ object
    sip.delete(win)
    assert dialog.source_window is None

    # Should not throw any exception
    dialog.finish(show_popup=False)


def test_AIStatusDialog_popup_dismissal_restores_source(qapp):
    from unittest.mock import patch
    from PyQt6.QtWidgets import QWidget, QMessageBox

    win = QWidget()
    win.show()
    events = _record_activation(win)

    dialog = AIStatusDialog()
    dialog.start("Test Popup Dismissal", source_window=win)

    was_headless = app_mode.headless
    try:
        app_mode.headless = False

        def record_popup_show(_box):
            events.append("popup")

        with patch('PyQt6.QtWidgets.QMessageBox.show', new=record_popup_show):
            dialog.finish(success=True, show_popup=True)

            # Source should not have been activated while popup is open
            assert events == ["popup"]

            # Simulate closing/destroying the QMessageBox
            msg_boxes = [w for w in qapp.topLevelWidgets() if isinstance(w, QMessageBox)]
            for mb in msg_boxes:
                mb.destroyed.emit(mb)

            assert events == ["popup", "raise", "activate"]
    finally:
        app_mode.headless = was_headless
        win.close()


def test_AIStatusDialog_cancel_no_keeps_running(qapp):
    from PyQt6.QtWidgets import QMessageBox
    from unittest.mock import MagicMock, patch
    dialog = AIStatusDialog()
    dialog.start("Test Cancel No")
    cancelled_spy = MagicMock()
    dialog.cancelled.connect(cancelled_spy)

    with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.No) as mock_q:
        dialog.on_cancel()
        mock_q.assert_called_once_with(
            dialog,
            "Cancel AI operation?",
            "The current request will stop after the active network step. Are you sure you want to cancel it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

    assert dialog.is_running is True
    assert dialog.user_cancelled is False
    assert dialog.cancel_button.isEnabled() is True
    assert dialog.title_label.text() == "Test Cancel No"
    cancelled_spy.assert_not_called()
    dialog.finish(show_popup=False)


def test_AIStatusDialog_cancel_yes_cancels_and_emits(qapp):
    from PyQt6.QtWidgets import QMessageBox
    from unittest.mock import MagicMock, patch
    dialog = AIStatusDialog()
    dialog.start("Test Cancel Yes")
    cancelled_spy = MagicMock()
    dialog.cancelled.connect(cancelled_spy)

    with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes) as mock_q:
        dialog.on_cancel()
        mock_q.assert_called_once()

    assert dialog.user_cancelled is True
    assert dialog.cancel_button.isEnabled() is False
    assert dialog.title_label.text() == "Cancelling AI Operation..."
    cancelled_spy.assert_called_once()

    # Second cancel invocation while cancelling should NOT prompt again
    with patch('PyQt6.QtWidgets.QMessageBox.question') as mock_q2:
        dialog.on_cancel()
        mock_q2.assert_not_called()
        assert cancelled_spy.call_count == 1

    dialog.finish(show_popup=False)


def test_AIStatusDialog_reject_escape_path_follows_confirmation(qapp):
    from PyQt6.QtWidgets import QMessageBox
    from unittest.mock import MagicMock, patch
    dialog = AIStatusDialog()
    dialog.start("Test Escape Reject")
    cancelled_spy = MagicMock()
    dialog.cancelled.connect(cancelled_spy)

    # Reject with No
    with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
        dialog.reject()
    assert dialog.user_cancelled is False
    cancelled_spy.assert_not_called()

    # Reject with Yes
    with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
        dialog.reject()
    assert dialog.user_cancelled is True
    cancelled_spy.assert_called_once()
    dialog.finish(show_popup=False)


def test_AIStatusDialog_close_event_follows_confirmation(qapp):
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtGui import QCloseEvent
    from unittest.mock import MagicMock, patch
    dialog = AIStatusDialog()
    dialog.start("Test Close Event")
    cancelled_spy = MagicMock()
    dialog.cancelled.connect(cancelled_spy)

    # Close with No
    event = QCloseEvent()
    with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
        dialog.closeEvent(event)
    assert event.isAccepted() is False
    assert dialog.user_cancelled is False
    cancelled_spy.assert_not_called()

    # Close with Yes
    event2 = QCloseEvent()
    with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
        dialog.closeEvent(event2)
    assert event2.isAccepted() is False
    assert dialog.user_cancelled is True
    cancelled_spy.assert_called_once()
    dialog.finish(show_popup=False)


def test_AIStatusDialog_finished_dialog_closes_without_confirmation(qapp):
    from PyQt6.QtGui import QCloseEvent
    from unittest.mock import patch
    dialog = AIStatusDialog()
    # Dialog not started / finished
    assert dialog.is_running is False

    with patch('PyQt6.QtWidgets.QMessageBox.question') as mock_q:
        dialog.reject()
        mock_q.assert_not_called()

    event = QCloseEvent()
    with patch('PyQt6.QtWidgets.QMessageBox.question') as mock_q:
        dialog.closeEvent(event)
        mock_q.assert_not_called()
        assert event.isAccepted() is True
