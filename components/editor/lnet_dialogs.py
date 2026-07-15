from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QHBoxLayout, QSpinBox, QPushButton, QCheckBox
from pathlib import Path

class MassFontDialog(QDialog):
    """Dialog class for mass font."""
    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.setWindowTitle("Set Font for Multiple Lines")
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Select a font to apply to the selected lines:"))
        
        self.font_combo = QComboBox(self)
        self.populate_fonts(parent)
        layout.addWidget(self.font_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate_fonts(self, main_window):
        # We need access to main_window attributes
        """Populate fonts."""
        default_font = getattr(main_window, 'default_font_file', 'None')
        self.font_combo.addItem(f"Plugin Default ({default_font})", "default")
        
        all_fonts = getattr(main_window, 'all_font_maps', {})
        if all_fonts:
            for font_key in sorted(all_fonts.keys()):
                if font_key != default_font:
                    self.font_combo.addItem(font_key, font_key)

    def get_selected_font(self):
        """Get the selected font."""
        return self.font_combo.currentData()

class MassWidthDialog(QDialog):
    """Dialog class for mass width."""
    def __init__(self, parent=None):
        """Initialize a new instance."""
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Set Width for Multiple Lines")
        layout = QVBoxLayout(self)
        
        # A multi-selection may contain several window kinds with different
        # defaults. Zero means "remove each string's override", allowing the
        # plugin to resolve the correct default independently for every line.
        self.default_width = 0
        layout.addWidget(QLabel(
            "Enter a new width for the selected lines.\n"
            "Enter 0 or click Default to use each line's window-type default."
        ))
        
        controls_layout = QHBoxLayout()
        self.width_spinbox = QSpinBox(self)
        self.width_spinbox.setRange(0, 10000)
        self.width_spinbox.setValue(self.default_width)
        controls_layout.addWidget(self.width_spinbox)

        self.default_button = QPushButton("Default", self)
        self.default_button.clicked.connect(self.set_default_width)
        controls_layout.addWidget(self.default_button)
        layout.addLayout(controls_layout)

        self.auto_width_checkbox = QCheckBox("Auto-width from original", self)
        self.auto_width_checkbox.setChecked(False)
        self.auto_width_checkbox.toggled.connect(self.on_auto_width_toggled)
        layout.addWidget(self.auto_width_checkbox)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def get_width(self):
        """Get the width."""
        return self.width_spinbox.value()

    def set_default_width(self):
        """Set the default width."""
        self.width_spinbox.setValue(self.default_width)

    def on_auto_width_toggled(self, checked):
        """Handle the auto width toggled event."""
        self.width_spinbox.setEnabled(not checked)
        self.default_button.setEnabled(not checked)

    def is_auto_width(self):
        """Check if is auto width."""
        return self.auto_width_checkbox.isChecked()
