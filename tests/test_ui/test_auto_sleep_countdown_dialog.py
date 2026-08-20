# tests/test_ui/test_auto_sleep_countdown_dialog.py ---
from unittest.mock import MagicMock
from components.auto_sleep_countdown_dialog import AutoSleepCountdownDialog

def test_auto_sleep_countdown_dialog_init(qapp):
    dialog = AutoSleepCountdownDialog(task_name="AI Batch Translation", total_seconds=300)
    assert "AI Batch Translation Finished" in dialog.title_label.text()
    assert dialog.time_label.text() == "05:00"
    assert dialog.progress_bar.maximum() == 300
    assert dialog.progress_bar.value() == 300


def test_auto_sleep_countdown_dialog_update_countdown(qapp):
    dialog = AutoSleepCountdownDialog(task_name="Pipeline", total_seconds=120)
    dialog.update_countdown(75)
    assert dialog.time_label.text() == "01:15"
    assert dialog.progress_bar.value() == 75


def test_auto_sleep_countdown_dialog_stay_awake_click(qapp):
    mock_manager = MagicMock()
    dialog = AutoSleepCountdownDialog(task_name="Pipeline", total_seconds=60, manager=mock_manager)
    dialog.cancel_button.click()
    mock_manager.cancel_sleep.assert_called_once_with("Stay Awake clicked")
