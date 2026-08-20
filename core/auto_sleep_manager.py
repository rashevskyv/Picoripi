# core/auto_sleep_manager.py ---
import sys
import time
from typing import Optional, Any, Callable
from PyQt6.QtCore import QObject, QTimer, QEvent, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from utils.logging_utils import log_info, log_error
from utils.power_utils import get_system_idle_seconds, restore_sleep, put_to_sleep


class UserActivityEventFilter(QObject):
    """Qt event filter to detect any user interaction inside the application."""

    def __init__(
        self,
        on_activity: Optional[Callable[[], None]] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.activity_detected = False
        self.on_activity = on_activity
        self._last_mouse_pos = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        event_type = event.type()
        if event_type in (
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.Wheel,
        ):
            self.activity_detected = True
            if self.on_activity:
                self.on_activity()
        elif event_type == QEvent.Type.MouseMove:
            pos = getattr(event, "globalPosition", None) or getattr(
                event, "globalPos", None
            )
            if pos:
                p = (pos().x(), pos().y()) if callable(pos) else (pos.x(), pos.y())
                if self._last_mouse_pos is not None:
                    dx = abs(p[0] - self._last_mouse_pos[0])
                    dy = abs(p[1] - self._last_mouse_pos[1])
                    if dx > 4 or dy > 4:
                        self.activity_detected = True
                        if self.on_activity:
                            self.on_activity()
                self._last_mouse_pos = p

        return False


class AutoSleepManager(QObject):
    """Coordinates idle-aware automatic computer sleep after task completion."""

    countdown_tick = pyqtSignal(int)
    sleep_cancelled = pyqtSignal(str)
    sleep_triggered = pyqtSignal()

    _instance: Optional["AutoSleepManager"] = None

    @classmethod
    def get_instance(cls) -> "AutoSleepManager":
        """Get or create singleton AutoSleepManager instance."""
        if cls._instance is None:
            cls._instance = AutoSleepManager()
        return cls._instance

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.is_active = False
        self.remaining_seconds = 0
        self.total_seconds = 0
        self.task_name = "Task"
        self._scheduled_time = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        self._event_filter: Optional[UserActivityEventFilter] = None
        self._countdown_dialog: Optional[Any] = None

    def schedule_sleep(
        self,
        task_name: str = "AI Operation",
        delay_seconds: int = 300,
        parent_widget: Optional[QWidget] = None,
        show_dialog: bool = True,
    ) -> bool:
        """Schedule or immediately trigger automatic system sleep after task completion.

        If the user has already been idle across the system for >= delay_seconds (e.g. 5+ minutes),
        sleep is triggered immediately (after a brief 2-second grace period for autosave and UI painting).

        If the user was active recently, a countdown runs for the remaining idle time.
        Any keyboard/mouse activity (or clicking Stay Awake / dialog buttons) immediately revokes sleep.
        """
        self.cancel_sleep(reason="Rescheduling")

        self.task_name = task_name
        threshold = max(1, delay_seconds)
        self.total_seconds = threshold

        # Check system-wide idle time immediately upon task finish
        sys_idle = get_system_idle_seconds()
        log_info(
            f"AutoSleepManager: Task '{task_name}' finished. Checking user idle state: "
            f"system idle = {sys_idle:.1f}s, threshold = {threshold}s."
        )

        app = QApplication.instance()
        if app:
            self._event_filter = UserActivityEventFilter(
                on_activity=lambda: self.cancel_sleep(
                    "Application interaction detected"
                ),
                parent=self,
            )
            app.installEventFilter(self._event_filter)

        self.is_active = True
        self._scheduled_time = time.time()

        if sys_idle >= threshold:
            # User is ALREADY away (has been idle for 5+ minutes).
            # Put computer to sleep immediately with a short 2s grace for UI painting / autosave.
            log_info(
                f"AutoSleepManager: User has already been idle for {sys_idle:.1f}s (>= {threshold}s threshold). "
                "Triggering immediate sleep..."
            )
            self.remaining_seconds = 2
            self._timer.setInterval(1000)
            self._timer.start()
            return True

        # User was active recently: wait for the remaining time until threshold of continuous idle
        remaining = max(1, int(threshold - sys_idle))
        self.remaining_seconds = remaining
        log_info(
            f"AutoSleepManager: User was active {sys_idle:.1f}s ago. "
            f"Scheduling sleep in {remaining}s if user remains idle."
        )

        # Show countdown UI if remaining time is significant (> 5s)
        if show_dialog and remaining > 5 and "pytest" not in sys.modules:
            try:
                from components.auto_sleep_countdown_dialog import (
                    AutoSleepCountdownDialog,
                )

                self._countdown_dialog = AutoSleepCountdownDialog(
                    parent=parent_widget,
                    task_name=task_name,
                    total_seconds=remaining,
                    manager=self,
                )
                self._countdown_dialog.show()
            except Exception as e:
                log_error(f"Failed to create auto sleep countdown dialog: {e}")

        self._timer.setInterval(1000)
        self._timer.start()
        return True

    def cancel_sleep(self, reason: str = "User activity detected"):
        """Cancel scheduled sleep and restore normal power state."""
        if not self.is_active and not self._timer.isActive():
            return

        self.is_active = False
        self._timer.stop()

        # Remove event filter
        app = QApplication.instance()
        if app and self._event_filter:
            app.removeEventFilter(self._event_filter)
            self._event_filter = None

        # Close countdown dialog
        if self._countdown_dialog:
            try:
                self._countdown_dialog._is_closing = True
                self._countdown_dialog.close()
                self._countdown_dialog.deleteLater()
            except Exception:
                pass
            self._countdown_dialog = None

        restore_sleep()
        log_info(f"AutoSleepManager: Cancelled scheduled sleep ({reason}).")
        self.sleep_cancelled.emit(reason)

    def _on_tick(self):
        """Timer tick handler: check user idle status and update countdown."""
        if not self.is_active:
            return

        # 1. Check in-app activity
        if self._event_filter and self._event_filter.activity_detected:
            self.cancel_sleep("Application user interaction detected")
            return

        # 2. Check system-wide idle time (Windows / OS)
        sys_idle = get_system_idle_seconds()

        # If user touched mouse/keyboard in the system, sys_idle drops to < 1s
        if sys_idle < 1.0:
            self.cancel_sleep("System user activity detected")
            return

        # 3. Decrement countdown
        self.remaining_seconds -= 1

        if self._countdown_dialog:
            try:
                self._countdown_dialog.update_countdown(self.remaining_seconds)
            except Exception:
                pass

        self.countdown_tick.emit(self.remaining_seconds)

        # 4. Trigger sleep if countdown reached zero with complete idle
        if self.remaining_seconds <= 0:
            self._trigger_sleep()

    def _trigger_sleep(self):
        """Perform pre-sleep autosave and suspend system."""
        self.is_active = False
        self._timer.stop()

        app = QApplication.instance()
        if app and self._event_filter:
            app.removeEventFilter(self._event_filter)
            self._event_filter = None

        if self._countdown_dialog:
            try:
                self._countdown_dialog._is_closing = True
                self._countdown_dialog.close()
                self._countdown_dialog.deleteLater()
            except Exception:
                pass
            self._countdown_dialog = None

        # Flush autosave before sleep
        self._autosave_all_sessions()

        log_info(
            "AutoSleepManager: User was idle for the full threshold duration. Putting system to sleep."
        )
        self.sleep_triggered.emit()
        put_to_sleep()

    def _autosave_all_sessions(self):
        """Autosave active project sessions to prevent data loss upon system sleep."""
        try:
            app = QApplication.instance()
            if app:
                for widget in app.topLevelWidgets():
                    if isinstance(widget, QMainWindow) and hasattr(
                        widget, "data_processor"
                    ):
                        dp = widget.data_processor
                        if hasattr(dp, "_autosave_session"):
                            dp._autosave_session(force=True)
                            log_info(
                                "AutoSleepManager: Session autosaved before system sleep."
                            )
                            break
        except Exception as e:
            log_error(f"AutoSleepManager: Failed to autosave session before sleep: {e}")
