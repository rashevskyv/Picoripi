# components/ai_status_dialog.py ---
from typing import Optional
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QProgressBar, QDialogButtonBox, QCheckBox
from PyQt6.QtGui import QMovie, QFont, QPalette
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QEvent
from utils.power_utils import prevent_sleep, restore_sleep, put_to_sleep
from core.auto_sleep_manager import AutoSleepManager

__all__ = ["AIStatusDialog", "prevent_sleep", "restore_sleep", "put_to_sleep"]

class AIStatusDialog(QDialog):
    """Dialog class for AI operation status."""
    cancelled = pyqtSignal()
    STATUS_PENDING = 0
    STATUS_IN_PROGRESS = 1
    STATUS_DONE = 2
    STATUS_ERROR = 3

    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.setWindowTitle("AI Operation")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setMinimumWidth(450)
        self.setSizeGripEnabled(False)
        self.user_cancelled = False
        self.is_running = False
        self.operation_title = "AI Operation"

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
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("", self)
        subtitle_font = QFont(self.title_label.font())
        subtitle_font.setPointSize(max(subtitle_font.pointSize() - 2, 8))
        subtitle_font.setItalic(True)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.sleep_after_checkbox.setToolTip("Suspend/Sleep the computer automatically after the AI task completes if idle.")
        self.sleep_after_checkbox.setChecked(False)
        self.sleep_after_checkbox.toggled.connect(self._handle_sleep_after_toggled)
        
        sleep_layout.addWidget(self.prevent_sleep_checkbox)
        sleep_layout.addWidget(self.sleep_after_checkbox)
        sleep_layout.addStretch()
        main_layout.addLayout(sleep_layout)

        self.button_box = QDialogButtonBox(self)
        self.cancel_button = self.button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        main_layout.addWidget(self.button_box)

        self.button_box.rejected.connect(self.on_cancel)

    def on_cancel(self):
        """Handle the cancel event."""
        self.reject()

    def reject(self):
        """Reject."""
        AutoSleepManager.get_instance().cancel_sleep("AI dialog rejected/cancelled")
        if getattr(self, 'is_running', False):
            self.user_cancelled = True
            self.cancelled.emit()
            self.title_label.setText("Cancelling AI Operation...")
            self.detail_label.setText("Please wait for the current request to abort cleanly...")
            self.detail_label.setVisible(True)
            self.cancel_button.setEnabled(False)
        else:
            super().reject()
            restore_sleep()

    def closeEvent(self, event: QEvent):
        """Closeevent."""
        AutoSleepManager.get_instance().cancel_sleep("AI dialog closed")
        if getattr(self, 'is_running', False):
            event.ignore()
            self.reject()
        else:
            super().closeEvent(event)
            restore_sleep()

    def setup_progress_bar(self, total_chunks: int, completed_chunks: int = 0):
        """Setup progress bar."""
        self.progress_bar.setRange(0, total_chunks)
        self.progress_bar.setValue(completed_chunks)
        self.progress_bar.setFormat('%p% (%v/%m chunks)')
        self.progress_bar.setVisible(True)

    def update_progress(self, completed_chunks: int):
        """Update the progress."""
        self.progress_bar.setValue(completed_chunks)

    def set_detail_text(self, text: str):
        """Set the detail text."""
        self.detail_label.setText(text)
        self.detail_label.setVisible(bool(text))

    def showEvent(self, event):
        """Showevent."""
        super().showEvent(event)
        self.movie.start()

    def hideEvent(self, event):
        """Hideevent."""
        self.movie.stop()
        super().hideEvent(event)

    def start(self, title: str, is_chunked: bool = False, model_name: Optional[str] = None):
        """Start."""
        self.user_cancelled = False
        self.is_running = True
        self.operation_title = title
        self.setWindowTitle(title)
        self.cancel_button.setEnabled(True)
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

    def finish(self, success: bool = True, show_popup: bool = True, translation_details: Optional[dict] = None, previous_translations: Optional[dict] = None):
        """Finish."""
        self.is_running = False
        self.cancel_button.setEnabled(True)
        self._set_model_name(None)
        self.detail_label.clear()
        self.detail_label.setVisible(False)
        self.hide()
        
        restore_sleep()
        
        # 1. Schedule sleep evaluation FIRST before showing dialogs/popups
        if self.sleep_after_checkbox.isChecked() and not getattr(self, 'user_cancelled', False) and success:
            delay = 300
            p = self.parentWidget()
            while p:
                sm = getattr(p, 'settings_manager', None)
                if sm:
                    val = sm.get("auto_sleep_idle_delay_seconds", 300)
                    if isinstance(val, int) and val > 0:
                        delay = val
                    break
                p = getattr(p, 'parentWidget', lambda: None)()
            AutoSleepManager.get_instance().schedule_sleep(
                task_name=self.operation_title,
                delay_seconds=delay,
                parent_widget=self.parentWidget() or self
            )
        else:
            AutoSleepManager.get_instance().cancel_sleep(reason="AI operation finished without sleep condition")

        # 2. Show structured popup notification to the user (suppressed during unit tests)
        import sys
        if 'pytest' not in sys.modules and show_popup:
            from PyQt6.QtWidgets import QMessageBox, QMainWindow, QApplication
            if getattr(self, 'user_cancelled', False):
                msg_box = QMessageBox(QMessageBox.Icon.Information, self.operation_title, f"{self.operation_title} was cancelled.", parent=self.parentWidget() or self)
                msg_box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                msg_box.show()
            elif success:
                total_retranslated = 0
                if previous_translations:
                    for b_idx, items in previous_translations.items():
                        total_retranslated += len(items)
                
                # Find MainWindow to store active dialog references
                mw = None
                p = self.parentWidget()
                while p:
                    if isinstance(p, QMainWindow):
                        mw = p
                        break
                    p = p.parentWidget() if hasattr(p, 'parentWidget') else None
                if not mw:
                    for widget in QApplication.topLevelWidgets():
                        if isinstance(widget, QMainWindow):
                            mw = widget
                            break

                if previous_translations and total_retranslated >= 1 and translation_details:
                    # Close previous comparison dialog if it is open
                    if mw and getattr(mw, 'active_comparison_dialog', None) is not None:
                        try:
                            mw.active_comparison_dialog.close()
                        except Exception:
                            pass
                    
                    from dialogs.ai_translation_comparison_dialog import AITranslationComparisonDialog
                    dialog = AITranslationComparisonDialog(self.parentWidget() or self, translation_details, previous_translations)
                    if mw:
                        mw.active_comparison_dialog = dialog
                    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                    if mw:
                        dialog.destroyed.connect(lambda: setattr(mw, 'active_comparison_dialog', None) if mw else None)
                    dialog.show()
                elif translation_details:
                    # Close previous result dialog if it is open
                    if mw and getattr(mw, 'active_result_dialog', None) is not None:
                        try:
                            mw.active_result_dialog.close()
                        except Exception:
                            pass

                    from dialogs.ai_translation_result_dialog import AITranslationResultDialog
                    dialog = AITranslationResultDialog(self.parentWidget() or self, translation_details)
                    if mw:
                        mw.active_result_dialog = dialog
                    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                    if mw:
                        dialog.destroyed.connect(lambda: setattr(mw, 'active_result_dialog', None) if mw else None)
                    dialog.show()
                else:
                    msg_box = QMessageBox(QMessageBox.Icon.Information, self.operation_title, f"{self.operation_title} finished.", parent=self.parentWidget() or self)
                    msg_box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                    msg_box.show()

    def _handle_prevent_sleep_toggled(self, checked: bool):
        """Internal helper to handle prevent sleep toggled."""
        if self.isVisible():
            if checked:
                prevent_sleep()
            else:
                restore_sleep()

    def _handle_sleep_after_toggled(self, checked: bool):
        """Internal helper to handle sleep after toggled."""
        pass

    def _set_model_name(self, model_name: Optional[str]) -> None:
        """Internal helper to set the model name."""
        text = (model_name or '').strip()
        if text:
            if not text.lower().startswith('model:'):
                text = f"Model: {text}"
            self.subtitle_label.setText(text)
            self.subtitle_label.setVisible(True)
        else:
            self.subtitle_label.clear()
            self.subtitle_label.setVisible(False)

    def set_model_name(self, model_name: Optional[str]) -> None:
        """Set or clear the visible model name."""
        self._set_model_name(model_name)

    def update_step(self, step_index: int, text: str, status: int):
        """Update the step."""
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
        """Internal helper to update the label style."""
        font = label.font()
        palette = label.palette()
        
        if status == self.STATUS_PENDING:
            font.setBold(False)
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.gray)
            prefix = "○"
        elif status == self.STATUS_IN_PROGRESS:
            font.setBold(True)
            palette.setColor(QPalette.ColorRole.WindowText, self.palette().color(QPalette.ColorRole.WindowText))
            prefix = "▶"
        elif status == self.STATUS_DONE:
            font.setBold(False)
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.gray)
            prefix = "✔"
        elif status == self.STATUS_ERROR:
            font.setBold(True)
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.red)
            prefix = "✖"
        else:
            prefix = "○"
            
        label.setFont(font)
        label.setPalette(palette)
        label.setText(f"{prefix} {text}")
