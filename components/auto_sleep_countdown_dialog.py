# components/auto_sleep_countdown_dialog.py ---
from typing import Optional, Any
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class AutoSleepCountdownDialog(QDialog):
    """Non-modal countdown notification dialog shown before entering sleep mode."""

    def __init__(self, parent=None, task_name: str = "Operation", total_seconds: int = 300, manager: Optional[Any] = None):
        super().__init__(parent)
        self.manager = manager
        self.total_seconds = max(1, total_seconds)
        self.task_name = task_name
        self._is_closing = False

        self.setWindowTitle("System Sleep Countdown")
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.title_label = QLabel(f"<b>{task_name} Finished</b>", self)
        font = self.title_label.font()
        font.setPointSize(11)
        self.title_label.setFont(font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.time_label = QLabel(self._format_time(self.total_seconds), self)
        time_font = QFont(font)
        time_font.setPointSize(22)
        time_font.setBold(True)
        self.time_label.setFont(time_font)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("color: #1a73e8;")
        layout.addWidget(self.time_label)

        self.info_label = QLabel(
            "The computer will sleep if no user activity is detected.\n"
            "Press any key, move the mouse, or click 'Stay Awake' to cancel.",
            self
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, self.total_seconds)
        self.progress_bar.setValue(self.total_seconds)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_button = QPushButton("Stay Awake", self)
        self.cancel_button.setDefault(True)
        self.cancel_button.clicked.connect(self._on_stay_awake_clicked)
        btn_layout.addWidget(self.cancel_button)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _format_time(self, seconds: int) -> str:
        mins = max(0, seconds) // 60
        secs = max(0, seconds) % 60
        return f"{mins:02d}:{secs:02d}"

    def update_countdown(self, remaining_seconds: int):
        """Update the countdown label and progress bar."""
        self.time_label.setText(self._format_time(remaining_seconds))
        self.progress_bar.setValue(max(0, remaining_seconds))

    def _on_stay_awake_clicked(self):
        if self.manager and not self._is_closing:
            self._is_closing = True
            self.manager.cancel_sleep("Stay Awake clicked")
        self.close()

    def reject(self):
        if self.manager and not self._is_closing:
            self._is_closing = True
            self.manager.cancel_sleep("Dialog dismissed")
        super().reject()

    def closeEvent(self, event):
        if self.manager and not self._is_closing:
            self._is_closing = True
            self.manager.cancel_sleep("Dialog closed")
        super().closeEvent(event)
