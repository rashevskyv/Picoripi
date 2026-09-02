"""Dialog shown when the glossary build pipeline is stopped by AI failure.

Displays the current progress, saved status on disk, and provides a countdown
timer that automatically retries resuming after a progressive delay (5m -> 10m).
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStyle,
    QTextEdit,
    QVBoxLayout,
)
from utils import power_utils
from core.i18n import tr


ACTION_RESUME = "resume"
ACTION_REVIEW = "review"
ACTION_CLOSE = "close"


def remaining_work(
    *,
    total_entries: int = 0,
    described_count: int = 0,
    undescribed_count: int = 0,
    untranslated_count: int = 0,
    translate: bool = True,
) -> tuple[int, int, int, int]:
    """Return (done, total, left, translated) until the glossary job is finished.

    Each term needs a description, then a translation. Undescribed terms still
    have both steps ahead; described-but-untranslated terms have one.
    """
    total_entries = max(0, int(total_entries))
    described_count = max(0, int(described_count))
    undescribed_count = max(0, int(undescribed_count))
    untranslated_count = max(0, int(untranslated_count))
    if total_entries <= 0:
        total_entries = described_count + undescribed_count
    translated = max(0, described_count - untranslated_count)
    if translate:
        total_steps = total_entries * 2
        done_steps = described_count + translated
    else:
        total_steps = total_entries
        done_steps = described_count
    done_steps = min(done_steps, total_steps)
    left = max(0, total_steps - done_steps)
    return done_steps, total_steps, left, translated


class GlossaryStoppedDialog(QDialog):
    """Informative dialog for paused glossary build with auto-retry countdown."""

    ACTION_RESUME = ACTION_RESUME
    ACTION_REVIEW = ACTION_REVIEW
    ACTION_CLOSE = ACTION_CLOSE

    def __init__(
        self,
        parent=None,
        *,
        stage_name: str = "",
        summary: str = "",
        total_entries: int = 0,
        described_count: int = 0,
        undescribed_count: int = 0,
        untranslated_count: int = 0,
        completed_units: int = 0,
        total_units: int = 0,
        last_error: str = "",
        auto_retry_delay: int = 300,
        can_resume: bool = True,
        prevent_sleep: bool = True,
        sleep_after: bool = False,
        translate: bool = True,
    ):
        super().__init__(parent)
        self.action = self.ACTION_CLOSE
        self.can_resume = can_resume
        self.auto_retry_delay = max(0, auto_retry_delay)
        self._remaining_seconds = self.auto_retry_delay
        self._timer: Optional[QTimer] = None

        stage_title = f" ({stage_name.capitalize()} pass)" if stage_name else ""
        self.setWindowTitle(f"Glossary Build Paused{stage_title}")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header with icon
        header_layout = QHBoxLayout()
        icon_label = QLabel(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        icon_label.setPixmap(icon.pixmap(32, 32))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        header_layout.addWidget(icon_label)

        header_text = QLabel(
            tr('<b>AI backend stopped responding during the glossary build.</b><br>All entries processed before this point are safely saved to disk.'),
            self,
        )
        header_text.setWordWrap(True)
        header_layout.addWidget(header_text, 1)
        layout.addLayout(header_layout)

        done_steps, total_steps, left, translated = remaining_work(
            total_entries=total_entries,
            described_count=described_count,
            undescribed_count=undescribed_count,
            untranslated_count=untranslated_count,
            translate=translate,
        )
        self.done_steps = done_steps
        self.total_steps = total_steps
        self.left_steps = left

        left_row = QHBoxLayout()
        self.remaining_label = QLabel(f"{left:,} left", self)
        self.remaining_label.setStyleSheet("font-size: 22px; font-weight: 700;")
        self.counts_label = QLabel(
            f"{done_steps:,} / {total_steps:,} done" if total_steps else "nothing queued",
            self,
        )
        self.counts_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.counts_label.setStyleSheet("font-size: 13px;")
        left_row.addWidget(self.remaining_label)
        left_row.addWidget(self.counts_label, 1)
        layout.addLayout(left_row)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, max(1, total_steps))
        self.progress_bar.setValue(done_steps if total_steps else 0)
        self.progress_bar.setTextVisible(True)
        pct = int(round(100 * done_steps / total_steps)) if total_steps else 0
        self.progress_bar.setFormat(f"{pct}%")
        self.progress_bar.setMinimumHeight(22)
        layout.addWidget(self.progress_bar)

        describe_total = total_entries or (described_count + undescribed_count)
        translate_total = describe_total if translate else 0
        breakdown = [
            f"Describe  {described_count:,} / {describe_total:,}",
        ]
        if translate:
            breakdown.append(f"Translate  {translated:,} / {translate_total:,}")
        if total_units > 0:
            breakdown.append(f"This pass  {completed_units:,} / {total_units:,}")
        self.breakdown_label = QLabel("   ·   ".join(breakdown), self)
        self.breakdown_label.setStyleSheet("color: palette(mid); font-size: 12px;")
        layout.addWidget(self.breakdown_label)

        if total_units > 0:
            self.pass_bar = QProgressBar(self)
            self.pass_bar.setRange(0, max(1, total_units))
            self.pass_bar.setValue(min(completed_units, total_units))
            self.pass_bar.setFormat("this pass %v / %m")
            self.pass_bar.setMinimumHeight(16)
            layout.addWidget(self.pass_bar)
        else:
            self.pass_bar = None

        # Error details box
        err_msg = str(last_error or summary).strip()
        if err_msg:
            details_label = QLabel(tr('<b>Details:</b>'), self)
            layout.addWidget(details_label)

            self.details_edit = QTextEdit(self)
            self.details_edit.setPlainText(err_msg)
            self.details_edit.setReadOnly(True)
            self.details_edit.setMaximumHeight(80)
            self.details_edit.setStyleSheet("font-size: 11px;")
            layout.addWidget(self.details_edit)

        # Sleep options
        sleep_layout = QHBoxLayout()
        self.prevent_sleep_checkbox = QCheckBox(tr('Prevent computer sleep'), self)
        self.prevent_sleep_checkbox.setToolTip(tr('Keep the computer awake while waiting and running.'))
        self.prevent_sleep_checkbox.setChecked(prevent_sleep)
        self.prevent_sleep_checkbox.toggled.connect(self._handle_prevent_sleep_toggled)

        self.sleep_after_checkbox = QCheckBox(tr('Put computer to sleep when finished'), self)
        self.sleep_after_checkbox.setToolTip(tr('Suspend/Sleep the computer automatically after the task completes if idle.'))
        self.sleep_after_checkbox.setChecked(sleep_after)

        sleep_layout.addWidget(self.prevent_sleep_checkbox)
        sleep_layout.addWidget(self.sleep_after_checkbox)
        sleep_layout.addStretch()
        layout.addLayout(sleep_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()

        self.resume_btn: Optional[QPushButton] = None
        if self.can_resume:
            self.resume_btn = QPushButton(self)
            self.resume_btn.setStyleSheet("font-weight: bold; padding: 6px 16px; min-height: 24px;")
            self.resume_btn.clicked.connect(self._on_resume_clicked)
            btn_layout.addWidget(self.resume_btn)

        self.review_btn = QPushButton(tr('Review Glossary'), self)
        self.review_btn.setStyleSheet("padding: 6px 14px; min-height: 24px;")
        self.review_btn.clicked.connect(self._on_review_clicked)
        btn_layout.addWidget(self.review_btn)

        self.close_btn = QPushButton(tr('Close'), self)
        self.close_btn.setStyleSheet("padding: 6px 14px; min-height: 24px;")
        self.close_btn.clicked.connect(self._on_close_clicked)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

        # Ensure sleep prevention is activated if checked
        if self.prevent_sleep_checkbox.isChecked():
            power_utils.prevent_sleep()

        # Setup countdown timer
        if self.can_resume and self.resume_btn is not None:
            if self.auto_retry_delay > 0:
                self._timer = QTimer(self)
                self._timer.setInterval(1000)
                self._timer.timeout.connect(self._on_tick)
                self._timer.start()
            self._update_resume_button_text()

    def _handle_prevent_sleep_toggled(self, checked: bool) -> None:
        if checked:
            power_utils.prevent_sleep()
        else:
            power_utils.restore_sleep()

    def _format_time(self, seconds: int) -> str:
        mins = max(0, seconds) // 60
        secs = max(0, seconds) % 60
        return f"{mins:02d}:{secs:02d}"

    def _update_resume_button_text(self) -> None:
        if self.resume_btn is None:
            return
        if self._remaining_seconds > 0 and self._timer is not None and self._timer.isActive():
            time_str = self._format_time(self._remaining_seconds)
            self.resume_btn.setText(f"Resume Unfinished Pass (Auto-retry in {time_str})")
        else:
            self.resume_btn.setText(tr('Resume Unfinished Pass'))

    def _on_tick(self) -> None:
        self._remaining_seconds -= 1
        self._update_resume_button_text()
        if self._remaining_seconds <= 0:
            self._stop_timer()
            self._on_resume_clicked()

    def _stop_timer(self) -> None:
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None

    def _on_resume_clicked(self) -> None:
        self._stop_timer()
        self.action = self.ACTION_RESUME
        self.accept()

    def _on_review_clicked(self) -> None:
        self._stop_timer()
        self.action = self.ACTION_REVIEW
        power_utils.restore_sleep()
        self.accept()

    def _on_close_clicked(self) -> None:
        self._stop_timer()
        self.action = self.ACTION_CLOSE
        power_utils.restore_sleep()
        self.reject()

    def reject(self) -> None:
        self._stop_timer()
        self.action = self.ACTION_CLOSE
        power_utils.restore_sleep()
        super().reject()

    def closeEvent(self, event) -> None:
        self._stop_timer()
        self.action = self.ACTION_CLOSE
        power_utils.restore_sleep()
        super().closeEvent(event)
