from pathlib import Path
from PyQt6.QtWidgets import QFormLayout, QCheckBox, QLineEdit, QLabel
from PyQt6.QtCore import Qt
from core.i18n import tr


class PluginPathsMixin:
    """File paths subtab for plugin settings."""

    def _setup_paths_subtab(self, tab):
        """Internal helper to setup paths subtab."""
        layout = QFormLayout(tab)
        
        self.dir_mode_checkbox = QCheckBox(tr('Directory Mode (Load from folder)'), tab)
        self.auto_generate_checkbox = QCheckBox(tr('Auto-generate translation path'), tab)
        
        layout.addRow(self.dir_mode_checkbox)
        layout.addRow(self.auto_generate_checkbox)
        
        self.original_path_edit = QLineEdit(tab)
        self.original_path_edit.setObjectName("PathLineEdit")
        self.edited_path_edit = QLineEdit(tab)
        self.edited_path_edit.setObjectName("PathLineEdit")

        self.orig_label_widget = QLabel(tr('Original File Path:'))
        self.changes_label_widget = QLabel(tr('Changes File Path:'))

        self.original_path_selector = self._create_path_selector(self.original_path_edit)
        self.edited_path_selector = self._create_path_selector(self.edited_path_edit)
        layout.addRow(self.orig_label_widget, self.original_path_selector)
        layout.addRow(self.changes_label_widget, self.edited_path_selector)

        # Original Fonts Directory Path Selection
        self.orig_fonts_path_edit = QLineEdit(tab)
        self.orig_fonts_path_edit.setObjectName("PathLineEdit")
        self.orig_fonts_path_edit.setPlaceholderText(tr('Optional path to original fonts folder'))
        self.orig_fonts_path_selector = self._create_dir_selector(self.orig_fonts_path_edit)
        layout.addRow(QLabel(tr('Original Fonts Directory Path (original font):')), self.orig_fonts_path_selector)

        # Fonts Directory Path Selection
        self.fonts_path_edit = QLineEdit(tab)
        self.fonts_path_edit.setObjectName("PathLineEdit")
        self.fonts_path_edit.setPlaceholderText(tr('Optional path to fonts folder'))
        self.fonts_path_selector = self._create_dir_selector(self.fonts_path_edit)
        layout.addRow(QLabel(tr('Fonts Directory Path (translated font):')), self.fonts_path_selector)

        # Signals
        self.dir_mode_checkbox.stateChanged.connect(self._on_dir_mode_changed)
        self.auto_generate_checkbox.stateChanged.connect(self._on_auto_generate_changed)
        self.original_path_edit.textChanged.connect(self._update_auto_changes_path)
        self.fonts_path_edit.textChanged.connect(self._on_fonts_dir_changed)
        self.orig_fonts_path_edit.textChanged.connect(self._on_orig_fonts_dir_changed)

    def _on_dir_mode_changed(self, state):
        """Internal helper to handle the dir mode changed event."""
        is_dir = (state == Qt.CheckState.Checked)
        if is_dir:
            self.orig_label_widget.setText(tr('Original Directory Path:'))
            self.changes_label_widget.setText(tr('Changes Directory Path:'))
        else:
            self.orig_label_widget.setText(tr('Original File Path:'))
            self.changes_label_widget.setText(tr('Changes File Path:'))
        self._update_auto_changes_path()

    def _on_auto_generate_changed(self, state):
        """Internal helper to handle the auto generate changed event."""
        is_auto = (state == Qt.CheckState.Checked)
        if hasattr(self, 'edited_path_selector'):
            self.edited_path_selector.setEnabled(not is_auto)
        else:
            self.edited_path_edit.setEnabled(not is_auto)
        self._update_auto_changes_path()

    def _update_auto_changes_path(self):
        """Internal helper to update the auto changes path."""
        if not hasattr(self, 'auto_generate_checkbox') or not self.auto_generate_checkbox.isChecked():
            return
        
        orig_path = self.original_path_edit.text().strip()
        if not orig_path:
            self.edited_path_edit.setText("")
            return

        is_dir = self.dir_mode_checkbox.isChecked()
        try:
            path_obj = Path(orig_path)
            if is_dir:
                parent = path_obj.parent
                name = path_obj.name
                if name:
                    new_path = (parent / f"{name}_translation").as_posix()
                else:
                    new_path = f"{orig_path}_translation"
            else:
                parent = path_obj.parent
                stem = path_obj.stem
                suffix = path_obj.suffix
                new_path = (parent / f"{stem}_translation{suffix}").as_posix()
                
            self.edited_path_edit.setText(new_path)
        except Exception:
            self.edited_path_edit.setText(f"{orig_path}_translation")
