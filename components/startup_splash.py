"""Responsive startup window shown before the main UI is ready."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget
from core.i18n import tr


class StartupSplash(QWidget):
    """Small frameless progress window that remains responsive during startup."""

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 210)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(42, 34, 42, 32)
        layout.setSpacing(12)

        title = QLabel(tr('PICORIPI'))
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #f3f0ff; letter-spacing: 3px;")

        subtitle = QLabel(tr('Translation Workbench'))
        subtitle.setStyleSheet("color: #aca4c7; font-size: 11px;")

        self.status_label = QLabel(tr('Starting…'))
        self.status_label.setStyleSheet("color: #ffffff; font-size: 12px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setStyleSheet(
            "QProgressBar { color: white; border: 1px solid #51486d; "
            "border-radius: 7px; background: #24202f; text-align: center; }"
            "QProgressBar::chunk { border-radius: 6px; "
            "background-color: #8b6cef; }"
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#17141f"))
        painter.setPen(QColor("#453b5d"))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 18, 18)
        super().paintEvent(event)

    def show_centered(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.center() - self.rect().center())
        self.show()
        self.raise_()
        self.repaint()
        self.progress_bar.repaint()

    def update_progress(self, value: int, message: str) -> None:
        self.progress_bar.setValue(max(0, min(100, int(value))))
        self.status_label.setText(message)
        # repaint() is synchronous and keeps the progress visible.  Running the
        # whole application event queue here allowed startup timers to re-enter
        # project loading before the current phase had finished.
        self.repaint()
