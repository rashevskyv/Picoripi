# --- START OF FILE ui/settings_dialog.py ---
# /home/runner/work/RAG_project/RAG_project/ui/settings_dialog.py
from pathlib import Path
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox,
    QDialogButtonBox, QWidget, QLabel, QTabWidget,
    QCheckBox, QLineEdit, QColorDialog, QPushButton,
    QHBoxLayout, QFileDialog, QMessageBox, QGroupBox,
    QDoubleSpinBox, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QMenu
)
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import pyqtSignal, Qt, QThread
from utils.logging_utils import log_debug
from components.labeled_spinbox import LabeledSpinBox
from components.dictionary_manager_dialog import DictionaryManagerDialog
from core.translation.config import build_default_translation_config, merge_translation_config
import pycountry

from .settings.settings_widgets import ColorPickerButton, TagDisplayWidget
from .settings.settings_ui_setup import SettingsDialogUiMixin

class ProviderTestWorker(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, provider_key: str, provider_settings: dict):
        super().__init__()
        self.provider_key = provider_key
        self.provider_settings = provider_settings

    def run(self):
        try:
            from core.translation.providers import create_translation_provider
            provider = create_translation_provider(self.provider_key, self.provider_settings)
            messages = [
                {"role": "user", "content": "Say the word \"Test\" and nothing else."}
            ]
            response = provider.translate(messages)
            if response and response.text:
                self.finished_signal.emit(True, response.text.strip())
            else:
                self.finished_signal.emit(False, "Received empty response from provider.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class SettingsDialog(QDialog, SettingsDialogUiMixin):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.setWindowTitle("Settings")
        initial_width = getattr(self.mw, 'settings_window_width', 800)
        self.setMinimumWidth(800)
        self.resize(initial_width, self.height())
        
        
        self.autofix_checkboxes = {}
        self.detection_checkboxes = {}
        self.translation_config_snapshot = build_default_translation_config()
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

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.load_initial_settings()

    def _get_lang_name(self, code):
        try:
            lang_code_part = code.split('_')[0]
            lang = pycountry.languages.get(alpha_2=lang_code_part)
            return lang.name if lang else code
        except Exception:
            return code

    def _create_path_selector(self, line_edit: QLineEdit):
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
        start_dir = line_edit.text().strip() if line_edit.text() else ""
        path = QFileDialog.getExistingDirectory(self, "Select Fonts Directory", start_dir)
        if path:
            line_edit.setText(path)

    def _on_fonts_dir_changed(self):
        self.mw.fonts_dir_path = self.fonts_path_edit.text().strip()
        selected_dir_name = self.plugin_combo.currentData()
        if selected_dir_name:
            self._populate_font_list(selected_dir_name)

    def _on_orig_fonts_dir_changed(self):
        self.mw.orig_fonts_dir_path = self.orig_fonts_path_edit.text().strip()

    def load_initial_settings(self):
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
        self.show_spaces_checkbox.setChecked(self.mw.show_multiple_spaces_as_dots)
        self.space_dot_color_picker.setColor(QColor(self.mw.space_dot_color_hex))
        self.restore_session_checkbox.setChecked(self.mw.restore_unsaved_on_startup)
        self.prompt_editor_checkbox.setChecked(getattr(self.mw, 'prompt_editor_enabled', True))
        
        self.enable_console_logging_checkbox.setChecked(getattr(self.mw, 'enable_console_logging', True))
        self.enable_file_logging_checkbox.setChecked(getattr(self.mw, 'enable_file_logging', True))
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
        self._on_dir_mode_changed(Qt.Checked if is_dir_mode else Qt.Unchecked)
        self._on_auto_generate_changed(Qt.Checked if auto_gen else Qt.Unchecked)
        
        self.preview_wrap_checkbox.setChecked(self.mw.preview_wrap_lines); self.editors_wrap_checkbox.setChecked(self.mw.editors_wrap_lines)
        self.newline_symbol_edit.setText(self.mw.newline_display_symbol)
        
        nl_color = getattr(self.mw, 'newline_color_rgba', '#A020F0'); self.newline_color_picker.setColor(QColor(nl_color))
        self.newline_bold_chk.setChecked(getattr(self.mw, 'newline_bold', True)); self.newline_italic_chk.setChecked(getattr(self.mw, 'newline_italic', False)); self.newline_underline_chk.setChecked(getattr(self.mw, 'newline_underline', False))
        
        tag_color = getattr(self.mw, 'tag_color_rgba', getattr(self.mw, 'bracket_tag_color_hex', '#FF8C00')); self.tag_color_picker.setColor(QColor(tag_color))
        self.tag_bold_chk.setChecked(getattr(self.mw, 'tag_bold', True)); self.tag_italic_chk.setChecked(getattr(self.mw, 'tag_italic', False)); self.tag_underline_chk.setChecked(getattr(self.mw, 'tag_underline', False))
        
        self.game_dialog_width_spinbox.setValue(self.mw.game_dialog_max_width_pixels); self.width_warning_spinbox.setValue(self.mw.line_width_warning_threshold_pixels)
        self.show_width_guideline_checkbox.setChecked(getattr(self.mw, 'show_width_guideline', True))
        self.lines_per_page_spinbox.setValue(getattr(self.mw, 'lines_per_page', 4))

        current_font_file = getattr(self.mw, 'default_font_file', ""); font_index = self.font_file_combo.findData(current_font_file)
        if font_index != -1: self.font_file_combo.setCurrentIndex(font_index)
        else: self.font_file_combo.setCurrentIndex(0)

        autofix_settings = getattr(self.mw, 'autofix_enabled', {}); detection_settings = getattr(self.mw, 'detection_enabled', {})
        for problem_id, checkbox in self.autofix_checkboxes.items(): checkbox.setChecked(autofix_settings.get(problem_id, False))
        for problem_id, checkbox in self.detection_checkboxes.items(): checkbox.setChecked(detection_settings.get(problem_id, True))

        self.translation_config_snapshot = merge_translation_config(build_default_translation_config(), getattr(self.mw, 'translation_config', {}))
        provider_key = self.translation_config_snapshot.get('provider', 'disabled')
        provider_index = self.translation_provider_combo.findData(provider_key)
        if provider_index != -1: self.translation_provider_combo.setCurrentIndex(provider_index)
        else: self.translation_provider_combo.setCurrentIndex(0)

        providers_cfg = self.translation_config_snapshot.get('providers', {})
        
        openai_cfg = providers_cfg.get('openai', {})
        active_openai_cfg = openai_cfg
        self.openai_api_key_edit.setText(active_openai_cfg.get('api_key', '')); self.openai_api_key_env_edit.setText(active_openai_cfg.get('api_key_env', ''))
        endpoint_val = active_openai_cfg.get('endpoint') or active_openai_cfg.get('base_url', '')
        self.openai_endpoint_edit.setText(endpoint_val); self.openai_model_edit.setText(active_openai_cfg.get('model', ''))
        try: self.openai_temperature_spin.setValue(float(active_openai_cfg.get('temperature', 0.0)))
        except (TypeError, ValueError): self.openai_temperature_spin.setValue(0.0)
        try: self.openai_max_tokens_spin.setValue(int(active_openai_cfg.get('max_output_tokens', 0) or 0))
        except (TypeError, ValueError): self.openai_max_tokens_spin.setValue(0)
        try: self.openai_timeout_spin.setValue(int(active_openai_cfg.get('timeout', 60) or 60))
        except (TypeError, ValueError): self.openai_timeout_spin.setValue(60)


        ollama_cfg = providers_cfg.get('ollama_chat', {})
        self.ollama_base_url_edit.setText(ollama_cfg.get('base_url', '')); self.ollama_model_edit.setText(ollama_cfg.get('model', ''))
        try: self.ollama_temperature_spin.setValue(float(ollama_cfg.get('temperature', 0.0)))
        except (TypeError, ValueError): self.ollama_temperature_spin.setValue(0.0)
        try: self.ollama_timeout_spin.setValue(int(ollama_cfg.get('timeout', 120) or 120))
        except (TypeError, ValueError): self.ollama_timeout_spin.setValue(120)
        self.ollama_keep_alive_edit.setText(ollama_cfg.get('keep_alive', ''))

        gemini_cfg = providers_cfg.get('gemini', {}); self.gemini_api_key_edit.setText(gemini_cfg.get('api_key', '')); self.gemini_model_edit.setText(gemini_cfg.get('model', '')); self.gemini_base_url_edit.setText(gemini_cfg.get('base_url', ''))

        perplexity_cfg = providers_cfg.get('perplexity', {})
        self.perplexity_api_key_edit.setText(perplexity_cfg.get('api_key', ''))
        self.perplexity_base_url_edit.setText(perplexity_cfg.get('base_url', ''))
        self.perplexity_model_edit.setText(perplexity_cfg.get('model', ''))
        try: self.perplexity_temperature_spin.setValue(float(perplexity_cfg.get('temperature', 0.0)))
        except (TypeError, ValueError): self.perplexity_temperature_spin.setValue(0.0)
        try: self.perplexity_max_tokens_spin.setValue(int(perplexity_cfg.get('max_output_tokens', 0) or 0))
        except (TypeError, ValueError): self.perplexity_max_tokens_spin.setValue(0)
        try: self.perplexity_timeout_spin.setValue(int(perplexity_cfg.get('timeout', 60) or 60))
        except (TypeError, ValueError): self.perplexity_timeout_spin.setValue(60)

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
        selected_dir_name = self.plugin_combo.currentData()
        
        autofix_settings = {pid: cb.isChecked() for pid, cb in self.autofix_checkboxes.items()}
        detection_settings = {pid: cb.isChecked() for pid, cb in self.detection_checkboxes.items()}

        translation_config_to_save = merge_translation_config(build_default_translation_config(), self.translation_config_snapshot)
        provider_key = self.translation_provider_combo.currentData() or 'disabled'
        translation_config_to_save['provider'] = provider_key
        providers_cfg = translation_config_to_save.setdefault('providers', {})
        
        openai_cfg = providers_cfg.setdefault('openai', {})
        openai_values = {
            'api_key': self.openai_api_key_edit.text().strip(), 'api_key_env': self.openai_api_key_env_edit.text().strip(),
            'endpoint': self.openai_endpoint_edit.text().strip(), 'base_url': self.openai_endpoint_edit.text().strip(),
            'model': self.openai_model_edit.text().strip(),
            'temperature': float(self.openai_temperature_spin.value()), 'max_output_tokens': int(self.openai_max_tokens_spin.value()),
            'timeout': int(self.openai_timeout_spin.value())
        }
        openai_cfg.update(openai_values)
        

        ollama_cfg = providers_cfg.setdefault('ollama_chat', {}); ollama_cfg.update({
            'base_url': self.ollama_base_url_edit.text().strip(), 'model': self.ollama_model_edit.text().strip(),
            'temperature': float(self.ollama_temperature_spin.value()), 'timeout': int(self.ollama_timeout_spin.value()),
            'keep_alive': self.ollama_keep_alive_edit.text().strip()
        })

        gemini_cfg = providers_cfg.setdefault('gemini', {}); gemini_cfg.update({'api_key': self.gemini_api_key_edit.text().strip(), 'model': self.gemini_model_edit.text().strip(), 'base_url': self.gemini_base_url_edit.text().strip()})
        
        perplexity_cfg = providers_cfg.setdefault('perplexity', {}); perplexity_cfg.update({
            'api_key': self.perplexity_api_key_edit.text().strip(),
            'base_url': self.perplexity_base_url_edit.text().strip(),
            'model': self.perplexity_model_edit.text().strip(),
            'temperature': float(self.perplexity_temperature_spin.value()),
            'max_output_tokens': int(self.perplexity_max_tokens_spin.value()),
            'timeout': int(self.perplexity_timeout_spin.value())
        })

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
            'font_size': self.font_size_spinbox.value(), 'show_multiple_spaces_as_dots': self.show_spaces_checkbox.isChecked(),
            'space_dot_color_hex': self.space_dot_color_picker.color().name(), 'restore_unsaved_on_startup': self.restore_session_checkbox.isChecked(),
            'prompt_editor_enabled': self.prompt_editor_checkbox.isChecked(),
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
            'autofix_enabled': autofix_settings, 'translation_config': translation_config_to_save, 'detection_enabled': detection_settings,
            'glossary_ai': glossary_ai_settings,
            'spellchecker_enabled': self.spellcheck_enabled_checkbox.isChecked(),
            'spellchecker_language': self.spellcheck_language_combo.currentData(),
            'settings_window_width': self.width(),
            'enable_console_logging': self.enable_console_logging_checkbox.isChecked(),
            'enable_file_logging': self.enable_file_logging_checkbox.isChecked(),
            'log_file_path': self.log_file_path_edit.text(),
            'enabled_log_categories': [cat_id for cat_id, chk in self.log_categories_checkboxes.items() if chk.isChecked()],
            'context_menu_tags': self._get_tags_from_tables()
        }

    def _get_tags_from_tables(self):
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
        plugin_name = self.plugin_combo.currentData()
        prompts_path = None
        if hasattr(self.mw, 'translation_handler') and hasattr(self.mw.translation_handler, 'glossary_handler'):
            prompts_path = self.mw.translation_handler.glossary_handler._prompt_manager._resolve_file("prompts.json", plugin_name)
        
        if not prompts_path:
            # Fallback if resolving failed
            from pathlib import Path
            candidates = [
                Path("plugins", plugin_name, "translation_prompts", "prompts.json") if plugin_name else None,
                Path("translation_prompts", "prompts.json")
            ]
            prompts_path = next((p for p in candidates if p and p.exists()), None)

        if prompts_path:
            from PyQt5.QtGui import QDesktopServices
            from PyQt5.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(prompts_path.resolve())))
        else:
            QMessageBox.warning(self, "Edit Prompts", "Could not find prompts.json file.")

    def on_test_provider_clicked(self):
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
        self.test_provider_btn.setEnabled(True)
        self.test_provider_btn.setText("Test Provider")

        if success:
            QMessageBox.information(self, "Test Provider Success", f"Connection successful!\nResponse from provider:\n\n{result}")
        else:
            QMessageBox.critical(self, "Test Provider Failure", f"Connection failed!\nError:\n\n{result}")
