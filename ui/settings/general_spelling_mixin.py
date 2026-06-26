from pathlib import Path
from PyQt6.QtWidgets import QFormLayout, QComboBox, QLabel, QCheckBox, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
from components.labeled_spinbox import LabeledSpinBox
from components.dictionary_manager_dialog import DictionaryManagerDialog
from .settings_widgets import ColorPickerButton
from utils.logging_utils import log_debug

class SettingsGeneralSpellingMixin:
    """Mixin class for general and spelling tabs in settings dialog."""

    def setup_general_tab(self):
        """Setup general tab."""
        layout = QFormLayout(self.general_tab)
        
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["Auto", "Light", "Dark"])
        layout.addRow(QLabel("Theme (requires restart):"), self.theme_combo)
        
        self.plugin_combo = QComboBox(self)
        self.populate_plugin_list()
        layout.addRow(QLabel("Active Game Plugin:"), self.plugin_combo)
        
        self.font_size_spinbox = LabeledSpinBox("Application Font Size:", 6, 24, 10, parent=self)
        layout.addRow(self.font_size_spinbox)
        
        self.tooltip_font_size_spinbox = LabeledSpinBox("Tooltip Font Size:", 6, 32, 11, parent=self)
        layout.addRow(self.tooltip_font_size_spinbox)
        
        self.external_script_path_edit = QLineEdit(self)
        self.external_script_path_edit.setPlaceholderText("Path to .bat, .cmd, .exe, etc.")
        self.external_script_selector = self._create_script_selector(self.external_script_path_edit)
        layout.addRow(QLabel("External Tool/Script Path:"), self.external_script_selector)
        
        self.show_spaces_checkbox = QCheckBox("Show special spaces as dots", self)
        layout.addRow(self.show_spaces_checkbox)
        
        self.space_dot_color_picker = ColorPickerButton(parent=self)
        layout.addRow("Space Dot Color:", self.space_dot_color_picker)
        
        self.restore_session_checkbox = QCheckBox("Restore unsaved session on startup", self)
        self.restore_session_checkbox.setToolTip("If unchecked, any unsaved changes will be discarded on close.")
        layout.addRow(self.restore_session_checkbox)

        self.prompt_editor_checkbox = QCheckBox("Show prompt editor before AI requests", self)
        layout.addRow(self.prompt_editor_checkbox)

        self.preview_enabled_checkbox = QCheckBox("Enable Live Preview (turn off to reduce lag)", self)
        layout.addRow(self.preview_enabled_checkbox)

        self.warnings_enabled_checkbox = QCheckBox("Enable Real-Time Warning Scan (turn off to reduce lag)", self)
        layout.addRow(self.warnings_enabled_checkbox)

        self.glossary_enabled_checkbox = QCheckBox("Enable Glossary System (turn off to reduce lag)", self)
        layout.addRow(self.glossary_enabled_checkbox)

        self.show_archive_size_warnings_checkbox = QCheckBox("Show archive size warnings", self)
        layout.addRow(self.show_archive_size_warnings_checkbox)

        self.plugin_combo.activated.connect(self.on_plugin_changed)
        self.theme_combo.activated.connect(self.on_theme_changed)

    def on_theme_changed(self, index):
        """Handle the theme changed event."""
        log_debug("SettingsDialog: Theme changed in dropdown.")
        selected_theme = self.theme_combo.currentText().lower()
        if selected_theme != self.initial_theme:
            self.theme_changed_requires_restart = True
            QMessageBox.information(self, "Theme Change", "A restart is required to apply the new theme.", QMessageBox.StandardButton.Ok)
        else:
            self.theme_changed_requires_restart = False

    def on_plugin_changed(self, index):
        """Handle the plugin changed event."""
        log_debug("SettingsDialog: Plugin changed in dropdown.")
        selected_dir_name = self.plugin_combo.currentData()
        
        self._populate_font_list(selected_dir_name)
        
        self.plugin_changed_requires_restart = True
        QMessageBox.information(self, "Plugin Change", "A restart is required to switch the game plugin.", QMessageBox.StandardButton.Ok)

    def setup_spelling_tab(self):
        """Setup spelling tab."""
        layout = QFormLayout(self.spelling_tab)
        
        self.spellcheck_enabled_checkbox = QCheckBox("Enable spell checking", self)
        layout.addRow(self.spellcheck_enabled_checkbox)
        
        self.spellcheck_language_combo = QComboBox(self)
        layout.addRow("Dictionary Language:", self.spellcheck_language_combo)
        
        manage_button = QPushButton("Manage Dictionaries...", self)
        manage_button.clicked.connect(self._open_dictionary_manager)
        layout.addRow(manage_button)
        
        self.populate_spellchecker_languages()

    def _open_dictionary_manager(self):
        """Internal helper to open dictionary manager."""
        dialog = DictionaryManagerDialog(self)
        dialog.exec()
        self.populate_spellchecker_languages()

    def populate_spellchecker_languages(self):
        """Populate spellchecker languages."""
        current_lang_data = self.spellcheck_language_combo.currentData()
        self.spellcheck_language_combo.clear()
        if self.mw and self.mw.spellchecker_manager:
            available_dicts = self.mw.spellchecker_manager.scan_local_dictionaries()
            for lang_code in sorted(available_dicts.keys()):
                display_name = self._get_lang_name(lang_code)
                self.spellcheck_language_combo.addItem(f"{display_name} ({lang_code})", lang_code)
        
        if current_lang_data:
            index = self.spellcheck_language_combo.findData(current_lang_data)
            if index != -1:
                self.spellcheck_language_combo.setCurrentIndex(index)
