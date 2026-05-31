# components/ai_status_dialog.py ---
import os
import ctypes
from typing import Optional
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QProgressBar, QDialogButtonBox, QCheckBox
from PyQt5.QtGui import QMovie, QFont, QPalette
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QEvent
from utils.logging_utils import log_info, log_error

def prevent_sleep():
    if os.name == 'nt':
        try:
            # ES_CONTINUOUS = 0x80000000, ES_SYSTEM_REQUIRED = 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
            log_info("System sleep prevention activated for AI operation.")
        except Exception as e:
            log_error(f"Failed to set sleep prevention: {e}")

def restore_sleep():
    if os.name == 'nt':
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            log_info("System sleep prevention deactivated.")
        except Exception as e:
            log_error(f"Failed to restore sleep state: {e}")

def put_to_sleep():
    if os.name == 'nt':
        try:
            # SetSuspendState(False, True, False) -> sleep
            ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
            log_info("System suspended successfully after AI operation.")
        except Exception as e:
            log_error(f"Failed to suspend system: {e}")
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

class AIStatusDialog(QDialog):
    cancelled = pyqtSignal()
    STATUS_PENDING = 0
    STATUS_IN_PROGRESS = 1
    STATUS_DONE = 2
    STATUS_ERROR = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Operation")
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(450)
        self.setSizeGripEnabled(False)

        self.steps = [
            "Preparing request...",
            "Sending to AI...",
            "Waiting for response...",
            "Validating result...",
            "Applying changes..."
        ]
        self.step_labels: list[QLabel] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        self.title_label = QLabel("AI Translation", self)
        font = self.title_label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("", self)
        subtitle_font = QFont(self.title_label.font())
        subtitle_font.setPointSize(max(subtitle_font.pointSize() - 2, 8))
        subtitle_font.setItalic(True)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setVisible(False)
        main_layout.addWidget(self.subtitle_label)
        main_layout.addSpacing(10)

        steps_widget = QWidget(self)
        steps_layout = QVBoxLayout(steps_widget)
        steps_layout.setContentsMargins(20, 10, 20, 10)
        steps_layout.setSpacing(8)

        for step_text in self.steps:
            label = QLabel(f"○ {step_text}", self)
            self.step_labels.append(label)
            steps_layout.addWidget(label)
        
        main_layout.addWidget(steps_widget)
        main_layout.addStretch(1)

        animation_layout = QHBoxLayout()
        animation_layout.addStretch(1)
        self.animation_label = QLabel(self)
        self.movie = QMovie("resources/icons/loading.gif")
        self.movie.setScaledSize(QSize(48, 48))
        self.animation_label.setMovie(self.movie)
        animation_layout.addWidget(self.animation_label)
        animation_layout.addStretch(1)
        
        main_layout.addLayout(animation_layout)
        main_layout.addStretch(1)

        self.detail_label = QLabel("", self)
        detail_font = QFont(self.title_label.font())
        detail_font.setPointSize(max(detail_font.pointSize() - 3, 8))
        detail_font.setItalic(True)
        self.detail_label.setFont(detail_font)
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setWordWrap(True)
        self.detail_label.setVisible(False)
        main_layout.addWidget(self.detail_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat('%p% (%v/%m chunks)')
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Sleep options
        sleep_layout = QHBoxLayout()
        self.prevent_sleep_checkbox = QCheckBox("Prevent computer sleep", self)
        self.prevent_sleep_checkbox.setToolTip("Keep the computer awake while AI operation is running.")
        self.prevent_sleep_checkbox.setChecked(True)
        self.prevent_sleep_checkbox.toggled.connect(self._handle_prevent_sleep_toggled)
        
        self.sleep_after_checkbox = QCheckBox("Put computer to sleep when finished", self)
        self.sleep_after_checkbox.setToolTip("Suspend/Sleep the computer automatically after the AI task completes.")
        self.sleep_after_checkbox.setChecked(False)
        self.sleep_after_checkbox.toggled.connect(self._handle_sleep_after_toggled)
        
        sleep_layout.addWidget(self.prevent_sleep_checkbox)
        sleep_layout.addWidget(self.sleep_after_checkbox)
        sleep_layout.addStretch()
        main_layout.addLayout(sleep_layout)

        self.button_box = QDialogButtonBox(self)
        self.cancel_button = self.button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        main_layout.addWidget(self.button_box)

        self.button_box.rejected.connect(self.on_cancel)

    def on_cancel(self):
        self.cancelled.emit()
        self.reject()
        restore_sleep()

    def closeEvent(self, event: QEvent):
        self.cancelled.emit()
        super().closeEvent(event)
        restore_sleep()

    def setup_progress_bar(self, total_chunks: int, completed_chunks: int = 0):
        self.progress_bar.setRange(0, total_chunks)
        self.progress_bar.setValue(completed_chunks)
        self.progress_bar.setFormat('%p% (%v/%m chunks)')
        self.progress_bar.setVisible(True)

    def update_progress(self, completed_chunks: int):
        self.progress_bar.setValue(completed_chunks)

    def set_detail_text(self, text: str):
        self.detail_label.setText(text)
        self.detail_label.setVisible(bool(text))

    def showEvent(self, event):
        super().showEvent(event)
        self.movie.start()

    def hideEvent(self, event):
        self.movie.stop()
        super().hideEvent(event)

    def start(self, title: str, is_chunked: bool = False, model_name: Optional[str] = None):
        self.title_label.setText(title)
        self._set_model_name(model_name)
        self.detail_label.clear()
        self.detail_label.setVisible(False)
        for i, label in enumerate(self.step_labels):
            self._update_label_style(label, self.STATUS_PENDING, self.steps[i])

        if is_chunked:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat('%p% (%v/%m chunks)')
            self.progress_bar.setVisible(False)
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Processing...")
            self.progress_bar.setVisible(True)

        if self.prevent_sleep_checkbox.isChecked():
            prevent_sleep()

        self.show()

    def finish(self):
        self._set_model_name(None)
        self.detail_label.clear()
        self.detail_label.setVisible(False)
        self.hide()
        
        restore_sleep()
        if self.sleep_after_checkbox.isChecked():
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(5000, put_to_sleep)

    def _handle_prevent_sleep_toggled(self, checked: bool):
        if self.isVisible():
            if checked:
                prevent_sleep()
            else:
                restore_sleep()

    def _handle_sleep_after_toggled(self, checked: bool):
        pass

    def _set_model_name(self, model_name: Optional[str]) -> None:
        text = (model_name or '').strip()
        if text:
            if not text.lower().startswith('model:'):
                text = f"Model: {text}"
            self.subtitle_label.setText(text)
            self.subtitle_label.setVisible(True)
        else:
            self.subtitle_label.clear()
            self.subtitle_label.setVisible(False)

    def update_step(self, step_index: int, text: str, status: int):
        if 0 <= step_index < len(self.step_labels):
            for i in range(len(self.step_labels)):
                current_status = self.STATUS_PENDING
                current_text = self.steps[i]
                if i < step_index:
                    current_status = self.STATUS_DONE
                elif i == step_index:
                    current_status = status
                    current_text = text
                
                self._update_label_style(self.step_labels[i], current_status, current_text)

    def _update_label_style(self, label: QLabel, status: int, text: str):
        font = label.font()
        palette = label.palette()
        
        if status == self.STATUS_PENDING:
            font.setBold(False)
            palette.setColor(QPalette.WindowText, Qt.gray)
            prefix = "○"
        elif status == self.STATUS_IN_PROGRESS:
            font.setBold(True)
            palette.setColor(QPalette.WindowText, self.palette().color(QPalette.WindowText))
            prefix = "▶"
        elif status == self.STATUS_DONE:
            font.setBold(False)
            palette.setColor(QPalette.WindowText, Qt.gray)
            prefix = "✔"
        elif status == self.STATUS_ERROR:
            font.setBold(True)
            palette.setColor(QPalette.WindowText, Qt.red)
            prefix = "✖"
        else:
            prefix = "○"
            
        label.setFont(font)
        label.setPalette(palette)
        label.setText(f"{prefix} {text}")

