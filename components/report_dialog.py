# components/report_dialog.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QPushButton
from PyQt6.QtCore import Qt

class LargeTextReportDialog(QDialog):
    """Dialog class for large text report."""
    def __init__(self, title: str, text: str, parent=None):
        # Handle mocking in tests
        """Initialize a new instance."""
        from PyQt6.QtWidgets import QWidget
        if parent is not None and (not isinstance(parent, QWidget) or "Mock" in str(type(parent))):
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
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        # Performance optimization for very long text
        self.text_edit.setUndoRedoEnabled(False)
