# dialogs/cached_translation_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton
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
        """
        from PyQt6.QtWidgets import QWidget
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)
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
        
        # 2. Source Label
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
                lines_desc.append(f"[{item['block_name']}] Line {item['string_idx'] + 1}:\n{item['text']}\n" + "-"*40)
            self.text_edit.setPlainText("\n".join(lines_desc))
            
        layout.addWidget(self.text_edit)
        
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
