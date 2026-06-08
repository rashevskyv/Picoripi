from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QHBoxLayout, QSpinBox, QPushButton
from pathlib import Path

class MassFontDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Font for Multiple Lines")
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Select a font to apply to the selected lines:"))
        
        self.font_combo = QComboBox(self)
        self.populate_fonts(parent)
        layout.addWidget(self.font_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate_fonts(self, main_window):
        # We need access to main_window attributes
        default_font = getattr(main_window, 'default_font_file', 'None')
        self.font_combo.addItem(f"Plugin Default ({default_font})", "default")
        
        all_fonts = getattr(main_window, 'all_font_maps', {})
        if all_fonts:
            for font_key in sorted(all_fonts.keys()):
                if font_key != default_font:
                    self.font_combo.addItem(font_key, font_key)

    def get_selected_font(self):
        return self.font_combo.currentData()

class MassWidthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Set Width for Multiple Lines")
        layout = QVBoxLayout(self)
        
        self.default_width = getattr(parent, 'game_dialog_max_width_pixels', 0) if parent else 0
        layout.addWidget(QLabel(f"Enter a new width for the selected lines.\nEnter 0 or {self.default_width} to reset to plugin default ({self.default_width})."))
        
        controls_layout = QHBoxLayout()
        self.width_spinbox = QSpinBox(self)
        self.width_spinbox.setRange(0, 10000)
        self.width_spinbox.setValue(self.default_width)
        controls_layout.addWidget(self.width_spinbox)

        self.default_button = QPushButton("Default", self)
        self.default_button.clicked.connect(self.set_default_width)
        controls_layout.addWidget(self.default_button)
        layout.addLayout(controls_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def get_width(self):
        return self.width_spinbox.value()

    def set_default_width(self):
        self.width_spinbox.setValue(self.default_width)
