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


from unittest.mock import patch, ANY

@patch('components.ai_status_dialog.prevent_sleep')
@patch('components.ai_status_dialog.restore_sleep')
@patch('components.ai_status_dialog.put_to_sleep')
def test_AIStatusDialog_sleep_handling(mock_put, mock_restore, mock_prevent, qapp):
    dialog = AIStatusDialog()
    
    # 1. Start with prevent sleep active
    dialog.prevent_sleep_checkbox.setChecked(True)
    dialog.start("Test title")
    mock_prevent.assert_called_once()
    
    # 2. Toggle prevent sleep checkbox while visible
    dialog.prevent_sleep_checkbox.setChecked(False)
    mock_restore.assert_called_once()
    
    dialog.prevent_sleep_checkbox.setChecked(True)
    assert mock_prevent.call_count == 2
    
    # 3. Finish, should call restore_sleep
    mock_restore.reset_mock()
    dialog.finish()
    mock_restore.assert_called_once()
    
    # 4. Finish with sleep_after checked
    dialog.sleep_after_checkbox.setChecked(True)
    with patch('core.auto_sleep_manager.AutoSleepManager.schedule_sleep') as mock_schedule:
        dialog.finish(success=True)
        mock_schedule.assert_called_once_with(
            task_name="Test title",
            delay_seconds=ANY,
            parent_widget=ANY
        )


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

def test_AIStatusDialog_finish_triggers_comparison(qapp):
    from unittest.mock import patch
    import sys
    dialog = AIStatusDialog()
    
    translation_details = {
        0: [(0, "new1"), (1, "new2")]
    }
    previous_translations = {
        0: [(0, "old1"), (1, "old2")]
    }
    
    # Backup pytest module
    pytest_module = sys.modules.get('pytest')
    
    try:
        # 1. More than 1 line re-translated -> AITranslationComparisonDialog
        if 'pytest' in sys.modules:
            del sys.modules['pytest']
            
        with patch('dialogs.ai_translation_comparison_dialog.AITranslationComparisonDialog') as mock_comp_dialog, \
             patch('dialogs.ai_translation_result_dialog.AITranslationResultDialog') as mock_res_dialog:
            
            dialog.finish(success=True, show_popup=True, translation_details=translation_details, previous_translations=previous_translations)
            
            mock_comp_dialog.assert_called_once_with(dialog.parentWidget() or dialog, translation_details, previous_translations)
            mock_comp_dialog.return_value.show.assert_called_once()
            mock_res_dialog.assert_not_called()
            
        # 2. Only 1 line re-translated -> AITranslationComparisonDialog
        single_prev = {
            0: [(0, "old1")]
        }
        
        if 'pytest' in sys.modules:
            del sys.modules['pytest']
            
        with patch('dialogs.ai_translation_comparison_dialog.AITranslationComparisonDialog') as mock_comp_dialog, \
             patch('dialogs.ai_translation_result_dialog.AITranslationResultDialog') as mock_res_dialog:
            
            dialog.finish(success=True, show_popup=True, translation_details=translation_details, previous_translations=single_prev)
            
            mock_comp_dialog.assert_called_once_with(dialog.parentWidget() or dialog, translation_details, single_prev)
            mock_comp_dialog.return_value.show.assert_called_once()
            mock_res_dialog.assert_not_called()
    finally:
        if pytest_module:
            sys.modules['pytest'] = pytest_module


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


def test_AIStatusDialog_finish_without_popup_activates_source(qapp):
    from PyQt6.QtWidgets import QWidget
    from unittest.mock import MagicMock
    win = QWidget()
    win.show()
    win.activateWindow = MagicMock()
    win.raise_ = MagicMock()

    dialog = AIStatusDialog()
    dialog.start("Test Return", source_window=win)
    dialog.finish(show_popup=False)

    win.raise_.assert_called()
    win.activateWindow.assert_called()
    win.close()


def test_AIStatusDialog_finish_in_pytest_activates_source(qapp):
    from PyQt6.QtWidgets import QWidget
    from unittest.mock import MagicMock
    win = QWidget()
    win.show()
    win.activateWindow = MagicMock()
    win.raise_ = MagicMock()

    dialog = AIStatusDialog()
    dialog.start("Test Pytest Fallback", source_window=win)
    # When pytest is in sys.modules, popup is suppressed and source is directly activated
    dialog.finish(success=True, show_popup=True)

    win.raise_.assert_called()
    win.activateWindow.assert_called()
    win.close()


def test_AIStatusDialog_cancel_and_reject_activates_source(qapp):
    from PyQt6.QtWidgets import QWidget, QMessageBox
    from unittest.mock import MagicMock, patch
    win = QWidget()
    win.show()
    win.activateWindow = MagicMock()
    win.raise_ = MagicMock()

    dialog = AIStatusDialog()
    dialog.start("Test Cancel Return", source_window=win)
    with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
        dialog.on_cancel()
    dialog.finish(success=False, show_popup=False)

    win.raise_.assert_called()
    win.activateWindow.assert_called()
    win.close()


def test_AIStatusDialog_reject_when_not_running_activates_source(qapp):
    from PyQt6.QtWidgets import QWidget
    from unittest.mock import MagicMock
    win = QWidget()
    win.show()
    win.activateWindow = MagicMock()
    win.raise_ = MagicMock()

    dialog = AIStatusDialog()
    dialog.source_window = win
    dialog.reject()

    win.raise_.assert_called()
    win.activateWindow.assert_called()
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
    import sys
    from unittest.mock import patch, MagicMock
    from PyQt6.QtWidgets import QWidget, QMessageBox

    win = QWidget()
    win.show()
    win.activateWindow = MagicMock()
    win.raise_ = MagicMock()

    dialog = AIStatusDialog()
    dialog.start("Test Popup Dismissal", source_window=win)

    pytest_module = sys.modules.get('pytest')
    try:
        if 'pytest' in sys.modules:
            del sys.modules['pytest']

        with patch('PyQt6.QtWidgets.QMessageBox.show') as mock_msg_show:
            dialog.finish(success=True, show_popup=True)
            mock_msg_show.assert_called_once()

            # Source should not have been activated while popup is open
            assert win.activateWindow.call_count == 0

            # Simulate closing/destroying the QMessageBox
            msg_boxes = [w for w in qapp.topLevelWidgets() if isinstance(w, QMessageBox)]
            for mb in msg_boxes:
                mb.destroyed.emit(mb)

            assert win.activateWindow.call_count >= 1
            assert win.raise_.call_count >= 1
    finally:
        if pytest_module:
            sys.modules['pytest'] = pytest_module
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
