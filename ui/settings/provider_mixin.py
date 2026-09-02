from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QInputDialog
from utils.logging_utils import log_debug
from core.translation.config import build_default_translation_config, merge_translation_config
from core.i18n import tr
from ui.settings.provider_worker import ProviderTestWorker


class SettingsProviderMixin:
    """Provider test, presets, and translation config UI."""

    def on_edit_prompts_clicked(self):
        """Handle the edit prompts clicked event."""
        plugin_name = self.plugin_combo.currentData()
        if not plugin_name:
            QMessageBox.warning(self, tr('Edit Prompts'), tr('Please select a plugin first.'))
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
            QMessageBox.warning(self, tr('Edit Prompts'), tr('Could not find or create prompts.json file.'))

    def on_test_provider_clicked(self):
        """Handle the test provider clicked event."""
        settings = self.get_settings()
        translation_config = settings.get('translation_config', {})
        provider_key = translation_config.get('provider', 'disabled')
        if provider_key == 'disabled':
            QMessageBox.warning(self, tr('Test Provider'), tr('Please select a provider first.'))
            return

        provider_settings = translation_config.get('providers', {}).get(provider_key, {})
        
        self.test_provider_btn.setEnabled(False)
        self.test_provider_btn.setText(tr('Testing...'))

        self.test_worker = ProviderTestWorker(provider_key, provider_settings)
        self.test_worker.finished_signal.connect(self.on_test_provider_finished)
        self.test_worker.start()

    def on_test_provider_finished(self, success, result):
        """Handle the test provider finished event."""
        self.test_provider_btn.setEnabled(True)
        self.test_provider_btn.setText(tr('Test Provider'))

        if success:
            QMessageBox.information(self, tr('Test Provider Success'), f"Connection successful!\nResponse from provider:\n\n{result}")
        else:
            QMessageBox.critical(self, tr('Test Provider Failure'), f"Connection failed!\nError:\n\n{result}")

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

        if hasattr(self, 'translation_workers_spin'):
            self.translation_workers_spin.setValue(int(self.translation_config_snapshot.get('workers', 6) or 6))

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
        if hasattr(self, 'translation_workers_spin'):
            config['workers'] = self.translation_workers_spin.value()
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
                QMessageBox.warning(self, tr('Save Preset'), tr('Cannot overwrite the Default preset.'))
                return
            
            config = self._get_translation_config_from_ui()
            self.translation_presets[name] = config
            
            self.translation_preset_combo.blockSignals(True)
            self.translation_preset_combo.clear()
            self.translation_preset_combo.addItem(tr('Default'), tr('default'))
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
            QMessageBox.warning(self, tr('Delete Preset'), tr('Cannot delete the Default preset.'))
            return
            
        reply = QMessageBox.question(self, tr('Delete Preset'), f"Are you sure you want to delete the preset '{current_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if current_data in self.translation_presets:
                del self.translation_presets[current_data]
            
            self.translation_preset_combo.blockSignals(True)
            self.translation_preset_combo.clear()
            self.translation_preset_combo.addItem(tr('Default'), tr('default'))
            for p_name in sorted(self.translation_presets.keys()):
                self.translation_preset_combo.addItem(p_name, p_name)
            self.translation_preset_combo.setCurrentIndex(0)
            self.translation_preset_combo.blockSignals(False)
            
            self._apply_translation_config_to_ui(build_default_translation_config())
