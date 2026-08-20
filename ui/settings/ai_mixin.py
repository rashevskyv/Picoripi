from PyQt6.QtWidgets import (
    QVBoxLayout, QFormLayout, QLineEdit, QHBoxLayout, QComboBox, 
    QPushButton, QGroupBox, QDoubleSpinBox, QSpinBox, QStackedWidget,
    QCheckBox, QWidget
)
from PyQt6.QtCore import Qt

class SettingsAiMixin:
    """Mixin class for AI Translation and AI Glossary tabs in settings dialog."""

    def on_provider_changed(self, index):
        """Handle the provider changed event."""
        provider_key = self.translation_provider_combo.itemData(index)
        page_index = self.provider_page_map.get(provider_key, 0)
        self.ai_provider_pages.setCurrentIndex(page_index)
        if hasattr(self, 'test_provider_btn'):
            self.test_provider_btn.setEnabled(provider_key != 'disabled')

    def setup_ai_translation_tab(self):
        """Setup ai translation tab."""
        layout = QVBoxLayout(self.ai_translation_tab)
        provider_form = QFormLayout()
        
        self.target_language_edit = QLineEdit(self)
        self.target_language_edit.setPlaceholderText("e.g. Ukrainian, Spanish, German")
        provider_form.addRow("Target Language:", self.target_language_edit)

        provider_layout = QHBoxLayout()
        self.translation_provider_combo = QComboBox(self)
        self.translation_provider_combo.addItem("Disabled", "disabled")
        self.translation_provider_combo.addItem("OpenAI Compatible", "openai")
        self.translation_provider_combo.addItem("Ollama Chat", "ollama_chat")
        self.translation_provider_combo.addItem("Gemini", "gemini")
        self.translation_provider_combo.addItem("Perplexity", "perplexity")
        provider_layout.addWidget(self.translation_provider_combo)

        self.test_provider_btn = QPushButton("Test Provider", self)
        self.test_provider_btn.setEnabled(False)
        provider_layout.addWidget(self.test_provider_btn)

        provider_form.addRow("Active Provider:", provider_layout)

        preset_layout = QHBoxLayout()
        self.translation_preset_combo = QComboBox(self)
        preset_layout.addWidget(self.translation_preset_combo)

        self.save_preset_btn = QPushButton("Save Preset", self)
        self.delete_preset_btn = QPushButton("Delete Preset", self)
        preset_layout.addWidget(self.save_preset_btn)
        preset_layout.addWidget(self.delete_preset_btn)

        provider_form.addRow("Preset:", preset_layout)

        self.translation_workers_spin = QSpinBox(self)
        self.translation_workers_spin.setRange(1, 16)
        self.translation_workers_spin.setValue(6)
        self.translation_workers_spin.setToolTip(
            "<b>Parallel Requests</b><br>"
            "Number of concurrent translation requests sent during batch/chunked translation.<br>"
            "Proxies with multi-account rotation (e.g. Gemini Web2API) process requests in parallel.<br>"
            "Set to 1 for standard sequential translation."
        )
        provider_form.addRow("Parallel Requests:", self.translation_workers_spin)

        layout.addLayout(provider_form)

        self.ai_provider_pages = QStackedWidget(self)
        layout.addWidget(self.ai_provider_pages)

        disabled_page = QWidget()
        self.ai_provider_pages.addWidget(disabled_page)

        openai_group = QGroupBox("OpenAI Compatible", self.ai_translation_tab)
        openai_layout = QFormLayout(openai_group)
        self.openai_api_key_edit = QLineEdit(self)
        self.openai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_api_key_edit.setPlaceholderText("Bearer token")
        openai_layout.addRow("API Key:", self.openai_api_key_edit)
        self.openai_api_key_env_edit = QLineEdit(self)
        self.openai_api_key_env_edit.setPlaceholderText("OPENAI_API_KEY")
        openai_layout.addRow("API Key Env Var:", self.openai_api_key_env_edit)
        self.openai_endpoint_edit = QLineEdit(self)
        self.openai_endpoint_edit.setPlaceholderText("https://api.openai.com/v1 or http://127.0.0.1:8081/v1")
        openai_layout.addRow("Endpoint:", self.openai_endpoint_edit)
        self.openai_model_edit = QLineEdit(self)
        self.openai_model_edit.setPlaceholderText("gpt-4o-mini or gemini-3.7-flash")
        openai_layout.addRow("Model:", self.openai_model_edit)
        self.openai_temperature_spin = QDoubleSpinBox(self)
        self.openai_temperature_spin.setRange(0.0, 2.0); self.openai_temperature_spin.setDecimals(2); self.openai_temperature_spin.setSingleStep(0.05); self.openai_temperature_spin.setValue(0.0)
        openai_layout.addRow("Temperature:", self.openai_temperature_spin)
        self.openai_max_tokens_spin = QSpinBox(self)
        self.openai_max_tokens_spin.setRange(0, 200000); self.openai_max_tokens_spin.setSingleStep(100); self.openai_max_tokens_spin.setSpecialValueText("Provider default"); self.openai_max_tokens_spin.setValue(0)
        openai_layout.addRow("Max Output Tokens:", self.openai_max_tokens_spin)
        self.openai_timeout_spin = QSpinBox(self)
        self.openai_timeout_spin.setRange(1, 600); self.openai_timeout_spin.setSuffix(" s"); self.openai_timeout_spin.setValue(60)
        openai_layout.addRow("Request Timeout:", self.openai_timeout_spin)
        self.ai_provider_pages.addWidget(openai_group)

        ollama_group = QGroupBox("Ollama Chat API", self.ai_translation_tab)
        ollama_layout = QFormLayout(ollama_group)
        self.ollama_base_url_edit = QLineEdit(self); self.ollama_base_url_edit.setPlaceholderText("http://localhost:11434"); ollama_layout.addRow("Base URL:", self.ollama_base_url_edit)
        self.ollama_model_edit = QLineEdit(self); self.ollama_model_edit.setPlaceholderText("llama3"); ollama_layout.addRow("Model:", self.ollama_model_edit)
        self.ollama_temperature_spin = QDoubleSpinBox(self); self.ollama_temperature_spin.setRange(0.0, 2.0); self.ollama_temperature_spin.setDecimals(2); self.ollama_temperature_spin.setSingleStep(0.05); self.ollama_temperature_spin.setValue(0.0); ollama_layout.addRow("Temperature:", self.ollama_temperature_spin)
        self.ollama_timeout_spin = QSpinBox(self); self.ollama_timeout_spin.setRange(1, 600); self.ollama_timeout_spin.setSuffix(" s"); self.ollama_timeout_spin.setValue(120); ollama_layout.addRow("Request Timeout:", self.ollama_timeout_spin)
        self.ollama_keep_alive_edit = QLineEdit(self); self.ollama_keep_alive_edit.setPlaceholderText("e.g. 5m or leave blank"); ollama_layout.addRow("Keep Alive:", self.ollama_keep_alive_edit)
        self.ai_provider_pages.addWidget(ollama_group)

        gemini_group = QGroupBox("Google Gemini API", self.ai_translation_tab)
        gemini_layout = QFormLayout(gemini_group)
        self.gemini_base_url_edit = QLineEdit(self)
        self.gemini_base_url_edit.setPlaceholderText("http://127.0.0.1:8081/v1 (or leave empty for Google API)")
        gemini_layout.addRow("Base URL (optional):", self.gemini_base_url_edit)
        self.gemini_api_key_edit = QLineEdit(self); self.gemini_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password); self.gemini_api_key_edit.setPlaceholderText("Gemini API Key (optional for local proxy)"); gemini_layout.addRow("API Key:", self.gemini_api_key_edit)
        self.gemini_model_edit = QLineEdit(self); self.gemini_model_edit.setPlaceholderText("gemini-3.7-flash"); gemini_layout.addRow("Model:", self.gemini_model_edit)
        self.ai_provider_pages.addWidget(gemini_group)

        perplexity_group = QGroupBox("Perplexity API", self.ai_translation_tab)
        perplexity_layout = QFormLayout(perplexity_group)
        self.perplexity_api_key_edit = QLineEdit(self)
        self.perplexity_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.perplexity_api_key_edit.setPlaceholderText("Bearer token")
        perplexity_layout.addRow("API Key:", self.perplexity_api_key_edit)
        self.perplexity_base_url_edit = QLineEdit(self)
        self.perplexity_base_url_edit.setPlaceholderText("https://api.perplexity.ai")
        perplexity_layout.addRow("Base URL:", self.perplexity_base_url_edit)
        self.perplexity_model_edit = QLineEdit(self)
        self.perplexity_model_edit.setPlaceholderText("sonar-medium-8x7b-chat")
        perplexity_layout.addRow("Model:", self.perplexity_model_edit)
        self.perplexity_temperature_spin = QDoubleSpinBox(self)
        self.perplexity_temperature_spin.setRange(0.0, 2.0); self.perplexity_temperature_spin.setDecimals(2); self.perplexity_temperature_spin.setSingleStep(0.05); self.perplexity_temperature_spin.setValue(0.0)
        perplexity_layout.addRow("Temperature:", self.perplexity_temperature_spin)
        self.perplexity_max_tokens_spin = QSpinBox(self)
        self.perplexity_max_tokens_spin.setRange(0, 200000); self.perplexity_max_tokens_spin.setSingleStep(100); self.perplexity_max_tokens_spin.setSpecialValueText("Provider default"); self.perplexity_max_tokens_spin.setValue(0)
        perplexity_layout.addRow("Max Output Tokens:", self.perplexity_max_tokens_spin)
        self.perplexity_timeout_spin = QSpinBox(self)
        self.perplexity_timeout_spin.setRange(1, 600); self.perplexity_timeout_spin.setSuffix(" s"); self.perplexity_timeout_spin.setValue(60)
        perplexity_layout.addRow("Request Timeout:", self.perplexity_timeout_spin)
        self.ai_provider_pages.addWidget(perplexity_group)

        self.translation_provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        self.openai_api_key_edit.textChanged.connect(self._refresh_glossary_api_key_from_translation)
        self.openai_api_key_env_edit.textChanged.connect(self._refresh_glossary_api_key_from_translation)
        self.gemini_api_key_edit.textChanged.connect(self._refresh_glossary_api_key_from_translation)
        
        self.edit_prompts_btn = QPushButton("Edit Prompts JSON", self)
        layout.addWidget(self.edit_prompts_btn)
        layout.addStretch(1)

    def setup_ai_glossary_tab(self):
        """Setup ai glossary tab."""
        layout = QFormLayout(self.ai_glossary_tab)

        self.glossary_provider_combo = QComboBox(self)
        self.glossary_provider_combo.addItems(["OpenAI Compatible", "Ollama", "Gemini"])
        layout.addRow("Provider:", self.glossary_provider_combo)

        self.glossary_api_key_edit = QLineEdit(self)
        self.glossary_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.glossary_api_key_edit.setPlaceholderText("Provider API Key")
        layout.addRow("API Key:", self.glossary_api_key_edit)

        self.glossary_use_translation_key_checkbox = QCheckBox("Use API key from AI Translation", self)
        layout.addRow("", self.glossary_use_translation_key_checkbox)

        self.glossary_model_edit = QLineEdit(self)
        self.glossary_model_edit.setPlaceholderText("e.g., gpt-4o-mini")
        layout.addRow("Model:", self.glossary_model_edit)

        self.glossary_chunk_size_spin = QSpinBox(self)
        self.glossary_chunk_size_spin.setRange(1000, 32000)
        self.glossary_chunk_size_spin.setSingleStep(100)
        self.glossary_chunk_size_spin.setSuffix(" chars")
        layout.addRow("Text Chunk Size:", self.glossary_chunk_size_spin)

        self.glossary_workers_spin = QSpinBox(self)
        self.glossary_workers_spin.setRange(1, 16)
        self.glossary_workers_spin.setToolTip(
            "How many glossary requests run at once. A proxy that rotates several "
            "accounts serves them in parallel; going wider than the number of "
            "accounts only queues the extra threads on an account's cooldown. "
            "1 means the old one-at-a-time build."
        )
        layout.addRow("Parallel Requests:", self.glossary_workers_spin)

        self.glossary_retry_delay_spin = QSpinBox(self)
        self.glossary_retry_delay_spin.setRange(0, 600)
        self.glossary_retry_delay_spin.setSuffix(" s")
        self.glossary_retry_delay_spin.setToolTip(
            "How long to wait before retrying the entries that failed. When the "
            "server sends a Retry-After, that wins over this."
        )
        layout.addRow("Retry Delay:", self.glossary_retry_delay_spin)

        self.glossary_use_translation_key_checkbox.stateChanged.connect(self._on_glossary_use_translation_key_changed)
        self.glossary_provider_combo.currentIndexChanged.connect(self._on_glossary_provider_changed)
        self.glossary_api_key_edit.textChanged.connect(self._on_glossary_api_key_changed)

    def _set_glossary_api_key_text(self, value: str) -> None:
        """Internal helper to set the glossary api key text."""
        self._glossary_updating_api_key = True
        try:
            self.glossary_api_key_edit.setText(value or "")
        finally:
            self._glossary_updating_api_key = False

    def _get_translation_credentials_for_glossary(self, provider_name: str) -> dict:
        """Internal helper to get the translation credentials for glossary."""
        providers_cfg = {}
        if isinstance(self.translation_config_snapshot, dict):
            providers_cfg = self.translation_config_snapshot.get('providers', {}) or {}

        if provider_name in ('OpenAI', 'OpenAI Compatible'):
            api_key = self.openai_api_key_edit.text().strip()
            if not api_key:
                api_key = providers_cfg.get('openai', {}).get('api_key', '')

            api_key_env = self.openai_api_key_env_edit.text().strip()
            if not api_key_env:
                api_key_env = providers_cfg.get('openai', {}).get('api_key_env', '')

            return {
                'api_key': api_key,
                'api_key_env': api_key_env
            }

        if provider_name == 'Gemini':
            api_key = self.gemini_api_key_edit.text().strip()
            api_key_env = ''
            gemini_cfg = providers_cfg.get('gemini', {}) or {}
            if not api_key:
                api_key = gemini_cfg.get('api_key', '')
            api_key_env = gemini_cfg.get('api_key_env', '')
            return {
                'api_key': api_key,
                'api_key_env': api_key_env
            }

        return {}

    def _update_glossary_api_key_controls(self, provider_name: str = None) -> None:
        """Internal helper to update the glossary api key controls."""
        provider = provider_name or self.glossary_provider_combo.currentText()
        use_translation = self.glossary_use_translation_key_checkbox.isChecked()
        self.glossary_api_key_edit.setEnabled(not use_translation)

        if use_translation:
            credentials = self._get_translation_credentials_for_glossary(provider)
            self._set_glossary_api_key_text(credentials.get('api_key') or '')
        else:
            manual_value = self._glossary_manual_api_keys.get(provider, '')
            self._set_glossary_api_key_text(manual_value)

    def _refresh_glossary_api_key_from_translation(self, *args):
        """Internal helper to update the glossary api key from translation."""
        if not self.glossary_use_translation_key_checkbox.isChecked():
            return
        provider = self.glossary_provider_combo.currentText()
        if provider in ("OpenAI", "OpenAI Compatible", "Gemini"):
            self._update_glossary_api_key_controls(provider)

    def _on_glossary_use_translation_key_changed(self, state):
        """Internal helper to handle the glossary use translation key changed event."""
        provider = self.glossary_provider_combo.currentText()
        if state == Qt.CheckState.Checked:
            self._glossary_manual_api_keys[provider] = self.glossary_api_key_edit.text().strip()
        self._update_glossary_api_key_controls(provider)

    def _on_glossary_provider_changed(self, index):
        """Internal helper to handle the glossary provider changed event."""
        provider = self.glossary_provider_combo.itemText(index)
        if not provider:
            provider = self.glossary_provider_combo.currentText()
        self._update_glossary_api_key_controls(provider)

    def _on_glossary_api_key_changed(self, text):
        """Internal helper to handle the glossary api key changed event."""
        if self._glossary_updating_api_key:
            return
        if self.glossary_use_translation_key_checkbox.isChecked():
            return
        provider = self.glossary_provider_combo.currentText()
        self._glossary_manual_api_keys[provider] = text.strip()
