from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QTextBrowser,
    QPlainTextEdit, QComboBox, QPushButton, QHBoxLayout, QDialogButtonBox,
    QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QObject
from PyQt6.QtGui import QTextCursor


class _ChatInputEventFilter(QObject):
    """_ chat input event filter implementation."""
    def __init__(self, parent):
        """Initialize a new instance."""
        super().__init__(parent)

    def eventFilter(self, obj, event):
        """Eventfilter."""
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                obj.parent().message_sent.emit()
                return True
        return super().eventFilter(obj, event)


class _ChatTab(QWidget):
    """_ chat tab implementation."""
    message_sent = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        controls_layout = QHBoxLayout()
        self.model_combo = QComboBox(self)
        controls_layout.addWidget(self.model_combo)
        self.web_search_checkbox = QCheckBox("Web Search", self)
        controls_layout.addWidget(self.web_search_checkbox)
        controls_layout.addStretch(1)
        layout.addLayout(controls_layout)

        self.history_view = QTextBrowser(self)
        self.history_view.setOpenExternalLinks(True)
        layout.addWidget(self.history_view, 1)

        input_layout = QHBoxLayout()
        self.input_edit = QPlainTextEdit(self)
        self.input_edit.setFixedHeight(100)
        self.input_edit.setPlaceholderText("Enter your message... (Ctrl+Enter to send)")
        input_layout.addWidget(self.input_edit)

        self.send_button = QPushButton("Send", self)
        self.send_button.setFixedSize(80, 100)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #003c6c;
            }
        """)
        input_layout.addWidget(self.send_button)
        layout.addLayout(input_layout)

        self._event_filter = _ChatInputEventFilter(self)
        self.input_edit.installEventFilter(self._event_filter)
        self.send_button.clicked.connect(self.message_sent.emit)

    def populate_models(self, providers_data: dict):
        """Populate models."""
        self.model_combo.clear()
        for provider_key, provider_info in providers_data.items():
            display_name = provider_info.get('display_name', provider_key)
            self.model_combo.addItem(f"{display_name}: {provider_info['model']}", provider_key)


class AIChatDialog(QDialog):
    """Dialog class for a i chat."""
    message_sent = pyqtSignal(int, str, str, bool)  # tab_index, message, provider_key, web_search_enabled

    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.setWindowTitle("AI Chat")
        self.resize(700, 800)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        main_layout.addWidget(self.tabs)

        self.tabs.tabBar().installEventFilter(self)

        self.add_tab_button = QPushButton("+")
        self.add_tab_button.setToolTip("New Chat Session")
        self.tabs.setCornerWidget(self.add_tab_button, Qt.Corner.TopLeftCorner)
        
        self.tabs.tabCloseRequested.connect(self.remove_tab)
        
        self._set_theme_styles()

    def _set_theme_styles(self):
        """Internal helper to set the theme styles."""
        is_dark = self.palette().window().color().lightness() < 128
        user_bg = "#3A3A3A" if is_dark else "#E8F0FE"
        ai_bg = "#2E2E2E" if is_dark else "#F7F7F7"
        code_bg = "#4A4A4A" if is_dark else "#E0E0E0"
        code_border = "#5A5A5A" if is_dark else "#CCCCCC"
        
        user_prefix_color = "#8AB4F8" if is_dark else "#1A73E8"
        ai_prefix_color = "#92C594" if is_dark else "#1E8E3E"

        style = f"""
            .message-table {{
                width: 100%;
                border-spacing: 0;
                margin-bottom: 8px;
            }}
            .user-message td, .ai-message td {{
                padding: 8px;
                border-radius: 5px;
            }}
            .user-message td {{
                background-color: {user_bg};
            }}
            .ai-message td {{
                background-color: {ai_bg};
            }}
            .chat-prefix {{
                font-weight: bold;
                margin-bottom: 4px;
            }}
            .chat-prefix::after {{
                content: ':';
            }}
            .chat-prefix-user {{
                color: {user_prefix_color};
            }}
            .chat-prefix-ai {{
                color: {ai_prefix_color};
            }}
            .chat-content {{
                white-space: pre-wrap;
                word-wrap: break-word;
            }}
            code {{
                background-color: {code_bg};
                border: 1px solid {code_border};
                border-radius: 3px;
                padding: 1px 3px;
                font-family: Consolas, monospace;
            }}
            p {{
                margin-top: 0;
                margin-bottom: 8px;
                padding: 0;
            }}
            p:last-child {{
                margin-bottom: 0;
            }}
            ul, ol {{
                margin-top: 5px;
                margin-bottom: 5px;
            }}
        """
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, _ChatTab):
                tab.history_view.document().setDefaultStyleSheet(style)

    def eventFilter(self, obj, event):
        """Eventfilter."""
        if obj == self.tabs.tabBar() and event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.MiddleButton:
            tab_index = obj.tabAt(event.pos())
            if tab_index != -1:
                self.remove_tab(tab_index)
                return True
        return super().eventFilter(obj, event)

    def add_new_tab(self):
        """Add new tab."""
        tab_index = self.tabs.count()
        new_tab = _ChatTab(self)
        self.tabs.addTab(new_tab, f"Chat {tab_index + 1}")
        
        self._set_theme_styles()
        
        new_tab.message_sent.connect(lambda: self._emit_message_sent(self.tabs.indexOf(new_tab)))
        self.tabs.setCurrentIndex(tab_index)
        return new_tab

    def remove_tab(self, index: int):
        """Remove tab."""
        if self.tabs.count() > 1:
            widget = self.tabs.widget(index)
            self.tabs.removeTab(index)
            if widget:
                widget.deleteLater()
        else:
            self.close()

    def _emit_message_sent(self, tab_index):
        """Internal helper to emit message sent."""
        if tab_index < 0: return
        tab = self.tabs.widget(tab_index)
        if isinstance(tab, _ChatTab):
            message = tab.input_edit.toPlainText().strip()
            provider_key = tab.model_combo.currentData()
            web_search_enabled = tab.web_search_checkbox.isChecked()
            if message and provider_key:
                self.message_sent.emit(tab_index, message, provider_key, web_search_enabled)
                tab.input_edit.clear()

    def append_to_history(self, tab_index: int, html_text: str):
        """Append to history."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.history_view.append(html_text)

    def set_input_enabled(self, tab_index: int, enabled: bool):
        """Set the input enabled."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.input_edit.setReadOnly(not enabled)
                tab.send_button.setEnabled(enabled)