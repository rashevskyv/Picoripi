"""AI Chat window: tabs, message queue, streaming answers, stop and retry."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QTextBrowser,
    QPlainTextEdit, QComboBox, QPushButton, QHBoxLayout, QCheckBox, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QObject
from PyQt6.QtGui import QFontMetrics, QTextCursor
from core.i18n import tr


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
    stop_requested = pyqtSignal()
    cancel_queue_requested = pyqtSignal()
    reset_context_requested = pyqtSignal()
    retry_requested = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        
        controls_layout = QHBoxLayout()
        self.model_combo = QComboBox(self)
        controls_layout.addWidget(self.model_combo)
        self.web_search_checkbox = QCheckBox(tr('Web Search'), self)
        controls_layout.addWidget(self.web_search_checkbox)

        self.status_label = QLabel(self)
        self.status_label.setStyleSheet("color: #777; font-size: 11px; padding: 2px 6px;")
        controls_layout.addWidget(self.status_label)
        controls_layout.addStretch(1)

        self.scroll_bottom_button = QPushButton(tr("↓ Bottom"), self)
        self.scroll_bottom_button.setToolTip(tr("Scroll to the bottom of the chat"))
        self.scroll_bottom_button.setStyleSheet("""
            QPushButton {
                padding: 2px 8px;
                font-size: 11px;
                border: 1px solid #bbb;
                border-radius: 4px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.15);
                border-color: #888;
            }
        """)
        self.scroll_bottom_button.clicked.connect(self.scroll_to_bottom)
        controls_layout.addWidget(self.scroll_bottom_button)

        self.reset_context_button = QPushButton(tr("Reset Context"), self)
        self.reset_context_button.setToolTip(tr("Clear conversation memory and start a new dialogue context"))
        self.reset_context_button.setStyleSheet("""
            QPushButton {
                padding: 2px 8px;
                font-size: 11px;
                border: 1px solid #bbb;
                border-radius: 4px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: rgba(230, 76, 60, 0.15);
                border-color: #e74c3c;
                color: #c0392b;
            }
        """)
        self.reset_context_button.clicked.connect(self.reset_context_requested.emit)
        controls_layout.addWidget(self.reset_context_button)

        layout.addLayout(controls_layout)

        self.history_view = QTextBrowser(self)
        self.history_view.setOpenExternalLinks(True)
        layout.addWidget(self.history_view, 1)

        self.floating_bottom_btn = QPushButton("↓", self.history_view.viewport())
        self.floating_bottom_btn.setFixedSize(32, 32)
        self.floating_bottom_btn.setToolTip(tr("Scroll to the bottom of the chat"))
        self.floating_bottom_btn.setStyleSheet("""
            QPushButton {
                border-radius: 16px;
                background-color: #0078d4;
                color: white;
                font-weight: bold;
                font-size: 16px;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.floating_bottom_btn.clicked.connect(self.scroll_to_bottom)
        self.floating_bottom_btn.hide()

        self.history_view.viewport().installEventFilter(self)
        self.history_view.verticalScrollBar().valueChanged.connect(self._update_floating_bottom_btn)
        self.history_view.verticalScrollBar().rangeChanged.connect(self._update_floating_bottom_btn)

        # Queue banner above input layout
        self.queue_bar = QWidget(self)
        queue_layout = QHBoxLayout(self.queue_bar)
        queue_layout.setContentsMargins(6, 3, 6, 3)
        self.queue_bar.setStyleSheet("""
            QWidget {
                background-color: rgba(230, 126, 34, 0.12);
                border: 1px solid #e67e22;
                border-radius: 4px;
            }
        """)
        self.queue_label = QLabel(self.queue_bar)
        self.queue_label.setStyleSheet("border: none; color: #d35400; font-weight: bold; font-size: 11px;")
        queue_layout.addWidget(self.queue_label, 1)
        self.cancel_queue_btn = QPushButton(tr("Cancel Queue"), self.queue_bar)
        self.cancel_queue_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """)
        self.cancel_queue_btn.clicked.connect(self.cancel_queue_requested.emit)
        queue_layout.addWidget(self.cancel_queue_btn)
        self.queue_bar.setVisible(False)
        layout.addWidget(self.queue_bar)

        input_layout = QHBoxLayout()
        self.input_edit = QPlainTextEdit(self)
        self.input_edit.setFixedHeight(100)
        self.input_edit.setPlaceholderText(tr('Enter your message... (Ctrl+Enter to send)'))
        input_layout.addWidget(self.input_edit, 1)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)

        bold_font = self.font()
        bold_font.setBold(True)
        fm = QFontMetrics(bold_font)
        button_width = max(
            110,
            fm.horizontalAdvance(tr('Send')) + 30,
            fm.horizontalAdvance(tr('Stop')) + 30,
            fm.horizontalAdvance(tr('Retry')) + 30,
        )

        self.send_button = QPushButton(tr('Send'), self)
        self.send_button.setFixedSize(button_width, 100)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                padding: 3px 6px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #003c6c;
            }
        """)
        btn_layout.addWidget(self.send_button)

        self.retry_button = QPushButton(tr('Retry'), self)
        self.retry_button.setFixedSize(button_width, 28)
        self.retry_button.setToolTip(tr('Retry the last message'))
        self.retry_button.setShortcut("Ctrl+Shift+R")
        self.retry_button.setStyleSheet("""
            QPushButton {
                background-color: #ea580c;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #c2410c;
            }
            QPushButton:pressed {
                background-color: #9a3412;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self.retry_button.setEnabled(False)
        self.retry_button.setVisible(False)
        self.retry_button.clicked.connect(self.retry_requested.emit)
        btn_layout.addWidget(self.retry_button)

        self.stop_button = QPushButton(tr('Stop'), self)
        self.stop_button.setFixedSize(button_width, 28)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #d9534f;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #c9302c;
            }
            QPushButton:pressed {
                background-color: #ac2925;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """)
        self.stop_button.setEnabled(False)
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        btn_layout.addWidget(self.stop_button)

        input_layout.addLayout(btn_layout)
        layout.addLayout(input_layout)

        self._can_retry = False
        self._event_filter = _ChatInputEventFilter(self)
        self.input_edit.installEventFilter(self._event_filter)
        self.send_button.clicked.connect(self.message_sent.emit)

    def set_status(self, text: str):
        """Set diagnostic status text."""
        self.status_label.setText(text)

    def set_can_retry(self, can_retry: bool, last_message: str = ""):
        """Set whether the retry button is enabled/visible when idle."""
        self._can_retry = can_retry
        if last_message:
            preview = last_message[:60] + ("..." if len(last_message) > 60 else "")
            self.retry_button.setToolTip(f"{tr('Retry the last message')}:\n\"{preview}\"")
        else:
            self.retry_button.setToolTip(tr('Retry the last message'))

        if not self.stop_button.isVisible():
            self.retry_button.setVisible(can_retry)
            self.retry_button.setEnabled(can_retry)
            if can_retry:
                self.send_button.setFixedHeight(68)
            else:
                self.send_button.setFixedHeight(100)

    def set_generating(self, generating: bool):
        """Toggle UI state when generating or idle."""
        self.stop_button.setVisible(generating)
        self.stop_button.setEnabled(generating)
        self.reset_context_button.setEnabled(not generating)
        if generating:
            self.retry_button.setVisible(False)
            self.retry_button.setEnabled(False)
            self.send_button.setFixedHeight(68)
        else:
            can_retry = getattr(self, '_can_retry', False)
            self.retry_button.setVisible(can_retry)
            self.retry_button.setEnabled(can_retry)
            if can_retry:
                self.send_button.setFixedHeight(68)
            else:
                self.send_button.setFixedHeight(100)

    def set_queue_count(self, count: int):
        """Update queue banner visibility and message count."""
        if count > 0:
            msg = tr("In Queue: {n} message(s) waiting for AI").format(n=count)
            self.queue_label.setText(f"⏳ {msg}")
            self.queue_bar.setVisible(True)
        else:
            self.queue_bar.setVisible(False)

    def eventFilter(self, obj, event):
        """Handle viewport resize to reposition floating bottom button."""
        if hasattr(self, 'history_view') and obj == self.history_view.viewport():
            if event.type() == QEvent.Type.Resize:
                self._update_floating_bottom_btn()
        return super().eventFilter(obj, event)

    def _update_floating_bottom_btn(self):
        """Update visibility and position of the floating scroll-to-bottom button."""
        if not hasattr(self, 'floating_bottom_btn') or not hasattr(self, 'history_view'):
            return
        at_bottom = self.is_at_bottom(60)
        self.floating_bottom_btn.setVisible(not at_bottom)
        if not at_bottom:
            vp = self.history_view.viewport()
            btn_size = 32
            x = vp.width() - btn_size - 14
            y = vp.height() - btn_size - 14
            self.floating_bottom_btn.move(max(0, x), max(0, y))
            self.floating_bottom_btn.raise_()

    def scroll_to_response(self, pos: int):
        """Scroll history view so that the response at `pos` is visible at the top of the viewport."""
        doc = self.history_view.document()
        if doc.characterCount() <= 1:
            return
        cursor = self.history_view.textCursor()
        cursor.setPosition(max(0, min(pos, doc.characterCount() - 1)))
        rect = self.history_view.cursorRect(cursor)
        sb = self.history_view.verticalScrollBar()
        target_scroll = sb.value() + rect.y() - 10
        sb.setValue(max(0, target_scroll))
        self._update_floating_bottom_btn()

    def scroll_to_bottom(self):
        """Scroll history view to the bottom."""
        sb = self.history_view.verticalScrollBar()
        sb.setValue(sb.maximum())
        self._update_floating_bottom_btn()

    def is_at_bottom(self, threshold: int = 40) -> bool:
        """Check if history view is currently scrolled near the bottom."""
        sb = self.history_view.verticalScrollBar()
        try:
            val = sb.value()
            max_val = sb.maximum()
            return bool(val >= max_val - threshold)
        except (TypeError, AttributeError):
            return True

    def remove_text_after(self, pos: int):
        """Remove all text from pos to the end of the document."""
        if pos <= 0:
            return
        cursor = self.history_view.textCursor()
        cursor.setPosition(pos)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()

    def insert_stream_chunk(self, chunk: str, auto_scroll: bool = True):
        """Insert a streaming text chunk and conditionally scroll to bottom."""
        cursor = self.history_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        if auto_scroll:
            self.history_view.setTextCursor(cursor)
            self.scroll_to_bottom()

    def get_document_end_pos(self) -> int:
        """Return the character count offset at the end of the document."""
        return max(0, self.history_view.document().characterCount() - 1)

    def populate_models(self, providers_data: dict):
        """Populate models."""
        self.model_combo.clear()
        for provider_key, provider_info in providers_data.items():
            display_name = provider_info.get('display_name', provider_key)
            self.model_combo.addItem(f"{display_name}: {provider_info['model']}", provider_key)


