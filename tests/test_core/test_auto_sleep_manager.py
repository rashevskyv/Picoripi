# tests/test_core/test_auto_sleep_manager.py ---
from unittest.mock import patch
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import QWidget
from core.auto_sleep_manager import AutoSleepManager, UserActivityEventFilter


def test_user_activity_event_filter_keypress(qapp):
    filter_obj = UserActivityEventFilter()
    assert filter_obj.activity_detected is False

    dummy_widget = QWidget()
    key_event = QKeyEvent(
        QEvent.Type.KeyPress, int(Qt.Key.Key_Space), Qt.KeyboardModifier.NoModifier
    )
    filter_obj.eventFilter(dummy_widget, key_event)
    assert filter_obj.activity_detected is True


def test_user_activity_event_filter_mouse_click(qapp):
    filter_obj = UserActivityEventFilter()
    dummy_widget = QWidget()
    mouse_event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    filter_obj.eventFilter(dummy_widget, mouse_event)
    assert filter_obj.activity_detected is True


def test_user_activity_event_filter_mouse_move_jitter(qapp):
    filter_obj = UserActivityEventFilter()
    dummy_widget = QWidget()

    # Tiny move (1px) -> should not trigger
    move1 = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(10.0, 10.0),
        QPointF(10.0, 10.0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    filter_obj.eventFilter(dummy_widget, move1)
    move2 = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(11.0, 11.0),
        QPointF(11.0, 11.0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    filter_obj.eventFilter(dummy_widget, move2)
    assert filter_obj.activity_detected is False

    # Significant move (25px) -> triggers activity
    move3 = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(35.0, 35.0),
        QPointF(35.0, 35.0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    filter_obj.eventFilter(dummy_widget, move3)
    assert filter_obj.activity_detected is True


def test_auto_sleep_manager_schedule_and_cancel(qapp):
    manager = AutoSleepManager()
    assert manager.is_active is False

    try:
        with (
            patch("core.auto_sleep_manager.restore_sleep") as mock_restore,
            patch("core.auto_sleep_manager.get_system_idle_seconds", return_value=0.0),
        ):
            manager.schedule_sleep(
                task_name="Test Task", delay_seconds=100, show_dialog=False
            )
            assert manager.is_active is True
            assert manager.remaining_seconds == 100
            assert manager.total_seconds == 100

            manager.cancel_sleep(reason="Manual test cancel")
            assert manager.is_active is False
            mock_restore.assert_called_once()
    finally:
        manager.cancel_sleep()


def test_auto_sleep_manager_immediate_sleep_when_already_idle(qapp):
    manager = AutoSleepManager()
    try:
        # User has already been idle for 600s (>= 300s threshold)
        with (
            patch(
                "core.auto_sleep_manager.get_system_idle_seconds", return_value=600.0
            ),
            patch("core.auto_sleep_manager.put_to_sleep") as mock_put,
        ):
            manager.schedule_sleep(
                task_name="Test Task", delay_seconds=300, show_dialog=False
            )
            assert manager.is_active is True
            assert manager.remaining_seconds == 2  # Short 2s grace

            # Tick 1
            manager._on_tick()
            assert manager.remaining_seconds == 1
            mock_put.assert_not_called()

            # Tick 2 -> Reaches 0 -> Triggers sleep immediately
            manager._on_tick()
            assert manager.is_active is False
            mock_put.assert_called_once()
    finally:
        manager.cancel_sleep()


def test_auto_sleep_manager_remaining_countdown_when_recently_active(qapp):
    manager = AutoSleepManager()
    try:
        # User was active 60s ago (threshold 300s) -> remaining 240s
        with patch(
            "core.auto_sleep_manager.get_system_idle_seconds", return_value=60.0
        ):
            manager.schedule_sleep(
                task_name="Test Task", delay_seconds=300, show_dialog=False
            )
            assert manager.is_active is True
            assert manager.remaining_seconds == 240
    finally:
        manager.cancel_sleep()


def test_auto_sleep_manager_tick_detects_app_activity(qapp):
    manager = AutoSleepManager()
    try:
        with patch("core.auto_sleep_manager.get_system_idle_seconds", return_value=0.0):
            manager.schedule_sleep(
                task_name="Test Task", delay_seconds=10, show_dialog=False
            )

        # Simulate activity in event filter
        manager._event_filter.activity_detected = True

        cancelled_reasons = []
        manager.sleep_cancelled.connect(cancelled_reasons.append)

        manager._on_tick()
        assert manager.is_active is False
        assert len(cancelled_reasons) == 1
        assert "Application" in cancelled_reasons[0]
    finally:
        manager.cancel_sleep()


def test_auto_sleep_manager_tick_detects_system_activity(qapp):
    manager = AutoSleepManager()
    try:
        with patch("core.auto_sleep_manager.get_system_idle_seconds", return_value=0.0):
            manager.schedule_sleep(
                task_name="Test Task", delay_seconds=300, show_dialog=False
            )
        manager.remaining_seconds = 295

        cancelled_reasons = []
        manager.sleep_cancelled.connect(cancelled_reasons.append)

        # If system idle drops to 0.5s -> user pressed key / moved mouse
        with patch("core.auto_sleep_manager.get_system_idle_seconds", return_value=0.5):
            manager._on_tick()

        assert manager.is_active is False
        assert len(cancelled_reasons) == 1
        assert "System" in cancelled_reasons[0]
    finally:
        manager.cancel_sleep()
