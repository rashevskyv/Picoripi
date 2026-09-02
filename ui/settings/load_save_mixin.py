from pathlib import Path
import json
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox
from utils.logging_utils import log_debug
from core.glossary_build.parallel import DEFAULT_RETRY_DELAY, DEFAULT_WORKERS
from core.translation.config import build_default_translation_config, merge_translation_config
import pycountry
from core.i18n import tr


class SettingsLoadSaveMixin:
    """Load/save settings, tags tables, accept/reject/close."""

    def _get_lang_name(self, code):
        """Internal helper to get the lang name."""
        try:
            lang_code_part = code.split('_')[0]
            lang = pycountry.languages.get(alpha_2=lang_code_part)
            return lang.name if lang else code
        except Exception:
            return code


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
        self.auto_sleep_idle_delay_spinbox.setValue(max(1, getattr(self.mw, 'auto_sleep_idle_delay_seconds', 300) // 60))
        
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
        self.translation_preset_combo.addItem(tr('Default'), tr('default'))
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
        self.glossary_workers_spin.setValue(int(glossary_ai_cfg.get('workers', DEFAULT_WORKERS) or DEFAULT_WORKERS))
        self.glossary_retry_delay_spin.setValue(int(glossary_ai_cfg.get('retry_delay', DEFAULT_RETRY_DELAY)))
        
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
            'chunk_size': self.glossary_chunk_size_spin.value(),
            'workers': self.glossary_workers_spin.value(),
            'retry_delay': self.glossary_retry_delay_spin.value()
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
            'auto_sleep_idle_delay_seconds': self.auto_sleep_idle_delay_spinbox.value() * 60,
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


    def accept(self):
        """Validate and persist plugin-specific files only when OK is pressed."""
        if (getattr(self.mw, "active_game_plugin", None) == "zelda_bmg"
                and self.plugin_combo.currentData() == "zelda_bmg"):
            success, error = self.persist_zelda_bmg_window_rules()
            if not success:
                QMessageBox.warning(self, tr('Invalid Window Layout'), error)
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
