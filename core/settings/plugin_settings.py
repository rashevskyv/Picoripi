import json
import os
from pathlib import Path
from typing import Dict, Optional, List, Any, Union
from utils.logging_utils import log_debug, log_info, log_error, log_warning
from utils.constants import (
    DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
    DEFAULT_LINE_WIDTH_WARNING_THRESHOLD
)
from core.translation.config import build_default_translation_config, merge_translation_config

class PluginSettings:
    def __init__(self, main_window: Any):
        self.mw = main_window

    def _get_plugin_config_path(self) -> Optional[Path]:
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        if not plugin_name:
            return None
        return Path("plugins") / plugin_name / "config.json"

    def _get_project_settings_path(self) -> Optional[Path]:
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project_dir:
            return Path(self.mw.project_manager.project_dir) / "project_settings.json"
        return None

    def _substitute_env_vars(self, data: Any) -> Any:
        """Recursively substitute environment variables in data structure."""
        import re
        if isinstance(data, dict):
            return {key: self._substitute_env_vars(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            def replace_env_var(match: re.Match) -> str:
                var_name = match.group(1) or match.group(2)
                return os.getenv(var_name, match.group(0))
            pattern = r'\$\{([^}]+)\}|\$([A-Z_][A-Z0-9_]*)'
            return re.sub(pattern, replace_env_var, data)
        return data

    def load(self, settings_dict: Dict[str, Any]) -> None:
        """Loads plugin-specific settings."""
        defaults = {
            "display_name": "Unknown Plugin", "default_tag_mappings": {}, "block_names": {}, "block_color_markers": {},
            "string_metadata": {}, "default_font_file": "", "fonts_dir_path": "", "orig_fonts_dir_path": "",
            "newline_display_symbol": "↵", "newline_css": "color: #A020F0; font-weight: bold;",
            "tag_css": "color: #808080; font-style: italic;",
            "bracket_tag_color_hex": "#FF8C00",
            "preview_wrap_lines": True, "editors_wrap_lines": False,
            "game_dialog_max_width_pixels": DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
            "line_width_warning_threshold_pixels": DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
            "lines_per_page": 4,
            "original_file_path": None, "edited_file_path": None,
            "is_directory_mode": False, "auto_generate_translation_path": False,
            "last_selected_block_index": -1, "last_selected_string_index": -1,
            "last_cursor_position_in_edited": 0, "last_edited_text_edit_scroll_value_v": 0,
            "last_edited_text_edit_scroll_value_h": 0, "last_preview_text_edit_scroll_value_v": 0,
            "last_original_text_edit_scroll_value_v": 0, "last_original_text_edit_scroll_value_h": 0,
            "search_history": [],
            "translation_config": build_default_translation_config(),
            "autofix_enabled": {},
            "detection_enabled": {},
            "align_sentences_to_original_pages": False,
            "prevent_empty_lines_in_autofix": False,
            "context_menu_tags": {"single_tags": [], "wrap_tags": []}
        }
        for key, value in defaults.items():
            if key == "translation_config":
                if key not in settings_dict:
                    settings_dict[key] = value
                if not hasattr(self.mw, key) or not getattr(self.mw, key, None):
                    if not isinstance(getattr(type(self.mw), key, None), property):
                        setattr(self.mw, key, value)
            else:
                settings_dict[key] = value
                if key not in ["block_names", "block_color_markers", "default_tag_mappings", "string_metadata"]:
                    if not isinstance(getattr(type(self.mw), key, None), property):
                        setattr(self.mw, key, value)
        
        # Ensure new style fields exist on MainWindow
        for field, default in [
            ('tag_color_rgba', "#FF8C00"), ('tag_bold', True), ('tag_italic', False), ('tag_underline', False),
            ('newline_color_rgba', "#A020F0"), ('newline_bold', True), ('newline_italic', False), ('newline_underline', False)
        ]:
            if not hasattr(self.mw, field): setattr(self.mw, field, default)
        
        if hasattr(self.mw, 'data_store') and not hasattr(self.mw.data_store, 'block_names'): self.mw.data_store.block_names = {}
        if not hasattr(self.mw, 'block_color_markers'): self.mw.block_color_markers = {}
        if not hasattr(self.mw, 'default_tag_mappings'): self.mw.default_tag_mappings = {}
        if not hasattr(self.mw, 'string_metadata'): self.mw.string_metadata = {}
        if not hasattr(self.mw, 'context_menu_tags'): self.mw.context_menu_tags = {"single_tags": [], "wrap_tags": []}
        self.mw.search_history_to_save = []

        plugin_config_path = self._get_plugin_config_path()
        plugin_data = {}
        if plugin_config_path and plugin_config_path.exists():
            try:
                with plugin_config_path.open('r', encoding='utf-8') as f:
                    plugin_data = json.load(f)
                plugin_data = self._substitute_env_vars(plugin_data)
                log_debug(f"Plugin default config loaded from '{plugin_config_path}'.")
            except Exception as e:
                log_error(f"Error loading plugin default config from '{plugin_config_path}': {e}", exc_info=True)

        project_settings_path = self._get_project_settings_path()
        project_data = {}
        if project_settings_path and project_settings_path.exists():
            try:
                with project_settings_path.open('r', encoding='utf-8') as f:
                    project_data = json.load(f)
                project_data = self._substitute_env_vars(project_data)
                log_info(f"Project settings loaded from '{project_settings_path}'.")
            except Exception as e:
                log_error(f"Error loading project settings from '{project_settings_path}': {e}", exc_info=True)

        combined_data = {}
        combined_data.update(plugin_data)
        combined_data.update(project_data)

        if not combined_data:
            log_warning("No plugin defaults or project settings found. Using defaults.")
            return

        try:
            self.mw.data_store.block_names.update({str(k): v for k, v in combined_data.get("block_names", {}).items()})
            self.mw.block_color_markers.update({k: set(v) for k, v in combined_data.get("block_color_markers", {}).items()})
            self.mw.default_tag_mappings.update(combined_data.get("default_tag_mappings", {}))
            
            try:
                self.mw.string_metadata = {eval(k): v for k, v in combined_data.get("string_metadata", {}).items()}
            except Exception as e:
                log_error(f"Error deserializing string_metadata keys: {e}. Metadata will be empty.", exc_info=True)
                self.mw.string_metadata = {}
            
            for key, value in combined_data.items():
                if key in ["block_names", "block_color_markers", "default_tag_mappings", "string_metadata", "translation_config"]:
                    continue
                settings_dict[key] = value
                if hasattr(self.mw, key) and not isinstance(getattr(type(self.mw), key, None), property):
                    setattr(self.mw, key, value)

            # Legacy migration logic
            self._migrate_legacy_styles(combined_data)
            
            self.mw.search_history_to_save = combined_data.get("search_history", [])
            
            # Get plugin defaults
            plugin_defaults_autofix = {}
            plugin_defaults_detection = {}
            plugin_name = getattr(self.mw, 'active_game_plugin', None)
            if plugin_name:
                try:
                    import importlib
                    config_module = importlib.import_module(f"plugins.{plugin_name}.config")
                    plugin_defaults_autofix = getattr(config_module, 'DEFAULT_AUTOFIX_SETTINGS', {})
                    plugin_defaults_detection = getattr(config_module, 'DEFAULT_DETECTION_SETTINGS', {})
                except Exception as e:
                    log_debug(f"Could not load config defaults for plugin {plugin_name}: {e}")

            loaded_autofix = combined_data.get("autofix_enabled", {})
            loaded_detection = combined_data.get("detection_enabled", {})

            # Start with plugin defaults and overlay loaded values
            merged_autofix = plugin_defaults_autofix.copy()
            merged_autofix.update(loaded_autofix)

            merged_detection = plugin_defaults_detection.copy()
            merged_detection.update(loaded_detection)

            self.mw.autofix_enabled = merged_autofix
            self.mw.detection_enabled = merged_detection

            if "translation_config" in project_data and project_data["translation_config"]:
                loaded_translation = project_data["translation_config"]
                if isinstance(loaded_translation, dict):
                    self.mw.translation_config = merge_translation_config(build_default_translation_config(), loaded_translation)
                else:
                    self.mw.translation_config = build_default_translation_config()
            elif not hasattr(self.mw, "translation_config") or not self.mw.translation_config:
                self.mw.translation_config = build_default_translation_config()

            log_debug("Merged settings loaded successfully.")
        except Exception as e:
            log_error(f"Error applying merged settings: {e}", exc_info=True)

    def _migrate_legacy_styles(self, plugin_data: Dict[str, Any]) -> None:
        # Implementation of style migration from SettingsManager
        if not hasattr(self.mw, 'tag_color_rgba') or not getattr(self.mw, 'tag_color_rgba', None):
            self.mw.tag_color_rgba = plugin_data.get('bracket_tag_color_hex') or '#FF8C00'
        if not hasattr(self.mw, 'tag_bold'): self.mw.tag_bold = True
        legacy_tag_css = plugin_data.get('tag_css', '')
        if not hasattr(self.mw, 'tag_italic'): self.mw.tag_italic = 'italic' in legacy_tag_css.lower() if isinstance(legacy_tag_css, str) else False
        if not hasattr(self.mw, 'tag_underline'): self.mw.tag_underline = 'underline' in legacy_tag_css.lower() if isinstance(legacy_tag_css, str) else False

        if not hasattr(self.mw, 'newline_color_rgba') or not getattr(self.mw, 'newline_color_rgba', None):
            legacy_nl_css = plugin_data.get('newline_css', '')
            nl_color = '#A020F0'
            if isinstance(legacy_nl_css, str) and '#' in legacy_nl_css:
                try:
                    hexpart = legacy_nl_css.split('#',1)[1].split(';',1)[0].strip()
                    if len(hexpart) >= 6: nl_color = f"#{hexpart[:6]}"
                except Exception: pass
            self.mw.newline_color_rgba = nl_color
        if not hasattr(self.mw, 'newline_bold'):
            legacy_nl_css = plugin_data.get('newline_css', '')
            self.mw.newline_bold = 'bold' in legacy_nl_css.lower() if isinstance(legacy_nl_css, str) else True
        if not hasattr(self.mw, 'newline_italic'):
            legacy_nl_css = plugin_data.get('newline_css', '')
            self.mw.newline_italic = 'italic' in legacy_nl_css.lower() if isinstance(legacy_nl_css, str) else False
        if not hasattr(self.mw, 'newline_underline'):
            legacy_nl_css = plugin_data.get('newline_css', '')
            self.mw.newline_underline = 'underline' in legacy_nl_css.lower() if isinstance(legacy_nl_css, str) else False

    def save(self) -> None:
        """Saves current settings to project_settings.json inside the project directory."""
        # Save custom aliases to aliases.json of the active plugin
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        if plugin_name:
            aliases_path = Path("plugins") / plugin_name / "aliases.json"
            try:
                aliases_path.parent.mkdir(parents=True, exist_ok=True)
                with open(aliases_path, 'w', encoding='utf-8') as f:
                    json.dump(getattr(self.mw, 'default_tag_mappings', {}), f, indent=4, ensure_ascii=False)
                log_info(f"Saved default tag mappings to {aliases_path}")
            except Exception as e:
                log_error(f"Failed to save aliases to {aliases_path}: {e}")

        project_settings_path = self._get_project_settings_path()
        if not project_settings_path:
            log_warning("No active project loaded. Project settings will not be saved.")
            return

        project_data = {}
        try:
            if project_settings_path.exists():
                with project_settings_path.open('r', encoding='utf-8') as f:
                    project_data = json.load(f)
        except Exception as e:
            log_error(f"Could not read existing project settings, will create a new one. Error: {e}", exc_info=True)

        plugin_data_to_save = {
            "default_tag_mappings": self.mw.default_tag_mappings,
            "block_names": self.mw.data_store.block_names,
            "block_color_markers": {k: list(v) for k, v in self.mw.block_color_markers.items()},
            "string_metadata": {str(k): v for k, v in self.mw.string_metadata.items()},
            "default_font_file": self.mw.default_font_file,
            "fonts_dir_path": getattr(self.mw, 'fonts_dir_path', ""),
            "orig_fonts_dir_path": getattr(self.mw, 'orig_fonts_dir_path', ""),
            "newline_display_symbol": self.mw.newline_display_symbol,
            "tag_color_rgba": getattr(self.mw, 'tag_color_rgba', "#FF8C00"),
            "tag_bold": getattr(self.mw, 'tag_bold', True),
            "tag_italic": getattr(self.mw, 'tag_italic', False),
            "tag_underline": getattr(self.mw, 'tag_underline', False),
            "newline_color_rgba": getattr(self.mw, 'newline_color_rgba', "#A020F0"),
            "newline_bold": getattr(self.mw, 'newline_bold', True),
            "newline_italic": getattr(self.mw, 'newline_italic', False),
            "newline_underline": getattr(self.mw, 'newline_underline', False),
            "preview_wrap_lines": self.mw.preview_wrap_lines,
            "editors_wrap_lines": self.mw.editors_wrap_lines,
            "game_dialog_max_width_pixels": self.mw.game_dialog_max_width_pixels,
            "line_width_warning_threshold_pixels": self.mw.line_width_warning_threshold_pixels,
            "lines_per_page": getattr(self.mw, 'lines_per_page', 4),
            "original_file_path": self.mw.data_store.json_path,
            "edited_file_path": self.mw.data_store.edited_json_path,
            "is_directory_mode": getattr(self.mw, 'is_directory_mode', False),
            "auto_generate_translation_path": getattr(self.mw, 'auto_generate_translation_path', False),
            "last_selected_block_index": self.mw.data_store.last_selected_block_index,
            "last_selected_string_index": self.mw.data_store.last_selected_string_index,
            "last_cursor_position_in_edited": self.mw.last_cursor_position_in_edited,
            "last_edited_text_edit_scroll_value_v": self.mw.last_edited_text_edit_scroll_value_v,
            "last_edited_text_edit_scroll_value_h": self.mw.last_edited_text_edit_scroll_value_h,
            "last_preview_text_edit_scroll_value_v": self.mw.last_preview_text_edit_scroll_value_v,
            "last_original_text_edit_scroll_value_v": self.mw.last_original_text_edit_scroll_value_v,
            "last_original_text_edit_scroll_value_h": self.mw.last_original_text_edit_scroll_value_h,
            "search_history": self.mw.search_history_to_save,
            "autofix_enabled": self.mw.autofix_enabled,
            "detection_enabled": self.mw.detection_enabled,
            "translation_config": self.mw.translation_config,
            "align_sentences_to_original_pages": getattr(self.mw, 'align_sentences_to_original_pages', False),
            "prevent_empty_lines_in_autofix": getattr(self.mw, 'prevent_empty_lines_in_autofix', False),
            "context_menu_tags": getattr(self.mw, 'context_menu_tags', {"single_tags": [], "wrap_tags": []})
        }
        
        project_data.update(plugin_data_to_save)
        
        try:
            project_settings_path.parent.mkdir(parents=True, exist_ok=True)
            with project_settings_path.open('w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4, ensure_ascii=False)
            log_debug(f"Project settings saved to '{project_settings_path}'.")
        except Exception as e:
            log_error(f"ERROR saving project settings to '{project_settings_path}': {e}", exc_info=True)
            if hasattr(self.mw, 'ui_provider') and self.mw.ui_provider:
                self.mw.ui_provider.show_message("Save Error", f"Could not save project configuration to\n{project_settings_path}", type="error")
            else:
                log_error("Could not save project configuration: UI provider not available.")

    def save_block_names(self) -> None:
        project_settings_path = self._get_project_settings_path()
        if not project_settings_path: return

        project_data = {}
        try:
            if project_settings_path.exists():
                with project_settings_path.open('r', encoding='utf-8') as f:
                    project_data = json.load(f)
        except Exception as e:
            log_error(f"Error reading project settings for block names: {e}", exc_info=True)

        project_data["block_names"] = self.mw.data_store.block_names
        try:
            with project_settings_path.open('w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4, ensure_ascii=False)
            log_debug(f"Block names saved successfully to '{project_settings_path}'.")
        except Exception as e:
            log_error(f"ERROR saving block names: {e}", exc_info=True)
