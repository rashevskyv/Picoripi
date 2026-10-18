"""Offer a saved or remembered translation for the current string."""
# dialogs/cached_translation_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton, QCheckBox, QScrollArea
)
from PyQt6.QtCore import Qt
from core.i18n import tr

class CachedTranslationDialog(QDialog):
    """Custom dialog for displaying cached translations to prevent window stretching."""
    def __init__(self, parent, cached_info: list):
        """
        Initialize the dialog.
        cached_info: List of dicts containing keys:
            - 'block_idx': int
            - 'block_name': str
            - 'string_idx': int
            - 'text': str
            - 'from_memory': bool, optional -- saved for the same source text at another place
        """
        from PyQt6.QtWidgets import QWidget
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)
        self._cached_info = list(cached_info)
        cached_count = len(cached_info)
        
        # Set Window Title
        if cached_count == 1:
            self.setWindowTitle(tr('Cached Translation Detected'))
        else:
            self.setWindowTitle(tr('Cached Translations Detected'))
            
        # Layouts and settings
        self.setMinimumSize(500, 350)
        self.resize(550, 400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. Info Label
        info_text = ""
        if cached_count == 1:
            item = cached_info[0]
            info_text = (
                f"A cached translation is available for <b>{item['block_name']}</b>, "
                f"Line <b>{item['string_idx'] + 1}</b>.<br><br>"
                "Use cached translation?"
            )
        else:
            info_text = (
                f"Cached translations are available for <b>{cached_count}</b> of the selected lines.<br>"
                "For cached lines, the translation will be restored instantly. Other lines will be translated via AI.<br><br>"
                "Use cached translations?"
            )
            
        self.info_label = QLabel(info_text, self)
        self.info_label.setTextFormat(Qt.TextFormat.RichText)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        # 2. Source Label (series sentences have their own dialog: SeriesSentenceDialog, D45)
        if cached_count == 1 and cached_info[0].get('from_memory'):
            self.source_label = QLabel(tr('Source: saved for the same text elsewhere in the project'), self)
        else:
            self.source_label = QLabel(tr('Source: Loaded from cache'), self)
        self.source_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.source_label)
        
        # 3. Text Area
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Populate text
        if cached_count == 1:
            self.text_edit.setPlainText(cached_info[0]['text'])
        else:
            # Multi-line overview
            lines_desc = []
            for item in cached_info:
                origin = " " + self._origin_label(item) if item.get('from_memory') else ""
                lines_desc.append(f"[{item['block_name']}] Line {item['string_idx'] + 1}{origin}:\n{item['text']}\n" + "-"*40)
            self.text_edit.setPlainText("\n".join(lines_desc))

        layout.addWidget(self.text_edit)

        # One check box per line: checked lines take the saved text; an unchecked line is translated anew.
        self._row_boxes: list = []
        if cached_count > 1:
            rows_widget = QWidget(self)
            rows_layout = QVBoxLayout(rows_widget)
            rows_layout.setContentsMargins(0, 0, 0, 0)
            for item in cached_info:
                box = QCheckBox(f"[{item['block_name']}] Line {item['string_idx'] + 1}", rows_widget)
                box.setChecked(True)
                box.setToolTip(tr('Checked: use the saved text. Unchecked: translate this line anew.'))
                self._row_boxes.append((item, box))
                rows_layout.addWidget(box)
            rows_layout.addStretch()
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(160)
            scroll.setWidget(rows_widget)
            layout.addWidget(scroll)
        
        # 4. Action Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch()
        
        self.restore_btn = QPushButton(tr('OK'), self)
        self.restore_btn.setToolTip(
            tr('<b>Use the saved translation</b><br>Click — reuse the translation already in the backup database. No AI request is made (Enter).')
        )
        self.restore_btn.setDefault(True)
        self.restore_btn.clicked.connect(lambda: self.done(1))
        btn_layout.addWidget(self.restore_btn)
        
        self.translate_btn = QPushButton(tr('Translate Anew'), self)
        self.translate_btn.setToolTip(
            tr('<b>Translate anew</b><br>Click — ignore the saved translation and send a fresh AI request.<br>Ctrl-clicking AI Translate in the main window skips this dialog and always re-translates.')
        )
        self.translate_btn.clicked.connect(lambda: self.done(2))
        btn_layout.addWidget(self.translate_btn)
        
        self.cancel_btn = QPushButton(tr('Cancel'), self)
        self.cancel_btn.setToolTip(
            tr('<b>Cancel</b><br>Click — leave the string as it is and make no AI request (Esc).')
        )
        self.cancel_btn.clicked.connect(lambda: self.done(0))
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    @staticmethod
    def _origin_label(item: dict) -> str:
        """Where a remembered row comes from: another place of this project."""
        return tr('(same text elsewhere)')

    def accepted_positions(self) -> list:
        """``(block_idx, string_idx)`` of every line whose saved text is to be used (the checked lines)."""
        if not self._row_boxes:
            # one line: its text is the choice (OK restores it, Translate Anew and Cancel never reach here)
            return [(item['block_idx'], item['string_idx']) for item in self._cached_info]
        return [(item['block_idx'], item['string_idx']) for item, box in self._row_boxes if box.isChecked()]
