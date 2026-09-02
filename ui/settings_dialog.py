# /home/runner/work/RAG_project/RAG_project/ui/settings_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QDialogButtonBox, QWidget, QTabWidget,
)
from core.translation.config import build_default_translation_config
from .settings.settings_ui_setup import SettingsDialogUiMixin
from .settings.path_picker_mixin import SettingsPathPickerMixin
from .settings.load_save_mixin import SettingsLoadSaveMixin
from .settings.provider_mixin import SettingsProviderMixin
from .settings.provider_worker import ProviderTestWorker
from core.i18n import tr

__all__ = ["SettingsDialog", "ProviderTestWorker"]


class SettingsDialog(
    SettingsPathPickerMixin,
    SettingsLoadSaveMixin,
    SettingsProviderMixin,
    SettingsDialogUiMixin,
    QDialog,
):
    """Dialog class for settings."""
    def __init__(self, main_window):
        """Initialize a new instance."""
        super().__init__(main_window)
        self.mw = main_window
        self.setWindowTitle(tr('Settings'))
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

        self.tabs.addTab(self.general_tab, tr('Global'))
        if is_project_active:
            self.tabs.addTab(self.plugin_tab, tr('Project'))
        self.tabs.addTab(self.spelling_tab, tr('Spelling'))
        self.tabs.addTab(self.ai_translation_tab, tr('AI Translation'))
        self.tabs.addTab(self.ai_glossary_tab, tr('AI Glossary'))
        self.tabs.addTab(self.logging_tab, tr('Logging'))
        
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

