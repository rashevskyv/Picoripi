import json
import os
from pathlib import Path
from typing import Dict, Optional, List, Any, Union
from PyQt5.QtWidgets import QMessageBox
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
            "string_metadata": {}, "default_font_file": "",
            "newline_display_symbol": "↵", "newline_css": "color: #A020F0; font-weight: bold;",
            "tag_css": "color: #808080; font-style: italic;",
            "bracket_tag_color_hex": "#FF8C00",
            "preview_wrap_lines": True, "editors_wrap_lines": False,
            "game_dialog_max_width_pixels": DEFAULT_GAME_DIALOG_MAX_WIDTH_PIXELS,
            "line_width_warning_threshold_pixels": DEFAULT_LINE_WIDTH_WARNING_THRESHOLD,
            "lines_per_page": 4,
            "original_file_path": None, "edited_file_path": None,
            "last_selected_block_index": -1, "last_selected_string_index": -1,
            "last_cursor_position_in_edited": 0, "last_edited_text_edit_scroll_value_v": 0,
            "last_edited_text_edit_scroll_value_h": 0, "last_preview_text_edit_scroll_value_v": 0,
            "last_original_text_edit_scroll_value_v": 0, "last_original_text_edit_scroll_value_h": 0,
            "search_history": [],
            "translation_config": build_default_translation_config(),
            "autofix_enabled": {},
            "detection_enabled": {},
            "context_menu_tags": {"single_tags": [], "wrap_tags": []}
        }
        for key, value in defaults.items():
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
        
        if not hasattr(self.mw, 'block_names'): self.mw.block_names = {}
        if not hasattr(self.mw, 'block_color_markers'): self.mw.block_color_markers = {}
        if not hasattr(self.mw, 'default_tag_mappings'): self.mw.default_tag_mappings = {}
        if not hasattr(self.mw, 'string_metadata'): self.mw.string_metadata = {}
        if not hasattr(self.mw, 'context_menu_tags'): self.mw.context_menu_tags = {"single_tags": [], "wrap_tags": []}
        self.mw.search_history_to_save = []

        plugin_config_path = self._get_plugin_config_path()
        if not plugin_config_path or not plugin_config_path.exists():
            log_warning(f"Plugin config not found at '{plugin_config_path}'. Using defaults.")
            return

        try:
            with plugin_config_path.open('r', encoding='utf-8') as f:
                plugin_data = json.load(f)

            plugin_data = self._substitute_env_vars(plugin_data)
            self.mw.block_names.update({str(k): v for k, v in plugin_data.get("block_names", {}).items()})
            self.mw.block_color_markers.update({k: set(v) for k, v in plugin_data.get("block_color_markers", {}).items()})
            self.mw.default_tag_mappings.update(plugin_data.get("default_tag_mappings", {}))
            
            try:
                self.mw.string_metadata = {eval(k): v for k, v in plugin_data.get("string_metadata", {}).items()}
            except Exception as e:
                log_error(f"Error deserializing string_metadata keys: {e}. Metadata will be empty.", exc_info=True)
                self.mw.string_metadata = {}
            
            for key, value in plugin_data.items():
                if key in ["block_names", "block_color_markers", "default_tag_mappings", "string_metadata"]:
                    continue
                settings_dict[key] = value
                if hasattr(self.mw, key) and not isinstance(getattr(type(self.mw), key, None), property):
                    setattr(self.mw, key, value)

            # Legacy migration logic
            self._migrate_legacy_styles(plugin_data)
            
            self.mw.search_history_to_save = plugin_data.get("search_history", [])
            self.mw.autofix_enabled = plugin_data.get("autofix_enabled", {})
            self.mw.detection_enabled = plugin_data.get("detection_enabled", {})

            loaded_translation = plugin_data.get("translation_config", {})
            if isinstance(loaded_translation, dict):
                self.mw.translation_config = merge_translation_config(build_default_translation_config(), loaded_translation)
            else:
                self.mw.translation_config = build_default_translation_config()

            log_debug(f"Plugin settings loaded from '{plugin_config_path}'.")
        except Exception as e:
            log_error(f"Error loading plugin settings from '{plugin_config_path}': {e}", exc_info=True)

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
        """Saves current plugin settings to plugin's config.json."""
        plugin_config_path = self._get_plugin_config_path()
        if not plugin_config_path: return

        plugin_data = {}
        try:
            if plugin_config_path.exists():
                with plugin_config_path.open('r', encoding='utf-8') as f:
                    plugin_data = json.load(f)
        except Exception as e:
            log_error(f"Could not read existing plugin config, will create a new one. Error: {e}", exc_info=True)

        plugin_data_to_save = {
            "default_tag_mappings": self.mw.default_tag_mappings,
            "block_names": self.mw.block_names,
            "block_color_markers": {k: list(v) for k, v in self.mw.block_color_markers.items()},
            "string_metadata": {str(k): v for k, v in self.mw.string_metadata.items()},
            "default_font_file": self.mw.default_font_file,
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
            "original_file_path": self.mw.json_path,
            "edited_file_path": self.mw.edited_json_path,
            "last_selected_block_index": self.mw.last_selected_block_index,
            "last_selected_string_index": self.mw.last_selected_string_index,
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
            "context_menu_tags": getattr(self.mw, 'context_menu_tags', {"single_tags": [], "wrap_tags": []})
        }
        
        plugin_data.update(plugin_data_to_save)
        
        try:
            with plugin_config_path.open('w', encoding='utf-8') as f:
                json.dump(plugin_data, f, indent=4, ensure_ascii=False)
            log_debug(f"Plugin settings saved to '{plugin_config_path}'.")
        except Exception as e:
            log_error(f"ERROR saving plugin settings to '{plugin_config_path}': {e}", exc_info=True)
            QMessageBox.critical(self.mw, "Save Error", f"Could not save plugin configuration to\n{plugin_config_path}")

    def save_block_names(self) -> None:
        plugin_config_path = self._get_plugin_config_path()
        if not plugin_config_path: return

        plugin_data = {}
        try:
            if plugin_config_path.exists():
                with plugin_config_path.open('r', encoding='utf-8') as f:
                    plugin_data = json.load(f)
        except Exception as e:
            log_error(f"Error reading plugin config for block names: {e}", exc_info=True)

        plugin_data["block_names"] = self.mw.block_names
        try:
            with plugin_config_path.open('w', encoding='utf-8') as f:
                json.dump(plugin_data, f, indent=4, ensure_ascii=False)
            log_debug(f"Block names saved successfully to '{plugin_config_path}'.")
        except Exception as e:
            log_error(f"ERROR saving block names: {e}", exc_info=True)
