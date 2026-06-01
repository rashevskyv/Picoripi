import pytest
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


def test_AIStatusDialog_modeless_and_sleep_checkboxes(qapp):
    dialog = AIStatusDialog()
    assert dialog.isModal() is False
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
    with patch('PyQt5.QtCore.QTimer.singleShot') as mock_timer:
        dialog.finish()
        mock_timer.assert_called_once_with(5000, ANY)


def test_AIStatusDialog_cancel_prevents_sleep(qapp):
    dialog = AIStatusDialog()
    dialog.sleep_after_checkbox.setChecked(True)
    
    # Start operation
    dialog.start("Test")
    assert dialog.user_cancelled is False
    
    # Simulate user cancel
    dialog.on_cancel()
    assert dialog.user_cancelled is True
    
    # Finish operation and verify put_to_sleep was NOT scheduled
    with patch('PyQt5.QtCore.QTimer.singleShot') as mock_timer:
        dialog.finish()
        mock_timer.assert_not_called()


