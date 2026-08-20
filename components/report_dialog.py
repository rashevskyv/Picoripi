# components/report_dialog.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QPushButton

class LargeTextReportDialog(QDialog):
    """Dialog class for large text report."""
    def __init__(self, title: str, text: str, parent=None):
        # Handle test/fallback context
        """Initialize a new instance."""
        from PyQt6.QtWidgets import QWidget
        if parent is not None and (not isinstance(parent, QWidget) or bool(getattr(parent, '_is_test_mode', False))):
            parent = None
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(text)
        self.text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text_edit)
        
        close_btn = QPushButton("Close", self)
        close_btn.setToolTip(
            "<b>Close</b><br>"
            "Click — dismiss the report (Esc).<br>"
            "Select text above and press Ctrl+C first if you want to keep a copy."
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        # Performance optimization for very long text
        self.text_edit.setUndoRedoEnabled(False)
