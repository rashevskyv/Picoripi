import json
import os
from pathlib import Path
from typing import Dict, Optional, List
from PyQt5.QtCore import QTimer
from utils.logging_utils import log_debug, log_info, log_error, log_warning

from core.settings.global_settings import GlobalSettings
from core.settings.plugin_settings import PluginSettings
from core.settings.font_map_loader import FontMapLoader
from core.settings.recent_projects_manager import RecentProjectsManager
from core.settings.session_state_manager import SessionStateManager

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class SettingsManager:
    def __init__(self, main_window):
        self.mw = main_window
        self.settings_file_path = "settings.json"
        self._settings = {}
        
        # Initialize specialized managers
        self.global_settings = GlobalSettings(main_window, self.settings_file_path)
        self.plugin_settings = PluginSettings(main_window)
        self.font_map_loader = FontMapLoader(main_window)
        self.recent_projects_manager = RecentProjectsManager(main_window)
        self.session_state = SessionStateManager()

    def get(self, key, default=None):
        """Get a setting value from the centralized storage."""
        return self._settings.get(key, default)

    def set(self, key, value):
        """Set a setting value in the centralized storage."""
        self._settings[key] = value
        # Update MainWindow attribute only if it's a plain attribute, not a property
        if hasattr(self.mw, key):
            cls = type(self.mw)
            attr = getattr(cls, key, None)
            if not isinstance(attr, property):
                setattr(self.mw, key, value)

    def load_settings(self):
        log_info(f"Loading settings from {self.settings_file_path}...")
        self.global_settings.load(self._settings)
        self.plugin_settings.load(self._settings)
        
        # Apply logging settings
        from utils.logging_utils import update_logger_handlers, set_enabled_log_categories, default_log_file_path
        set_enabled_log_categories(self.get('enabled_log_categories', ["general", "lifecycle", "file_ops", "settings", "ui_action", "ai", "scanner", "plugins"]))
        update_logger_handlers(
            self.get('enable_console_logging', True), 
            self.get('enable_file_logging', True),
            self.get('log_file_path', default_log_file_path)
        )
        
        self.font_map_loader.load_all_font_maps()

        self.mw.initial_load_path = getattr(self.mw, 'original_file_path', None)
        self.mw.initial_edited_load_path = getattr(self.mw, 'edited_file_path', None)
        
        if self.mw.restore_unsaved_on_startup:
            self.load_unsaved_session()

        if not self.mw.initial_load_path and not self.mw.json_path:
            log_debug("SettingsManager: No initial_load_path, ensuring UI is cleared.")
            if hasattr(self.mw, 'ui_updater'):
                self.mw.ui_updater.populate_blocks()
                self.mw.ui_updater.populate_strings_for_block(-1)

        log_info("Settings loading finished.")

    def save_settings(self):
        log_debug("Saving all settings...")
        self.global_settings.save(self._settings)
        self.plugin_settings.save()

    def load_unsaved_session(self):
        log_debug("Attempting to load unsaved session data...")
        if not Path(self.settings_file_path).exists():
            return
        
        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
            
            if settings_data.get("restore_unsaved_on_startup", False):
                session_data_str_keys = settings_data.get("unsaved_session_data")
                if session_data_str_keys and isinstance(session_data_str_keys, dict):
                    deserialized_data = {eval(k): v for k, v in session_data_str_keys.items()}
                    self.mw.edited_data = deserialized_data
                    self.mw.unsaved_changes = bool(self.mw.edited_data)
                    log_info(f"Successfully loaded {len(self.mw.edited_data)} unsaved items from session.")
                    if self.mw.unsaved_changes:
                        if hasattr(self.mw, 'helper'):
                            QTimer.singleShot(0, self.mw.helper.rebuild_unsaved_block_indices)
                        if hasattr(self.mw, 'ui_updater'):
                            QTimer.singleShot(0, self.mw.ui_updater.update_title)
                            QTimer.singleShot(0, self.mw.ui_updater.populate_blocks)
            else:
                log_debug("Restore unsaved session is disabled in settings. Skipping load.")
        except Exception as e:
            log_error(f"Error loading unsaved session data: {e}", exc_info=True)

    # Delegation methods for backward compatibility
    def load_all_font_maps(self):
        self.font_map_loader.load_all_font_maps()

    def add_recent_project(self, project_path: str, max_recent: int = 10):
        self.recent_projects_manager.add_recent_project(project_path, max_recent)

    def remove_recent_project(self, project_path: str):
        self.recent_projects_manager.remove_recent_project(project_path)

    def clear_recent_projects(self):
        self.recent_projects_manager.clear_recent_projects()

    def save_block_names(self):
        self.plugin_settings.save_block_names()

    def _update_icon_sequences_cache(self):
        self.font_map_loader.update_icon_sequences_cache()

    def _refresh_icon_highlighting(self):
        self.font_map_loader.refresh_icon_highlighting()
