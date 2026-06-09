# /home/runner/work/RAG_project/RAG_project/ui/settings_dialog.py
import os
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QColorDialog, QPushButton
from PyQt6.QtGui import QColor
from PyQt6.QtCore import pyqtSignal

class ColorPickerButton(QPushButton):
    colorChanged = pyqtSignal(QColor)

    def __init__(self, initial_color=QColor("black"), parent=None):
        super().__init__(parent)
        self._color = QColor(initial_color)
        try:
            self.setText(self._color.name(QColor.HexArgb))
        except Exception:
            self.setText(self._color.name())
        self.setToolTip("Click to choose a color")
        self.clicked.connect(self.pick_color)
        self._update_style()

    def color(self) -> QColor:
        return self._color

    def setColor(self, color: QColor):
        if self._color != color:
            self._color = color
            try:
                self.setText(self._color.name(QColor.HexArgb))
            except Exception:
                self.setText(self._color.name())
            self._update_style()
            self.colorChanged.emit(self._color)

    def _update_style(self):
        self.setStyleSheet(f"background-color: {self._color.name()}; color: {self._get_contrasting_text_color(self._color)};")

    def _get_contrasting_text_color(self, bg_color: QColor) -> str:
        return "white" if bg_color.lightness() < 128 else "black"

    def pick_color(self):
        try:
            options = QColorDialog.ShowAlphaChannel
        except Exception:
            options = 0
        chosen = QColorDialog.getColor(self._color, self.window(), "Select Color", options)
        if chosen.isValid():
            self.setColor(chosen)

class TagDisplayWidget(QWidget):
    textChanged = pyqtSignal(str)

    def __init__(self, initial_text="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        
        self.line_edit = QLineEdit(initial_text, self)
        layout.addWidget(self.line_edit)
        
        self.color_btn = QPushButton(self)
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setToolTip("Pick color")
        layout.addWidget(self.color_btn)
        
        self.color_btn.clicked.connect(self._pick_color)
        self.line_edit.textChanged.connect(self._update_btn_color)
        self._update_btn_color()

    def _update_btn_color(self):
        text = self.line_edit.text().strip()
        if text.startswith('#') and len(text) in (4, 7, 9):
            self.color_btn.setStyleSheet(f"background-color: {text}; border: 1px solid gray; border-radius: 2px;")
            self.color_btn.setText("")
        else:
            self.color_btn.setStyleSheet("border: 1px solid gray; border-radius: 2px;")
            self.color_btn.setText("...")
        self.textChanged.emit(text)

    def _pick_color(self):
        current_text = self.line_edit.text().strip()
        initial_color = QColor(current_text) if current_text.startswith('#') else QColor("white")
        
        try:
            options = QColorDialog.ShowAlphaChannel
        except Exception:
            options = 0
            
        color = QColorDialog.getColor(initial_color, self.window(), "Pick color", options)
        if color.isValid():
            try:
                self.line_edit.setText(color.name(QColor.HexArgb).upper())
            except Exception:
                self.line_edit.setText(color.name().upper())

    def text(self):
        return self.line_edit.text().strip()
