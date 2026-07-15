# /home/runner/work/RAG_project/RAG_project/ui/settings_dialog.py
from pathlib import Path
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QDialogButtonBox, QWidget, QLabel, QTabWidget,
    QCheckBox, QLineEdit, QColorDialog, QPushButton,
    QHBoxLayout, QFileDialog, QMessageBox, QGroupBox,
    QDoubleSpinBox, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QMenu, QInputDialog
)
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from utils.logging_utils import log_debug
from components.labeled_spinbox import LabeledSpinBox
from components.dictionary_manager_dialog import DictionaryManagerDialog
from core.translation.config import build_default_translation_config, merge_translation_config
import pycountry

from .settings.settings_widgets import ColorPickerButton, TagDisplayWidget
from .settings.settings_ui_setup import SettingsDialogUiMixin

class ProviderTestWorker(QThread):
    """Provider test worker implementation."""
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, provider_key: str, provider_settings: dict):
        """Initialize a new instance."""
        super().__init__()
        self.provider_key = provider_key
        self.provider_settings = provider_settings
        self._is_cancelled = False

    def cancel(self):
        """Request cancellation."""
        self._is_cancelled = True

    def run(self):
        """Run."""
        try:
            from core.translation.providers import create_translation_provider
            provider = create_translation_provider(self.provider_key, self.provider_settings)
            messages = [
                {"role": "user", "content": "Say the word \"Test\" and nothing else."}
            ]
            if self._is_cancelled:
                return
            response = provider.translate(messages)
            if self._is_cancelled:
                return
            if response and response.text:
                self.finished_signal.emit(True, response.text.strip())
            else:
                self.finished_signal.emit(False, "Received empty response from provider.")
        except Exception as e:
            if self._is_cancelled:
                return
            self.finished_signal.emit(False, str(e))