class AIChatDialog(QDialog):
    """Dialog class for a i chat."""
    message_sent = pyqtSignal(int, str, str, bool)  # tab_index, message, provider_key, web_search_enabled
    stop_generation_requested = pyqtSignal(int)  # tab_index
    cancel_queue_requested = pyqtSignal(int)  # tab_index
    reset_context_requested = pyqtSignal(int)  # tab_index
    retry_requested = pyqtSignal(int)  # tab_index

    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(None)
        self.main_window = parent
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle(tr('AI Chat'))
        self.resize(700, 800)

        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        main_layout.addWidget(self.tabs)

        self.tabs.tabBar().installEventFilter(self)

        self.add_tab_button = QPushButton(tr('+'))
        self.add_tab_button.setToolTip(tr('New Chat Session'))
        self.tabs.setCornerWidget(self.add_tab_button, Qt.Corner.TopLeftCorner)
        
        self.tabs.tabCloseRequested.connect(self.remove_tab)
        
        self._set_theme_styles()

    def _set_theme_styles(self):
        """Internal helper to set the theme styles."""
        is_dark = self.palette().window().color().lightness() < 128
        user_bg = "#3A3A3A" if is_dark else "#E8F0FE"
        ai_bg = "#2E2E2E" if is_dark else "#F7F7F7"
        code_bg = "#4A4A4A" if is_dark else "#EAEAEA"
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
                word-wrap: break-word;
            }}
            .user-chat-content {{
                white-space: pre-wrap;
            }}
            code {{
                background-color: {code_bg};
                border: 1px solid {code_border};
                border-radius: 3px;
                padding: 1px 3px;
                font-family: Consolas, monospace;
            }}
            pre {{
                background-color: {code_bg};
                border: 1px solid {code_border};
                border-radius: 4px;
                padding: 6px;
                font-family: Consolas, monospace;
                margin: 6px 0;
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
                margin-top: 4px;
                margin-bottom: 6px;
                padding-left: 20px;
            }}
            li {{
                margin-bottom: 3px;
            }}
            h1, h2, h3, h4, h5 {{
                margin-top: 8px;
                margin-bottom: 4px;
                font-weight: bold;
            }}
            h1 {{ font-size: 1.25em; }}
            h2 {{ font-size: 1.15em; }}
            h3 {{ font-size: 1.05em; }}
            h4 {{ font-size: 1.0em; }}
            hr {{
                border: 0;
                border-top: 1px solid {code_border};
                margin: 8px 0;
            }}
            blockquote {{
                border-left: 3px solid {ai_prefix_color};
                margin: 6px 0;
                padding-left: 8px;
                color: #888;
            }}
            table.md-table, table {{
                border-collapse: collapse;
                margin: 8px 0;
                width: 100%;
            }}
            th, td {{
                border: 1px solid {code_border};
                padding: 4px 8px;
            }}
            .message-table td {{
                border: none;
            }}
            th {{
                background-color: {code_bg};
                font-weight: bold;
            }}
            .chat-queue-badge {{
                background-color: #e67e22;
                color: white;
                border-radius: 3px;
                padding: 1px 6px;
                font-size: 0.8em;
                font-weight: normal;
                margin-left: 6px;
            }}
            .chat-interrupted-warning {{
                margin-top: 8px;
                padding: 6px 10px;
                background-color: rgba(255, 193, 7, 0.15);
                border-left: 3px solid #ffc107;
                color: #b27b00;
                font-size: 0.9em;
                border-radius: 2px;
            }}
            .chat-thinking {{
                color: #888;
                font-style: italic;
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
        new_tab.stop_requested.connect(lambda: self.stop_generation_requested.emit(self.tabs.indexOf(new_tab)))
        new_tab.cancel_queue_requested.connect(lambda: self.cancel_queue_requested.emit(self.tabs.indexOf(new_tab)))
        new_tab.reset_context_requested.connect(lambda: self.reset_context_requested.emit(self.tabs.indexOf(new_tab)))
        new_tab.retry_requested.connect(lambda: self.retry_requested.emit(self.tabs.indexOf(new_tab)))
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

    def set_tab_status(self, tab_index: int, text: str):
        """Set status text for a specific tab."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.set_status(text)

    def set_tab_generating(self, tab_index: int, generating: bool):
        """Set generating state for a specific tab."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.set_generating(generating)

    def set_tab_can_retry(self, tab_index: int, can_retry: bool, last_message: str = ""):
        """Set whether retry button is enabled/visible for a specific tab."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.set_can_retry(can_retry, last_message=last_message)

    def set_tab_queue_count(self, tab_index: int, count: int):
        """Set queue count banner for a specific tab."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.set_queue_count(count)

    def scroll_to_response(self, tab_index: int, pos: int):
        """Scroll history view of a specific tab so that response at pos is visible."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.scroll_to_response(pos)

    def scroll_to_bottom(self, tab_index: int):
        """Scroll history view of a specific tab to the bottom."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if isinstance(tab, _ChatTab):
                tab.scroll_to_bottom()

    def is_tab_at_bottom(self, tab_index: int, threshold: int = 40) -> bool:
        """Check if a specific tab is currently near the bottom."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if hasattr(tab, 'is_at_bottom'):
                return tab.is_at_bottom(threshold)
        return True

    def remove_tab_text_after(self, tab_index: int, pos: int):
        """Remove all text from pos to end of document for a specific tab."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if hasattr(tab, 'remove_text_after'):
                tab.remove_text_after(pos)

    def insert_tab_stream_chunk(self, tab_index: int, chunk: str, auto_scroll: bool = True):
        """Insert a stream chunk into a specific tab."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if hasattr(tab, 'insert_stream_chunk'):
                tab.insert_stream_chunk(chunk, auto_scroll=auto_scroll)

    def get_tab_document_end_pos(self, tab_index: int) -> int:
        """Return end pos for a specific tab."""
        if 0 <= tab_index < self.tabs.count():
            tab = self.tabs.widget(tab_index)
            if hasattr(tab, 'get_document_end_pos'):
                return tab.get_document_end_pos()
        return 0