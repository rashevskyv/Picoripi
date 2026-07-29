# dialogs/tag_alias_dialog.py
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QMessageBox)
from PyQt6.QtGui import QIntValidator
from PyQt6.QtCore import QThread, pyqtSignal, QTimer

FORCE_ALIAS_INFO = (
    "You have enabled the Force Alias option for this tag.\n\n"
    "This permanently replaces the dynamic name tag with its plain text translation in the final exported game.\n\n"
    "In the original game, character and horse names are customizable, but we lock them to 'Link' and 'Epona'. "
    "This allows us to grammatically inflect them properly in our Slavic translation (e.g. 'Лінку', 'Епоні') and handle addressing properly.\n\n"
    "The AI will translate the name (e.g., 'Link' to 'Лінку'), and it will remain as plain text in the exported game."
)

class TagAliasDialog(QDialog):
    """Dialog class for tag alias."""
    def __init__(self, parent, title: str, original_tag: str, current_alias: str = "", current_width: int = None):
        """Initialize a new instance."""
        self._is_initializing = True
        self.mw = parent
        from PyQt6.QtWidgets import QWidget
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(380, 245)
        
        layout = QVBoxLayout(self)
        
        # Info about original tag
        self.info_label = QLabel(f"Original tag: <b>{original_tag}</b>", self)
        layout.addWidget(self.info_label)
        
        # Force alias checkbox
        self.force_checkbox = QCheckBox("Force alias (convert tag to permanent plain text)", self)
        self.force_checkbox.setToolTip(FORCE_ALIAS_INFO)
        layout.addWidget(self.force_checkbox)
        
        # Alias field
        layout.addWidget(QLabel("Alias name (will be enclosed in curly braces):", self))
        
        alias_input_layout = QHBoxLayout()
        self.prefix_label = QLabel("F:", self)
        self.prefix_label.setStyleSheet("font-weight: bold; font-size: 11pt; color: #808080;")
        self.alias_edit = QLineEdit(self)
        alias_input_layout.addWidget(self.prefix_label)
        alias_input_layout.addWidget(self.alias_edit)
        layout.addLayout(alias_input_layout)
        
        # Custom width field (defined first so it exists when setting initial checkbox state)
        self.width_label = QLabel("Custom width in pixels (leave empty for none):", self)
        layout.addWidget(self.width_label)
        self.width_edit = QLineEdit(self)
        self.width_edit.setValidator(QIntValidator(1, 9999, self))
        if current_width is not None:
            self.width_edit.setText(str(current_width))
        layout.addWidget(self.width_edit)
        
        # Connect signals
        self.force_checkbox.stateChanged.connect(self._on_force_changed)
        self.alias_edit.textChanged.connect(self._on_text_changed)
        self.alias_edit.returnPressed.connect(self.accept)
        self.width_edit.returnPressed.connect(self.accept)

        # Populate initial values (this will trigger stateChanged and set enabled states correctly)
        display_alias = current_alias
        if display_alias.startswith('{') and display_alias.endswith('}'):
            display_alias = display_alias[1:-1]
            
        if display_alias.lower().startswith('f:'):
            self.force_checkbox.setChecked(True)
            self.alias_edit.setText(display_alias[2:])
            self.prefix_label.setVisible(True)
        else:
            self.force_checkbox.setChecked(False)
            self.alias_edit.setText(display_alias)
            self.prefix_label.setVisible(False)
            
        # Run _on_force_changed initially to ensure correct disabled state of the width field
        self._on_force_changed(None)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK", self)
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)
        self._is_initializing = False
        
        QTimer.singleShot(0, self.alias_edit.setFocus)

    def showEvent(self, event):
        """Showevent."""
        super().showEvent(event)
        QTimer.singleShot(50, self.alias_edit.setFocus)
        QTimer.singleShot(100, self.alias_edit.selectAll)

    def _on_force_changed(self, state):
        """Internal helper to handle the force changed event."""
        is_checked = self.force_checkbox.isChecked()
        self.prefix_label.setVisible(is_checked)
        
        # Disable custom width when Force Alias is enabled
        self.width_label.setEnabled(not is_checked)
        self.width_edit.setEnabled(not is_checked)
        
        # Remove F: from text field if user checked the box
        text = self.alias_edit.text().strip()
        if is_checked and text.lower().startswith('f:'):
            self.alias_edit.setText(text[2:])
            
        # Show informational popup if manually checked by the user
        if is_checked and not self._is_initializing:
            if getattr(self.mw, 'show_force_alias_warning', True):
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Force Alias Enabled")
                msg_box.setText(FORCE_ALIAS_INFO)
                msg_box.setIcon(QMessageBox.Icon.Information)
                
                cb = QCheckBox("Don't show next time", msg_box)
                msg_box.setCheckBox(cb)
                
                msg_box.exec()
                
                if cb.isChecked():
                    self.mw.show_force_alias_warning = False
                    if hasattr(self.mw, 'settings_manager') and self.mw.settings_manager:
                        self.mw.settings_manager.save_settings()

    def _on_text_changed(self, text):
        # If Force Alias is enabled, prevent user from typing the 'F:' prefix manually inside the text field
        """Internal helper to handle the text changed event."""
        if self.force_checkbox.isChecked() and text.lower().startswith('f:'):
            self.alias_edit.setText(text[2:])

    def get_data(self) -> tuple[str, int | None]:
        """Get the data."""
        alias = self.alias_edit.text().strip()
        alias = alias.lstrip('{').rstrip('}')
        if alias.lower().startswith('f:'):
            alias = alias[2:]
            
        if alias:
            if self.force_checkbox.isChecked():
                alias = f"{{F:{alias}}}"
            else:
                alias = f"{{{alias}}}"
        
        width_str = self.width_edit.text().strip()
        width = int(width_str) if width_str.isdigit() else None
        return alias, width


class AliasUpdateWorker(QThread):
    """Alias update worker implementation."""
    finished_signal = pyqtSignal(object, object, object)

    def __init__(self, edited_data_copy: dict, data_copy: list, edited_file_data_copy: list, alias: str, original_tag: str):
        """Initialize a new instance."""
        super().__init__()
        self.edited_data_copy = edited_data_copy
        self.data_copy = data_copy
        self.edited_file_data_copy = edited_file_data_copy
        self.alias = alias
        self.original_tag = original_tag

    def run(self):
        # 1. Update edited_data
        """Run."""
        for key, val in list(self.edited_data_copy.items()):
            if isinstance(val, str) and self.alias in val:
                self.edited_data_copy[key] = val.replace(self.alias, self.original_tag)
                
        # 2. Update data (original read-only text)
        if self.data_copy:
            for b_idx in range(len(self.data_copy)):
                if isinstance(self.data_copy[b_idx], list):
                    for s_idx in range(len(self.data_copy[b_idx])):
                        val = self.data_copy[b_idx][s_idx]
                        if isinstance(val, str) and self.alias in val:
                            self.data_copy[b_idx][s_idx] = val.replace(self.alias, self.original_tag)
                            
        # 3. Update edited_file_data
        if self.edited_file_data_copy:
            for b_idx in range(len(self.edited_file_data_copy)):
                if isinstance(self.edited_file_data_copy[b_idx], list):
                    for s_idx in range(len(self.edited_file_data_copy[b_idx])):
                        val = self.edited_file_data_copy[b_idx][s_idx]
                        if isinstance(val, str) and self.alias in val:
                            self.edited_file_data_copy[b_idx][s_idx] = val.replace(self.alias, self.original_tag)
                            
        self.finished_signal.emit(self.edited_data_copy, self.data_copy, self.edited_file_data_copy)
