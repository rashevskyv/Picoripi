from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QHBoxLayout, QAbstractItemView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

class HelpShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts Reference")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        
        title_label = QLabel("Keyboard Shortcuts")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(False) 
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setAlternatingRowColors(True)
        
        self.shortcuts = [
            # Category: General
            ("--- GENERAL ---", ""),
            ("Save Project/File", "Ctrl + S"),
            ("AI Chat Window", "Ctrl + Shift + C"),
            ("Shortcuts Help", "F1"),
            ("Settings", "Ctrl + P"),
            
            # Category: Editor
            ("--- EDITOR ---", ""),
            ("Undo", "Ctrl + Z"),
            ("Redo", "Ctrl + Y / Ctrl + Shift + Z"),
            ("Find Text", "Ctrl + F"),
            ("Find Next", "F3"),
            ("Find Previous", "Shift + F3"),
            ("Paste Block Text", "Ctrl + Shift + V"),
            ("Auto-fix Current String", "Ctrl + Shift + A"),
            
            # Category: Navigation
            ("--- NAVIGATION ---", ""),
            ("Navigate to Next Problem", "Ctrl + Down"),
            ("Navigate to Previous Problem", "Ctrl + Up"),
            ("Select Next String", "Alt + Down / Down (in Preview)"),
            ("Select Previous String", "Alt + Up / Up (in Preview)"),
            ("Next Block", "Alt + Shift + Down"),
            ("Previous Block", "Alt + Shift + Up"),
            ("Next Folder/Category", "Alt + Shift + Right"),
            ("Previous Folder/Category", "Alt + Shift + Left"),
        ]
        
        self.table.setRowCount(len(self.shortcuts))
        for i, (action, shortcut) in enumerate(self.shortcuts):
            item_action = QTableWidgetItem(action)
            item_shortcut = QTableWidgetItem(shortcut)
            
            if action.startswith("---"):
                # Style as section header
                item_action.setBackground(QColor("#333333"))
                item_action.setForeground(QColor("white"))
                item_action.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                item_shortcut.setBackground(QColor("#333333"))
                # Merge or Span column would be better but let's just make it look like a header
                
            self.table.setItem(i, 0, item_action)
            self.table.setItem(i, 1, item_shortcut)
            self.table.item(i, 1).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
        layout.addWidget(self.table)
        
        footer_layout = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        footer_layout.addStretch()
        footer_layout.addWidget(close_button)
        layout.addLayout(footer_layout)

def show_shortcuts_dialog(parent):
    dialog = HelpShortcutsDialog(parent)
    dialog.exec()
