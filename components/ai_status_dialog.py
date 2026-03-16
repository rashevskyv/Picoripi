# --- START OF FILE components/ai_status_dialog.py ---
# components/ai_status_dialog.py ---
import os
from typing import Optional
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QProgressBar, QDialogButtonBox
from PyQt5.QtGui import QMovie, QFont, QPalette
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QEvent

class AIStatusDialog(QDialog):
    cancelled = pyqtSignal()
    STATUS_PENDING = 0
    STATUS_IN_PROGRESS = 1
    STATUS_DONE = 2
    STATUS_ERROR = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Operation")
        self.setModal(True)
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

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat('%p%')
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.button_box = QDialogButtonBox(self)
        self.cancel_button = self.button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        main_layout.addWidget(self.button_box)

        self.button_box.rejected.connect(self.on_cancel)

    def on_cancel(self):
        self.cancelled.emit()
        self.reject()

    def closeEvent(self, event: QEvent):
        self.cancelled.emit()
        super().closeEvent(event)

    def setup_progress_bar(self, total_chunks: int, completed_chunks: int = 0):
        self.progress_bar.setRange(0, total_chunks)
        self.progress_bar.setValue(completed_chunks)
        self.progress_bar.setFormat('%p%')
        self.progress_bar.setVisible(True)

    def update_progress(self, completed_chunks: int):
        self.progress_bar.setValue(completed_chunks)

    def showEvent(self, event):
        super().showEvent(event)
        self.movie.start()

    def hideEvent(self, event):
        self.movie.stop()
        super().hideEvent(event)

    def start(self, title: str, is_chunked: bool = False, model_name: Optional[str] = None):
        self.title_label.setText(title)
        self._set_model_name(model_name)
        for i, label in enumerate(self.step_labels):
            self._update_label_style(label, self.STATUS_PENDING, self.steps[i])

        if is_chunked:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat('%p%')
            self.progress_bar.setVisible(False)
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Processing...")
            self.progress_bar.setVisible(True)

        self.open()

    def finish(self):
        self._set_model_name(None)
        self.hide()

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

