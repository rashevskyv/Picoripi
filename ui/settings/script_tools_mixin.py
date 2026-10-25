"""Settings controls for user-defined toolbar scripts."""
from PyQt6.QtCore import QPointF, QRegularExpression, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap, QRegularExpressionValidator, QValidator
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from core.i18n import tr


class ToolBadgeDialog(QDialog):
    """Edit a short text badge and preview its toolbar rendering."""

    def __init__(self, badge: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit Tool Icon"))
        layout = QVBoxLayout(self)
        self.badge_edit = QLineEdit(badge, self)
        self.badge_edit.setValidator(BadgeLengthValidator(self.badge_edit))
        self.badge_edit.setPlaceholderText(tr("Examples: B, B1, ▶️, 🔧"))
        layout.addWidget(QLabel(tr("Text or emoji badge:"), self))
        layout.addWidget(self.badge_edit)
        self.preview = QLabel(self)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(64, 64)
        layout.addWidget(self.preview, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.badge_edit.textChanged.connect(self._update_preview)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_preview(self.badge_edit.text())

    def _update_preview(self, text: str) -> None:
        self.preview.setPixmap(tool_badge_icon(text).pixmap(48, 48))

    def accept(self):
        if self.badge_edit.hasAcceptableInput():
            super().accept()


def tool_badge_icon(text: str):
    """Render a short text or emoji badge for a toolbar action."""
    from PyQt6.QtGui import QIcon

    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QColor("#0078d7"))
    font = QFont("Segoe UI", 12, QFont.Weight.Bold)
    painter.setFont(font)
    metrics = painter.fontMetrics()
    available = pixmap.width() - 4
    width = max(1, metrics.horizontalAdvance(text))
    height = max(1, metrics.height())
    scale = min(1.0, available / width, available / height)
    painter.translate(pixmap.width() / 2, pixmap.height() / 2)
    painter.scale(scale, scale)
    painter.drawText(QPointF(-width / 2, (metrics.ascent() - metrics.descent()) / 2), text)
    painter.end()
    return QIcon(pixmap)


class BadgeLengthValidator(QValidator):
    """Limit badge length by Unicode code points without cutting emoji sequences."""

    def validate(self, text: str, position: int):
        state = QValidator.State.Acceptable if is_valid_badge(text) else QValidator.State.Invalid
        return state, text, position


def is_valid_badge(text: str) -> bool:
    """Return whether a badge fits the short, Unicode-safe input limit."""
    return len(text) <= 8 and not any(0xD800 <= ord(char) <= 0xDFFF for char in text)


class SettingsScriptToolsMixin:
    """Build and read the scrollable custom script tool list."""

    def setup_tools_tab(self):
        layout = QVBoxLayout(self.tools_tab)
        self.tool_rows = []
        self.tools_scroll = QScrollArea(self.tools_tab)
        self.tools_scroll.setWidgetResizable(True)
        self.tools_rows_widget = QWidget(self.tools_scroll)
        self.tools_rows_layout = QVBoxLayout(self.tools_rows_widget)
        self.tools_rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tools_scroll.setWidget(self.tools_rows_widget)
        layout.addWidget(self.tools_scroll)
        self.add_tool_button = QPushButton(tr("+ Add tool"), self.tools_tab)
        self.add_tool_button.clicked.connect(lambda: self._add_tool_row({"name": "", "path": "", "icon": "B"}))
        layout.addWidget(self.add_tool_button, alignment=Qt.AlignmentFlag.AlignLeft)

    def _add_tool_row(self, tool):
        row = QWidget(self.tools_rows_widget)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        badge = str(tool.get("icon", "B"))[:8]
        icon_button = QPushButton(row)
        icon_button.setFixedSize(36, 32)
        icon_button.setIcon(tool_badge_icon(badge))
        icon_button.setToolTip(tr("Edit tool icon"))
        badge_holder = [badge]
        icon_button.clicked.connect(lambda: self._edit_tool_badge(icon_button, badge_holder))
        name_edit = QLineEdit(str(tool.get("name", "")), row)
        name_edit.setValidator(QRegularExpressionValidator(QRegularExpression(".{0,80}"), name_edit))
        name_edit.setPlaceholderText(tr("Tool name"))
        path_edit = QLineEdit(str(tool.get("path", "")), row)
        path_edit.setPlaceholderText(tr("Path to .bat, .cmd, .exe, .py, etc."))
        browse_button = QPushButton(tr("Browse"), row)
        browse_button.clicked.connect(lambda: self._browse_tool_path(path_edit))
        remove_button = QPushButton(tr("Remove"), row)
        remove_button.clicked.connect(lambda: self._remove_tool_row(row))
        row_layout.addWidget(icon_button)
        row_layout.addWidget(name_edit, 1)
        row_layout.addWidget(path_edit, 2)
        row_layout.addWidget(browse_button)
        row_layout.addWidget(remove_button)
        self.tools_rows_layout.addWidget(row)
        self.tool_rows.append((row, icon_button, name_edit, path_edit, badge_holder))

    def _edit_tool_badge(self, button, badge_holder):
        dialog = ToolBadgeDialog(badge_holder[0], self)
        if dialog.exec():
            badge_holder[0] = dialog.badge_edit.text() or "B"
            button.setIcon(tool_badge_icon(badge_holder[0]))

    def _browse_tool_path(self, edit):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Select External Script/Tool"), edit.text().strip(),
            "Scripts/Executables (*.bat *.cmd *.exe *.py *.sh);;All Files (*)",
        )
        if path:
            edit.setText(path)

    def _remove_tool_row(self, row):
        self.tool_rows = [entry for entry in self.tool_rows if entry[0] is not row]
        self.tools_rows_layout.removeWidget(row)
        row.deleteLater()

    def get_external_tools(self):
        tools = []
        for _, icon_button, name, path, badge in self.tool_rows:
            if name.text().strip() or path.text().strip():
                if not is_valid_badge(badge[0]):
                    badge[0] = "B"
                    icon_button.setIcon(tool_badge_icon(badge[0]))
                tools.append({"name": name.text().strip(), "path": path.text().strip(), "icon": badge[0]})
        return tools

    def load_external_tools(self, tools):
        for row, *_ in self.tool_rows:
            self.tools_rows_layout.removeWidget(row)
            row.deleteLater()
        self.tool_rows.clear()
        for tool in tools:
            self._add_tool_row(tool)