class SettingsDialog(QDialog, SettingsDialogUiMixin):
    """Dialog class for settings."""
    def __init__(self, main_window):
        """Initialize a new instance."""
        super().__init__(main_window)
        self.mw = main_window
        self.setWindowTitle("Settings")
        initial_width = getattr(self.mw, 'settings_window_width', 800)
        self.setMinimumWidth(800)
        self.resize(initial_width, self.height())
        
        
        self.autofix_checkboxes = {}
        self.detection_checkboxes = {}
        self.translation_config_snapshot = build_default_translation_config()
        self.test_worker = None
        self.plugin_changed_requires_restart = False
        self.theme_changed_requires_restart = False
        self.initial_plugin_name = self.mw.active_game_plugin
        self.initial_theme = getattr(self.mw, 'theme', 'auto')
        self.rules_changed_requires_rescan = False

        self._glossary_manual_api_keys = {}
        self._glossary_updating_api_key = False

        self.provider_page_map = {
            "disabled": 0,
            "openai": 1,
            "ollama_chat": 2,
            "gemini": 3,
            "perplexity": 4
        }

        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget(self)
        main_layout.addWidget(self.tabs)
        
        self.general_tab = QWidget()
        self.plugin_tab = QWidget()
        self.spelling_tab = QWidget()
        self.ai_translation_tab = QWidget()
        self.ai_glossary_tab = QWidget()
        self.logging_tab = QWidget()

        is_project_active = hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project is not None

        self.tabs.addTab(self.general_tab, "Global")
        if is_project_active:
            self.tabs.addTab(self.plugin_tab, "Project")
        self.tabs.addTab(self.spelling_tab, "Spelling")
        self.tabs.addTab(self.ai_translation_tab, "AI Translation")
        self.tabs.addTab(self.ai_glossary_tab, "AI Glossary")
        self.tabs.addTab(self.logging_tab, "Logging")
        
        self.setup_general_tab()
        self.setup_plugin_tab()
        self.setup_spelling_tab()
        self.setup_ai_translation_tab()
        self.setup_ai_glossary_tab()
        self.setup_logging_tab()

        self.edit_prompts_btn.clicked.connect(self.on_edit_prompts_clicked)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.load_initial_settings()

    def _get_lang_name(self, code):
        """Internal helper to get the lang name."""
        try:
            lang_code_part = code.split('_')[0]
            lang = pycountry.languages.get(alpha_2=lang_code_part)
            return lang.name if lang else code
        except Exception:
            return code

    def _create_script_selector(self, line_edit: QLineEdit):
        """Internal helper to create script selector."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(line_edit)
        
        browse_button = QPushButton("...")
        browse_button.setFixedSize(24, 24)
        browse_button.clicked.connect(lambda: self._browse_for_script(line_edit))
        layout.addWidget(browse_button)
        
        return widget

    def _browse_for_script(self, line_edit: QLineEdit):
        """Internal helper to browse for script."""
        start_dir = line_edit.text().strip() if line_edit.text() else ""
        if start_dir:
            try:
                start_dir = str(Path(start_dir).parent.as_posix())
            except Exception:
                start_dir = ""
        
        filter_str = "Scripts/Executables (*.bat *.cmd *.exe *.py *.sh);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select External Script/Tool", start_dir, filter_str)
        if path:
            line_edit.setText(path)

    def _create_path_selector(self, line_edit: QLineEdit):
        """Internal helper to create path selector."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        
        layout.addWidget(line_edit)
        
        browse_button = QPushButton("...")
        browse_button.setFixedSize(24, 24)
        browse_button.clicked.connect(lambda: self._browse_for_file(line_edit))
        layout.addWidget(browse_button)
        
        return widget

    def _browse_for_file(self, line_edit: QLineEdit):
        """Internal helper to browse for file."""
        is_dir_mode = self.dir_mode_checkbox.isChecked()

        start_dir = line_edit.text() if line_edit.text() else ""
        if not is_dir_mode and start_dir:
            try:
                start_dir = str(Path(start_dir).parent.as_posix())
            except Exception:
                start_dir = ""

        if is_dir_mode:
            path = QFileDialog.getExistingDirectory(self, "Select Directory", start_dir)
        else:
            filter_str = "Supported Files (*.json *.arc *.rarc *.bfn *.bmg);;JSON Files (*.json);;Archive Files (*.arc *.rarc);;Font Files (*.bfn);;BMG Files (*.bmg);;All Files (*)"
            path, _ = QFileDialog.getOpenFileName(self, "Select File", start_dir, filter_str)

        if path:
            line_edit.setText(path)

    def _create_dir_selector(self, line_edit: QLineEdit):
        """Internal helper to create dir selector."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        
        layout.addWidget(line_edit)
        
        browse_button = QPushButton("...")
        browse_button.setFixedSize(24, 24)
        browse_button.clicked.connect(lambda: self._browse_for_directory(line_edit))
        layout.addWidget(browse_button)
        
        return widget

    def _browse_for_directory(self, line_edit: QLineEdit):
        """Internal helper to browse for directory."""
        start_dir = line_edit.text().strip() if line_edit.text() else ""
        path = QFileDialog.getExistingDirectory(self, "Select Fonts Directory", start_dir)
        if path:
            line_edit.setText(path)

    def _on_fonts_dir_changed(self):
        """Internal helper to handle the fonts dir changed event."""
        self.mw.fonts_dir_path = self.fonts_path_edit.text().strip()
        selected_dir_name = self.plugin_combo.currentData()
        if selected_dir_name:
            self._populate_font_list(selected_dir_name)

    def _on_orig_fonts_dir_changed(self):
        """Internal helper to handle the orig fonts dir changed event."""
        self.mw.orig_fonts_dir_path = self.orig_fonts_path_edit.text().strip()

    def load_initial_settings(self):
        """Load initial settings."""
        current_theme = getattr(self.mw, 'theme', 'auto')
        if current_theme == 'dark': self.theme_combo.setCurrentIndex(2)
        elif current_theme == 'light': self.theme_combo.setCurrentIndex(1)
        else: self.theme_combo.setCurrentIndex(0)
            
        current_plugin_dir_name = getattr(self.mw, 'active_game_plugin', 'zelda_mc')
        idx = self.plugin_combo.findData(current_plugin_dir_name)
        if idx != -1:
            self.plugin_combo.blockSignals(True)
            self.plugin_combo.setCurrentIndex(idx)
            self.plugin_combo.blockSignals(False)
        
        self._populate_font_list(current_plugin_dir_name)
        
        self.font_size_spinbox.setValue(self.mw.current_font_size)
        self.tooltip_font_size_spinbox.setValue(getattr(self.mw, 'tooltip_font_size', 11))
        self.external_script_path_edit.setText(getattr(self.mw, 'external_script_path', ""))
        self.show_spaces_checkbox.setChecked(self.mw.show_multiple_spaces_as_dots)
        self.space_dot_color_picker.setColor(QColor(self.mw.space_dot_color_hex))
        self.restore_session_checkbox.setChecked(self.mw.restore_unsaved_on_startup)
        self.prompt_editor_checkbox.setChecked(getattr(self.mw, 'prompt_editor_enabled', True))
        self.preview_enabled_checkbox.setChecked(getattr(self.mw, 'preview_enabled', True))
        self.warnings_enabled_checkbox.setChecked(getattr(self.mw, 'warnings_enabled', True))
        self.glossary_enabled_checkbox.setChecked(getattr(self.mw, 'glossary_enabled', True))
        self.show_archive_size_warnings_checkbox.setChecked(getattr(self.mw, 'show_archive_size_warnings', True))
        
        self.enable_console_logging_checkbox.setChecked(getattr(self.mw, 'enable_console_logging', True))
        self.enable_file_logging_checkbox.setChecked(getattr(self.mw, 'enable_file_logging', True))
        self.log_ai_traffic_checkbox.setChecked(getattr(self.mw, 'log_ai_traffic', False))
        self.log_file_path_edit.setText(getattr(self.mw, 'log_file_path', ""))
        
        enabled_cats = getattr(self.mw, 'enabled_log_categories', ["general", "lifecycle", "file_ops", "settings", "ui_action", "ai", "scanner", "plugins"])
        for cat_id, chk in self.log_categories_checkboxes.items():
            chk.setChecked(cat_id in enabled_cats)
        
        is_project_active = hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project is not None
        
        is_dir_mode = False
        auto_gen = False
        if is_project_active:
            proj = self.mw.project_manager.project
            is_dir_mode = proj.metadata.get('is_directory_mode', False)
            auto_gen = proj.metadata.get('auto_generate_translation_path', False)
            self.original_path_edit.setText(proj.metadata.get('source_path', ''))
            self.edited_path_edit.setText(proj.metadata.get('translation_path', ''))
            self.fonts_path_edit.setText(getattr(self.mw, 'fonts_dir_path', ""))
            self.orig_fonts_path_edit.setText(getattr(self.mw, 'orig_fonts_dir_path', ""))
            
            # Enable controls
            self.dir_mode_checkbox.setEnabled(True)
            self.auto_generate_checkbox.setEnabled(True)
            if hasattr(self, 'original_path_selector'): self.original_path_selector.setEnabled(True)
            if hasattr(self, 'edited_path_selector'): self.edited_path_selector.setEnabled(not auto_gen)
            if hasattr(self, 'fonts_path_selector'): self.fonts_path_selector.setEnabled(True)
            if hasattr(self, 'orig_fonts_path_selector'): self.orig_fonts_path_selector.setEnabled(True)
        else:
            is_dir_mode = getattr(self.mw, 'is_directory_mode', False)
            auto_gen = getattr(self.mw, 'auto_generate_translation_path', False)
            self.original_path_edit.setText("")
            self.edited_path_edit.setText("")
            self.fonts_path_edit.setText("")
            self.orig_fonts_path_edit.setText("")
            
            # Disable controls
            self.dir_mode_checkbox.setEnabled(False)
            self.auto_generate_checkbox.setEnabled(False)
            if hasattr(self, 'original_path_selector'): self.original_path_selector.setEnabled(False)
            if hasattr(self, 'edited_path_selector'): self.edited_path_selector.setEnabled(False)
            if hasattr(self, 'fonts_path_selector'): self.fonts_path_selector.setEnabled(False)
            if hasattr(self, 'orig_fonts_path_selector'): self.orig_fonts_path_selector.setEnabled(False)
            
        self.dir_mode_checkbox.setChecked(is_dir_mode)
        self.auto_generate_checkbox.setChecked(auto_gen)
        self._on_dir_mode_changed(Qt.CheckState.Checked if is_dir_mode else Qt.CheckState.Unchecked)
        self._on_auto_generate_changed(Qt.CheckState.Checked if auto_gen else Qt.CheckState.Unchecked)
        
        self.preview_wrap_checkbox.setChecked(self.mw.preview_wrap_lines); self.editors_wrap_checkbox.setChecked(self.mw.editors_wrap_lines)
        self.newline_symbol_edit.setText(self.mw.newline_display_symbol)
        
        nl_color = getattr(self.mw, 'newline_color_rgba', '#A020F0'); self.newline_color_picker.setColor(QColor(nl_color))
        self.newline_bold_chk.setChecked(getattr(self.mw, 'newline_bold', True)); self.newline_italic_chk.setChecked(getattr(self.mw, 'newline_italic', False)); self.newline_underline_chk.setChecked(getattr(self.mw, 'newline_underline', False))
        
        tag_color = getattr(self.mw, 'tag_color_rgba', getattr(self.mw, 'bracket_tag_color_hex', '#FF8C00')); self.tag_color_picker.setColor(QColor(tag_color))
        self.tag_bold_chk.setChecked(getattr(self.mw, 'tag_bold', True)); self.tag_italic_chk.setChecked(getattr(self.mw, 'tag_italic', False)); self.tag_underline_chk.setChecked(getattr(self.mw, 'tag_underline', False))
        
        self.game_dialog_width_spinbox.setValue(self.mw.game_dialog_max_width_pixels); self.width_warning_spinbox.setValue(self.mw.line_width_warning_threshold_pixels)
        self.show_width_guideline_checkbox.setChecked(getattr(self.mw, 'show_width_guideline', True))
        self.lines_per_page_spinbox.setValue(getattr(self.mw, 'lines_per_page', 4))
        if hasattr(self, 'use_per_window_layouts_checkbox'):
            self.use_per_window_layouts_checkbox.setChecked(
                getattr(self.mw, 'use_per_window_layouts', True)
            )

        current_font_file = getattr(self.mw, 'default_font_file', ""); font_index = self.font_file_combo.findData(current_font_file)
        if font_index != -1: self.font_file_combo.setCurrentIndex(font_index)
        else: self.font_file_combo.setCurrentIndex(0)

        autofix_settings = getattr(self.mw, 'autofix_enabled', {}); detection_settings = getattr(self.mw, 'detection_enabled', {})
        for problem_id, checkbox in self.autofix_checkboxes.items(): checkbox.setChecked(autofix_settings.get(problem_id, False))
        for problem_id, checkbox in self.detection_checkboxes.items(): checkbox.setChecked(detection_settings.get(problem_id, True))
        
        align_sentences = getattr(self.mw, 'align_sentences_to_original_pages', False)
        if hasattr(self, 'align_sentences_checkbox'):
            self.align_sentences_checkbox.setChecked(align_sentences)

        prevent_empty_lines = getattr(self.mw, 'prevent_empty_lines_in_autofix', False)
        if hasattr(self, 'prevent_empty_lines_checkbox'):
            self.prevent_empty_lines_checkbox.setChecked(prevent_empty_lines)

        self.translation_presets = getattr(self.mw, 'translation_presets', {}).copy()
        current_preset = getattr(self.mw, 'current_translation_preset', 'default')

        self.translation_preset_combo.blockSignals(True)
        self.translation_preset_combo.clear()
        self.translation_preset_combo.addItem("Default", "default")
        for p_name in sorted(self.translation_presets.keys()):
            self.translation_preset_combo.addItem(p_name, p_name)

        idx = self.translation_preset_combo.findData(current_preset)
        if idx != -1:
            self.translation_preset_combo.setCurrentIndex(idx)
        else:
            self.translation_preset_combo.setCurrentIndex(0)
        self.translation_preset_combo.blockSignals(False)

        self.translation_preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        self.save_preset_btn.clicked.connect(self.on_save_preset_clicked)
        self.delete_preset_btn.clicked.connect(self.on_delete_preset_clicked)

        self.translation_config_snapshot = merge_translation_config(build_default_translation_config(), getattr(self.mw, 'translation_config', {}))
        self._apply_translation_config_to_ui(self.translation_config_snapshot)
        self.target_language_edit.setText(getattr(self.mw, 'target_language', 'Ukrainian'))

        # Load AI Glossary settings
        glossary_ai_cfg = getattr(self.mw, 'glossary_ai', {})
        glossary_provider = glossary_ai_cfg.get('provider', 'OpenAI')
        if glossary_provider == 'OpenAI':
            glossary_provider = 'OpenAI Compatible'
        provider_index = self.glossary_provider_combo.findText(glossary_provider)
        if provider_index >= 0:
            self.glossary_provider_combo.blockSignals(True)
            self.glossary_provider_combo.setCurrentIndex(provider_index)
            self.glossary_provider_combo.blockSignals(False)
        else:
            self.glossary_provider_combo.setCurrentText(glossary_provider)

        manual_key = glossary_ai_cfg.get('api_key', '')
        self._glossary_manual_api_keys[glossary_provider] = manual_key
        self._glossary_manual_api_keys['OpenAI'] = manual_key
        self._glossary_manual_api_keys['OpenAI Compatible'] = manual_key

        use_translation_key = glossary_ai_cfg.get('use_translation_api_key', False)
        self.glossary_use_translation_key_checkbox.blockSignals(True)
        self.glossary_use_translation_key_checkbox.setChecked(use_translation_key)
        self.glossary_use_translation_key_checkbox.blockSignals(False)

        self._update_glossary_api_key_controls(glossary_provider)

        self.glossary_model_edit.setText(glossary_ai_cfg.get('model', 'gpt-4o'))
        self.glossary_chunk_size_spin.setValue(glossary_ai_cfg.get('chunk_size', 8000))
        
        # Load Spellchecker settings
        self.spellcheck_enabled_checkbox.setChecked(getattr(self.mw, 'spellchecker_enabled', False))
        current_lang = getattr(self.mw, 'spellchecker_language', 'uk')
        lang_index = self.spellcheck_language_combo.findData(current_lang)
        if lang_index != -1:
            self.spellcheck_language_combo.setCurrentIndex(lang_index)

        # Load Context Menu Tags
        tags_data = getattr(self.mw, 'context_menu_tags', {"single_tags": [], "wrap_tags": []})
        
        single_tags = tags_data.get("single_tags", [])
        self.single_tags_table.setRowCount(0)
        for t in single_tags:
            self._add_table_row(self.single_tags_table, t.get("display", ""), t.get("tag", ""))
            
        wrap_tags = tags_data.get("wrap_tags", [])
        self.wrap_tags_table.setRowCount(0)
        for t in wrap_tags:
            self._add_table_row(self.wrap_tags_table, t.get("display", ""), t.get("open", ""), t.get("close", ""))

        self.single_tags_table.setSortingEnabled(True)
        self.wrap_tags_table.setSortingEnabled(True)

        self.on_provider_changed(self.translation_provider_combo.currentIndex())
        self.test_provider_btn.clicked.connect(self.on_test_provider_clicked)
        self.rules_changed_requires_rescan = False


    def get_settings(self) -> dict:
        """Get the settings."""
        selected_dir_name = self.plugin_combo.currentData()
        
        # Read Tag Aliases from table if table exists
        aliases_dict = {}
        if hasattr(self, "aliases_table"):
            for r in range(self.aliases_table.rowCount()):
                item_alias = self.aliases_table.item(r, 0)
                item_tag = self.aliases_table.item(r, 1)
                alias_val = item_alias.text().strip() if item_alias else ""
                tag_val = item_tag.text().strip() if item_tag else ""
                if alias_val and tag_val:
                    aliases_dict[alias_val] = tag_val
        else:
            aliases_dict = getattr(self.mw, "default_tag_mappings", {})

        # Read and Save Font Map to file if table exists
        if hasattr(self, "font_map_table"):
            new_font_map = {}
            for r in range(self.font_map_table.rowCount()):
                item_char = self.font_map_table.item(r, 0)
                item_width = self.font_map_table.item(r, 1)
                char_val = item_char.text() if item_char else ""
                width_val = item_width.text().strip() if item_width else ""
                if char_val and width_val:
                    try:
                        new_font_map[char_val] = {"width": int(width_val)}
                    except ValueError:
                        pass
            
            # Save to active plugin's font_map.json
            if selected_dir_name:
                font_map_path = Path("plugins") / selected_dir_name / "font_map.json"
                try:
                    font_map_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(font_map_path, 'w', encoding='utf-8') as f:
                        json.dump(new_font_map, f, indent=4, ensure_ascii=False)
                    self.mw.current_font_map = new_font_map
                    self.rules_changed_requires_rescan = True
                except Exception as e:
                    log_debug(f"SettingsDialog: Failed to save font_map.json: {e}")
        
        autofix_settings = {pid: cb.isChecked() for pid, cb in self.autofix_checkboxes.items()}
        detection_settings = {pid: cb.isChecked() for pid, cb in self.detection_checkboxes.items()}

        translation_config_to_save = self._get_translation_config_from_ui()
        self.translation_config_snapshot = translation_config_to_save

        glossary_provider = self.glossary_provider_combo.currentText()
        use_translation_key = self.glossary_use_translation_key_checkbox.isChecked()
        manual_key = self._glossary_manual_api_keys.get(glossary_provider, '')
        if not use_translation_key:
            manual_key = self.glossary_api_key_edit.text().strip()

        glossary_ai_settings = {
            'provider': glossary_provider,
            'api_key': manual_key or '',
            'use_translation_api_key': use_translation_key,
            'model': self.glossary_model_edit.text().strip(),
            'chunk_size': self.glossary_chunk_size_spin.value()
        }

        is_project_active = hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project is not None
        return {
            'theme': self.theme_combo.currentText().lower(), 'active_game_plugin': selected_dir_name,
            'font_size': self.font_size_spinbox.value(),
            'tooltip_font_size': self.tooltip_font_size_spinbox.value(),
            'external_script_path': self.external_script_path_edit.text().strip(),
            'show_multiple_spaces_as_dots': self.show_spaces_checkbox.isChecked(),
            'space_dot_color_hex': self.space_dot_color_picker.color().name(), 'restore_unsaved_on_startup': self.restore_session_checkbox.isChecked(),
            'prompt_editor_enabled': self.prompt_editor_checkbox.isChecked(),
            'preview_enabled': self.preview_enabled_checkbox.isChecked(),
            'warnings_enabled': self.warnings_enabled_checkbox.isChecked(),
            'glossary_enabled': self.glossary_enabled_checkbox.isChecked(),
            'show_archive_size_warnings': self.show_archive_size_warnings_checkbox.isChecked(),
            'original_file_path': self.original_path_edit.text() if is_project_active else getattr(self.mw, 'original_file_path', ''),
            'edited_file_path': self.edited_path_edit.text() if is_project_active else getattr(self.mw, 'edited_file_path', ''),
            'is_directory_mode': self.dir_mode_checkbox.isChecked() if is_project_active else getattr(self.mw, 'is_directory_mode', False),
            'auto_generate_translation_path': self.auto_generate_checkbox.isChecked() if is_project_active else getattr(self.mw, 'auto_generate_translation_path', False),
            'fonts_dir_path': self.fonts_path_edit.text().strip() if is_project_active else getattr(self.mw, 'fonts_dir_path', ''),
            'orig_fonts_dir_path': self.orig_fonts_path_edit.text().strip() if is_project_active else getattr(self.mw, 'orig_fonts_dir_path', ''),
            'default_font_file': self.font_file_combo.currentData(), 'preview_wrap_lines': self.preview_wrap_checkbox.isChecked(),
            'editors_wrap_lines': self.editors_wrap_checkbox.isChecked(), 'newline_display_symbol': self.newline_symbol_edit.text(),
            'newline_color_rgba': self.newline_color_picker.color().name(QColor.HexArgb) if hasattr(QColor, 'HexArgb') else self.newline_color_picker.color().name(),
            'newline_bold': self.newline_bold_chk.isChecked(), 'newline_italic': self.newline_italic_chk.isChecked(), 'newline_underline': self.newline_underline_chk.isChecked(),
            'tag_color_rgba': self.tag_color_picker.color().name(QColor.HexArgb) if hasattr(QColor, 'HexArgb') else self.tag_color_picker.color().name(),
            'tag_bold': self.tag_bold_chk.isChecked(), 'tag_italic': self.tag_italic_chk.isChecked(), 'tag_underline': self.tag_underline_chk.isChecked(),
            'game_dialog_max_width_pixels': self.game_dialog_width_spinbox.value(), 'line_width_warning_threshold_pixels': self.width_warning_spinbox.value(),
            'show_width_guideline': self.show_width_guideline_checkbox.isChecked(),
            'lines_per_page': self.lines_per_page_spinbox.value(),
            'use_per_window_layouts': (
                self.use_per_window_layouts_checkbox.isChecked()
                if hasattr(self, 'use_per_window_layouts_checkbox')
                else getattr(self.mw, 'use_per_window_layouts', True)
            ),
            'autofix_enabled': autofix_settings,
            'align_sentences_to_original_pages': self.align_sentences_checkbox.isChecked() if hasattr(self, 'align_sentences_checkbox') else False,
            'prevent_empty_lines_in_autofix': self.prevent_empty_lines_checkbox.isChecked() if hasattr(self, 'prevent_empty_lines_checkbox') else False,
            'translation_config': translation_config_to_save,
            'translation_presets': self.translation_presets,
            'target_language': self.target_language_edit.text().strip() or 'Ukrainian',
            'current_translation_preset': self.translation_preset_combo.currentData(),
            'detection_enabled': detection_settings,
            'glossary_ai': glossary_ai_settings,
            'spellchecker_enabled': self.spellcheck_enabled_checkbox.isChecked(),
            'spellchecker_language': self.spellcheck_language_combo.currentData(),
            'settings_window_width': self.width(),
            'enable_console_logging': self.enable_console_logging_checkbox.isChecked(),
            'enable_file_logging': self.enable_file_logging_checkbox.isChecked(),
            'log_ai_traffic': self.log_ai_traffic_checkbox.isChecked(),
            'log_file_path': self.log_file_path_edit.text(),
            'enabled_log_categories': [cat_id for cat_id, chk in self.log_categories_checkboxes.items() if chk.isChecked()],
            'context_menu_tags': self._get_tags_from_tables(),
            'default_tag_mappings': aliases_dict
        }

    def _get_tags_from_tables(self):
        """Internal helper to get the tags from tables."""
        single_tags = []
        for r in range(self.single_tags_table.rowCount()):
            widget = self.single_tags_table.cellWidget(r, 0)
            disp = widget.text() if widget else ""
            item1 = self.single_tags_table.item(r, 1)
            tag = item1.text().strip() if item1 else ""
            if disp or tag:
                single_tags.append({"display": disp, "tag": tag})
                
        wrap_tags = []
        for r in range(self.wrap_tags_table.rowCount()):
            widget = self.wrap_tags_table.cellWidget(r, 0)
            disp = widget.text() if widget else ""
            item1 = self.wrap_tags_table.item(r, 1)
            ot = item1.text().strip() if item1 else ""
            item2 = self.wrap_tags_table.item(r, 2)
            ct = item2.text().strip() if item2 else ""
            if disp or ot or ct:
                wrap_tags.append({"display": disp, "open": ot, "close": ct})
                
        return {"single_tags": single_tags, "wrap_tags": wrap_tags}

    def on_edit_prompts_clicked(self):
        """Handle the edit prompts clicked event."""
        plugin_name = self.plugin_combo.currentData()
        if not plugin_name:
            QMessageBox.warning(self, "Edit Prompts", "Please select a plugin first.")
            return

        plugin_prompts_path = Path("plugins", plugin_name, "translation_prompts", "prompts.json")
        
        # If local prompts.json doesn't exist, materialize it on-demand
        if not plugin_prompts_path.exists():
            fallback_path = None
            if hasattr(self.mw, 'translation_handler') and hasattr(self.mw.translation_handler, 'glossary_handler'):
                fallback_path = self.mw.translation_handler.glossary_handler._prompt_manager._resolve_file("prompts.json", plugin_name)
            
            if not fallback_path:
                candidates = [
                    Path("plugins", "common", "defaults", "prompts.json"),
                    Path("translation_prompts", "prompts.json")
                ]
                fallback_path = next((p for p in candidates if p and p.exists()), None)
            
            if fallback_path and fallback_path.exists():
                try:
                    plugin_prompts_path.parent.mkdir(parents=True, exist_ok=True)
                    import shutil
                    shutil.copy2(fallback_path, plugin_prompts_path)
                    log_debug(f"Materialized local prompts.json for plugin '{plugin_name}' from {fallback_path}")
                except Exception as e:
                    log_debug(f"Failed to materialize local prompts.json: {e}")
        
        if plugin_prompts_path.exists():
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(plugin_prompts_path.resolve())))
        else:
            QMessageBox.warning(self, "Edit Prompts", "Could not find or create prompts.json file.")

    def on_test_provider_clicked(self):
        """Handle the test provider clicked event."""
        settings = self.get_settings()
        translation_config = settings.get('translation_config', {})
        provider_key = translation_config.get('provider', 'disabled')
        if provider_key == 'disabled':
            QMessageBox.warning(self, "Test Provider", "Please select a provider first.")
            return

        provider_settings = translation_config.get('providers', {}).get(provider_key, {})
        
        self.test_provider_btn.setEnabled(False)
        self.test_provider_btn.setText("Testing...")

        self.test_worker = ProviderTestWorker(provider_key, provider_settings)
        self.test_worker.finished_signal.connect(self.on_test_provider_finished)
        self.test_worker.start()

    def on_test_provider_finished(self, success, result):
        """Handle the test provider finished event."""
        self.test_provider_btn.setEnabled(True)
        self.test_provider_btn.setText("Test Provider")

        if success:
            QMessageBox.information(self, "Test Provider Success", f"Connection successful!\nResponse from provider:\n\n{result}")
        else:
            QMessageBox.critical(self, "Test Provider Failure", f"Connection failed!\nError:\n\n{result}")

    def _apply_translation_config_to_ui(self, config: dict):
        """Internal helper to apply translation config to ui."""
        self.translation_config_snapshot = merge_translation_config(build_default_translation_config(), config)
        provider_key = self.translation_config_snapshot.get('provider', 'disabled')
        provider_index = self.translation_provider_combo.findData(provider_key)
        
        self.translation_provider_combo.blockSignals(True)
        if provider_index != -1:
            self.translation_provider_combo.setCurrentIndex(provider_index)
        else:
            self.translation_provider_combo.setCurrentIndex(0)
        self.translation_provider_combo.blockSignals(False)
        self.on_provider_changed(self.translation_provider_combo.currentIndex())

        providers_cfg = self.translation_config_snapshot.get('providers', {})
        
        openai_cfg = providers_cfg.get('openai', {})
        self.openai_api_key_edit.setText(openai_cfg.get('api_key', ''))
        self.openai_api_key_env_edit.setText(openai_cfg.get('api_key_env', ''))
        endpoint_val = openai_cfg.get('endpoint') or openai_cfg.get('base_url', '')
        self.openai_endpoint_edit.setText(endpoint_val)
        self.openai_model_edit.setText(openai_cfg.get('model', ''))
        try:
            self.openai_temperature_spin.setValue(float(openai_cfg.get('temperature', 0.0)))
        except (TypeError, ValueError):
            self.openai_temperature_spin.setValue(0.0)
        try:
            self.openai_max_tokens_spin.setValue(int(openai_cfg.get('max_output_tokens', 0) or 0))
        except (TypeError, ValueError):
            self.openai_max_tokens_spin.setValue(0)
        try:
            self.openai_timeout_spin.setValue(int(openai_cfg.get('timeout', 60) or 60))
        except (TypeError, ValueError):
            self.openai_timeout_spin.setValue(60)

        ollama_cfg = providers_cfg.get('ollama_chat', {})
        self.ollama_base_url_edit.setText(ollama_cfg.get('base_url', ''))
        self.ollama_model_edit.setText(ollama_cfg.get('model', ''))
        try:
            self.ollama_temperature_spin.setValue(float(ollama_cfg.get('temperature', 0.0)))
        except (TypeError, ValueError):
            self.ollama_temperature_spin.setValue(0.0)
        try:
            self.ollama_timeout_spin.setValue(int(ollama_cfg.get('timeout', 120) or 120))
        except (TypeError, ValueError):
            self.ollama_timeout_spin.setValue(120)
        self.ollama_keep_alive_edit.setText(ollama_cfg.get('keep_alive', ''))

        gemini_cfg = providers_cfg.get('gemini', {})
        self.gemini_api_key_edit.setText(gemini_cfg.get('api_key', ''))
        self.gemini_model_edit.setText(gemini_cfg.get('model', ''))
        self.gemini_base_url_edit.setText(gemini_cfg.get('base_url', ''))

        perplexity_cfg = providers_cfg.get('perplexity', {})
        self.perplexity_api_key_edit.setText(perplexity_cfg.get('api_key', ''))
        self.perplexity_base_url_edit.setText(perplexity_cfg.get('base_url', ''))
        self.perplexity_model_edit.setText(perplexity_cfg.get('model', ''))
        try:
            self.perplexity_temperature_spin.setValue(float(perplexity_cfg.get('temperature', 0.0)))
        except (TypeError, ValueError):
            self.perplexity_temperature_spin.setValue(0.0)
        try:
            self.perplexity_max_tokens_spin.setValue(int(perplexity_cfg.get('max_output_tokens', 0) or 0))
        except (TypeError, ValueError):
            self.perplexity_max_tokens_spin.setValue(0)
        try:
            self.perplexity_timeout_spin.setValue(int(perplexity_cfg.get('timeout', 60) or 60))
        except (TypeError, ValueError):
            self.perplexity_timeout_spin.setValue(60)

    def _get_translation_config_from_ui(self) -> dict:
        """Internal helper to get the translation config from ui."""
        config = merge_translation_config(build_default_translation_config(), self.translation_config_snapshot)
        provider_key = self.translation_provider_combo.currentData() or 'disabled'
        config['provider'] = provider_key
        providers_cfg = config.setdefault('providers', {})
        
        openai_cfg = providers_cfg.setdefault('openai', {})
        openai_cfg.update({
            'api_key': self.openai_api_key_edit.text().strip(),
            'api_key_env': self.openai_api_key_env_edit.text().strip(),
            'endpoint': self.openai_endpoint_edit.text().strip(),
            'base_url': self.openai_endpoint_edit.text().strip(),
            'model': self.openai_model_edit.text().strip(),
            'temperature': float(self.openai_temperature_spin.value()),
            'max_output_tokens': int(self.openai_max_tokens_spin.value()),
            'timeout': int(self.openai_timeout_spin.value())
        })
        
        ollama_cfg = providers_cfg.setdefault('ollama_chat', {})
        ollama_cfg.update({
            'base_url': self.ollama_base_url_edit.text().strip(),
            'model': self.ollama_model_edit.text().strip(),
            'temperature': float(self.ollama_temperature_spin.value()),
            'timeout': int(self.ollama_timeout_spin.value()),
            'keep_alive': self.ollama_keep_alive_edit.text().strip()
        })

        gemini_cfg = providers_cfg.setdefault('gemini', {})
        gemini_cfg.update({
            'api_key': self.gemini_api_key_edit.text().strip(),
            'model': self.gemini_model_edit.text().strip(),
            'base_url': self.gemini_base_url_edit.text().strip()
        })
        
        perplexity_cfg = providers_cfg.setdefault('perplexity', {})
        perplexity_cfg.update({
            'api_key': self.perplexity_api_key_edit.text().strip(),
            'base_url': self.perplexity_base_url_edit.text().strip(),
            'model': self.perplexity_model_edit.text().strip(),
            'temperature': float(self.perplexity_temperature_spin.value()),
            'max_output_tokens': int(self.perplexity_max_tokens_spin.value()),
            'timeout': int(self.perplexity_timeout_spin.value())
        })
        return config

    def on_preset_changed(self, index):
        """Handle the preset changed event."""
        preset_name = self.translation_preset_combo.itemData(index)
        if not preset_name:
            return
        
        if preset_name == "default":
            config = build_default_translation_config()
        else:
            config = self.translation_presets.get(preset_name)
            if not config:
                return
        
        self._apply_translation_config_to_ui(config)

    def on_save_preset_clicked(self):
        """Handle the save preset clicked event."""
        current_name = self.translation_preset_combo.currentText()
        if current_name == "Default":
            current_name = ""
            
        name, ok = QInputDialog.getText(self, "Save Preset", "Enter preset name:", text=current_name)
        if ok and name.strip():
            name = name.strip()
            if name == "Default":
                QMessageBox.warning(self, "Save Preset", "Cannot overwrite the Default preset.")
                return
            
            config = self._get_translation_config_from_ui()
            self.translation_presets[name] = config
            
            self.translation_preset_combo.blockSignals(True)
            self.translation_preset_combo.clear()
            self.translation_preset_combo.addItem("Default", "default")
            for p_name in sorted(self.translation_presets.keys()):
                self.translation_preset_combo.addItem(p_name, p_name)
            
            idx = self.translation_preset_combo.findText(name)
            if idx != -1:
                self.translation_preset_combo.setCurrentIndex(idx)
            self.translation_preset_combo.blockSignals(False)

    def on_delete_preset_clicked(self):
        """Handle the delete preset clicked event."""
        current_name = self.translation_preset_combo.currentText()
        current_data = self.translation_preset_combo.currentData()
        if current_data == "default":
            QMessageBox.warning(self, "Delete Preset", "Cannot delete the Default preset.")
            return
            
        reply = QMessageBox.question(self, "Delete Preset", f"Are you sure you want to delete the preset '{current_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if current_data in self.translation_presets:
                del self.translation_presets[current_data]
            
            self.translation_preset_combo.blockSignals(True)
            self.translation_preset_combo.clear()
            self.translation_preset_combo.addItem("Default", "default")
            for p_name in sorted(self.translation_presets.keys()):
                self.translation_preset_combo.addItem(p_name, p_name)
            self.translation_preset_combo.setCurrentIndex(0)
            self.translation_preset_combo.blockSignals(False)
            
            self._apply_translation_config_to_ui(build_default_translation_config())

    def accept(self):
        """Validate and persist plugin-specific files only when OK is pressed."""
        if (getattr(self.mw, "active_game_plugin", None) == "zelda_bmg"
                and self.plugin_combo.currentData() == "zelda_bmg"):
            success, error = self.persist_zelda_bmg_window_rules()
            if not success:
                QMessageBox.warning(self, "Invalid Window Layout", error)
                return
        super().accept()

    def reject(self):
        """Safely clean up worker thread on rejection/closure."""
        if self.test_worker:
            from utils.thread_utils import safe_shutdown_thread
            safe_shutdown_thread(self.test_worker, self.test_worker)
            self.test_worker = None
        super().reject()

    def closeEvent(self, event):
        """Handle dialog close event."""
        self.reject()
        event.accept()
