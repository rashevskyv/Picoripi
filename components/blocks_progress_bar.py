"""The overall translation progress bar beside "Blocks:": red when little is done, through yellow to green."""
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QProgressBar, QSizePolicy

from core.i18n import tr


def progress_color(fraction: float) -> QColor:
    """Hue 0 (red) at 0 % through 60 (yellow) to 120 (green) at 100 %."""
    return QColor.fromHsv(int(120 * min(max(fraction, 0.0), 1.0)), 170, 210)


class BlocksProgressBar(QProgressBar):
    """Rows translated of rows that need a translation, for the whole project."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(40)
        self.setMaximumHeight(18)
        self.setTextVisible(True)
        self.setVisible(False)

    def show_progress(self, done: int, total: int) -> None:
        """Hidden while the project has no row to translate."""
        self.setVisible(total > 0)
        if total <= 0:
            return
        self.setRange(0, total)
        self.setValue(done)
        self.setFormat(f"{done} / {total} (%p%)")
        self.setToolTip(tr('Translated rows in the whole project: {done} of {total}', done=done, total=total))
        chunk = progress_color(done / total).name()
        self.setStyleSheet(
            "QProgressBar { border: 1px solid palette(mid); border-radius: 3px; text-align: center; }"
            f"QProgressBar::chunk {{ background-color: {chunk}; border-radius: 2px; }}")
