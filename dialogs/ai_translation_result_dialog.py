# dialogs/ai_translation_result_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton
)
from PyQt6.QtCore import Qt
from core.i18n import tr

class AITranslationResultDialog(QDialog):
    """Custom dialog for displaying detailed AI translation results in a scrollable format."""
    def __init__(self, parent, translation_details: dict):
        """
        Initialize the dialog.
        translation_details: Dict mapping block_idx (int) -> List of (string_idx (int), translated_text (str))
        """
        # Resolve parent widget correctly for QDialog
        from PyQt6.QtWidgets import QWidget
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)
        
        self.setWindowTitle(tr('AI Translation Results'))
        self.setMinimumSize(550, 400)
        self.resize(600, 450)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Calculate summary counts
        total_lines = 0
        total_blocks = len(translation_details)
        
        # Build text description
        lines_desc = []
        
        # Access main window data store for block names if possible
        mw = parent_widget
        # traverse up to find main window with data_store if parent is not main window
        while mw and not hasattr(mw, 'data_store'):
            mw = mw.parentWidget()
            
        ds = getattr(mw, 'data_store', None)
        
        for b_idx, items in sorted(translation_details.items()):
            block_name = None
            if ds and hasattr(ds, 'block_names') and ds.block_names:
                block_name = ds.block_names.get(str(b_idx))
            if not block_name:
                if b_idx == -2:
                    block_name = "Chapter Mode"
                elif b_idx == 999999:
                    block_name = "All Blocks Chronological"
                else:
                    block_name = f"Block {b_idx + 1}"
            
            lines_desc.append(f"=== {block_name} ===")
            for string_idx, text in sorted(items, key=lambda x: x[0]):
                total_lines += 1
                lines_desc.append(f"Line {string_idx + 1}:\n{text}\n")
            lines_desc.append("-" * 50)
            
        # 1. Title Summary Info Label
        summary_text = (
            f"AI translation finished successfully.<br>"
            f"Applied to <b>{total_lines}</b> line(s) across <b>{total_blocks}</b> block(s)."
        )
        self.info_label = QLabel(summary_text, self)
        self.info_label.setTextFormat(Qt.TextFormat.RichText)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        # 2. Read-only scrollable text edit for translation details
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.text_edit.setPlainText("\n".join(lines_desc))
        layout.addWidget(self.text_edit)
        
        # 3. Action Buttons Layout (standard OK/Close button)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.close_btn = QPushButton(tr('OK'), self)
        self.close_btn.setToolTip(
            tr('<b>OK</b><br>Click — close the result summary (Enter). The translations are already applied; nothing here is undone by closing.')
        )
        self.close_btn.setDefault(True)
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
