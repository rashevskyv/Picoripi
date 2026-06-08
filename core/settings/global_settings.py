import json
import base64
from pathlib import Path
from typing import Dict, Any, Union, Optional
from PyQt5.QtGui import QFont
from utils.logging_utils import log_debug, log_info, log_error, log_warning
from core.translation.config import build_default_translation_config, merge_translation_config

class GlobalSettings:
    def __init__(self, main_window: Any, settings_file_path: Union[str, Path] = "settings.json"):
        self.mw = main_window
        self.settings_file_path = settings_file_path
        self.defaults = self._get_defaults()

    def _get_defaults(self) -> Dict[str, Any]:
        default_font_size = QFont().pointSize() if QFont().pointSize() > 0 else 10
        return {
            "tree_font_size": default_font_size,
            "preview_font_size": default_font_size,
            "editors_font_size": default_font_size,
            "tooltip_font_size": 11,
            "external_script_path": "",
            "font_size": default_font_size,
            "active_game_plugin": "zelda_mc",
            "show_multiple_spaces_as_dots": True,
            "enable_console_logging": True,
            "enable_file_logging": True,
            "log_file_path": "",
            "settings_window_width": 800,
            "enabled_log_categories": ["general", "lifecycle", "file_ops", "settings", "ui_action", "ai", "scanner", "plugins"],
            "space_dot_color_hex": "#BBBBBB",
            "window_was_maximized": False,
            "window_normal_geometry": None,
            "main_splitter_state": None,
            "right_splitter_state": None,
            "bottom_right_splitter_state": None,
            "editor_preview_splitter_state": None,
            "theme": "auto",
            "restore_unsaved_on_startup": False,
            "last_opened_path": "",
            "prompt_editor_enabled": True,
            "spellchecker_enabled": False,
            "spellchecker_language": "uk",
            "preview_enabled": True,
            "warnings_enabled": True,
            "glossary_enabled": True,
            "show_archive_size_warnings": True,
            "last_browse_dir": str(Path.home()),
            "recent_projects": [],
            "translation_ai": {
                "provider": "OpenAI", "api_key": "", "model": "gpt-4o"
            },
            "translation_config": build_default_translation_config(),
            "translation_presets": {},
            "current_translation_preset": "default",
            "glossary_ai": {
                "provider": "OpenAI",
                "api_key": "",
                "use_translation_api_key": False,
                "model": "gpt-4o",
                "chunk_size": 8000
            },
            "bfn_glyph_table_column_widths": [],
            "bookmarks": [],
            "bfn_auto_sync_enabled": False,
            "preview_bg_image_path": "",
            "preview_bg_scale": 100,
            "preview_bg_offset_x": 0,
            "preview_bg_offset_y": 0,
            "preview_bg_hidden": False,
            "preview_line_spacing": 10,
            "preview_text_rect": [15, 15, 300, 120],
            "preview_text_color": "#ffffff",
            "preview_shadow_enabled": False,
            "preview_shadow_color": "#000000",
            "preview_shadow_alpha": 178,
            "preview_shadow_angle": 315,
            "preview_shadow_distance": 3,
            "preview_glow_enabled": False,
            "preview_glow_color": "#ffffff",
            "preview_glow_alpha": 180,
            "preview_glow_spread": 4,
            "preview_fix_font_scale": False,
            "preview_fixed_font_scale": 1.0,
            "mempalace_file_path": "",
            "mempalace_wing_name": "",
            "mempalace_mapping_scope": 0,
            "mempalace_mapping_only": False,
            "mempalace_selected_blocks": [],
            "mempalace_builder_width": 650,
            "mempalace_builder_height": 500,
            "log_ai_traffic": False,
            "show_force_alias_warning": True,
            "variations_window_geometry": None,
            "variations_splitter_state": None,
            "hide_empty_strings": False
        }

    def load(self, settings_dict: Dict[str, Any]) -> None:
        """Loads global settings into the provided settings_dict and updates MainWindow."""
        for key, value in self.defaults.items():
            settings_dict[key] = value
            # Compatibility: only set if not property
            cls = type(self.mw)
            attr = getattr(cls, key, None)
            if not isinstance(attr, property):
                setattr(self.mw, key, value)
        
        self.mw.current_font_size = self.defaults['font_size']

        p_file = Path(self.settings_file_path)
        if not p_file.exists():
            return

        try:
            with p_file.open('r', encoding='utf-8') as f:
                settings_data = json.load(f)

            for key, default_value in self.defaults.items():
                loaded_value = settings_data.get(key, default_value)
                if key == "translation_config":
                    merged_value = merge_translation_config(default_value, loaded_value)
                    settings_dict[key] = merged_value
                    if not isinstance(getattr(type(self.mw), key, None), property):
                        setattr(self.mw, key, merged_value)
                elif isinstance(default_value, dict):
                    merged_value = default_value.copy()
                    if isinstance(loaded_value, dict):
                        merged_value.update(loaded_value)
                    settings_dict[key] = merged_value
                    if not isinstance(getattr(type(self.mw), key, None), property):
                        setattr(self.mw, key, merged_value)
                else:
                    settings_dict[key] = loaded_value
                    if not isinstance(getattr(type(self.mw), key, None), property):
                        setattr(self.mw, key, loaded_value)

            # Specialized logic from original _load_global_settings
            default_font_size = self.defaults['font_size']
            self.mw.editors_font_size = settings_data.get('editors_font_size', settings_data.get('font_size', default_font_size))
            self.mw.tree_font_size = settings_data.get('tree_font_size', settings_data.get('font_size', default_font_size))
            self.mw.preview_font_size = settings_data.get('preview_font_size', settings_data.get('font_size', default_font_size))
            self.mw.current_font_size = settings_data.get('font_size', default_font_size)
            self.mw.window_geometry_to_restore = settings_data.get("window_normal_geometry")
            self.mw.window_was_maximized_at_save = settings_data.get("window_was_maximized", False)
            log_debug("Global settings loaded.")
        except Exception as e:
            log_error(f"Error loading global settings: {e}", exc_info=True)

    def save(self, settings_dict: Dict[str, Any]) -> None:
        """Saves current global settings to settings.json."""
        global_data = {}
        p_file = Path(self.settings_file_path)
        try:
            if p_file.exists():
                with p_file.open('r', encoding='utf-8') as f:
                    global_data = json.load(f)
        except Exception as e:
             log_error(f"Could not read existing global settings, will create a new one. Error: {e}", exc_info=True)

        translation_config_to_save = getattr(self.mw, 'translation_config', {})
        if not isinstance(translation_config_to_save, dict):
            translation_config_to_save = {}

        translation_ai_val = getattr(self.mw, 'translation_ai', {})
        translation_ai_to_save = translation_ai_val.copy() if isinstance(translation_ai_val, dict) else {}

        if translation_config_to_save:
            provider = translation_config_to_save.get('provider', 'disabled')
            if provider != 'disabled':
                prov_cfg = translation_config_to_save.get('providers', {}).get(provider, {})
                if isinstance(prov_cfg, dict):
                    translation_ai_to_save['provider'] = provider
                    if 'api_key' in prov_cfg:
                        translation_ai_to_save['api_key'] = prov_cfg['api_key']
                    if 'model' in prov_cfg:
                        translation_ai_to_save['model'] = prov_cfg['model']

        global_data.update({
            "tree_font_size": getattr(self.mw, 'tree_font_size', self.mw.current_font_size),
            "preview_font_size": getattr(self.mw, 'preview_font_size', self.mw.current_font_size),
            "editors_font_size": getattr(self.mw, 'editors_font_size', self.mw.current_font_size),
            "tooltip_font_size": getattr(self.mw, 'tooltip_font_size', 11),
            "external_script_path": "" if type(getattr(self.mw, 'external_script_path', "")).__name__ in ('Mock', 'MagicMock') else getattr(self.mw, 'external_script_path', ""),
            "font_size": self.mw.current_font_size,
            "active_game_plugin": self.mw.active_game_plugin,
            "show_multiple_spaces_as_dots": self.mw.show_multiple_spaces_as_dots,
            "space_dot_color_hex": self.mw.space_dot_color_hex,
            "window_was_maximized": self.mw.window_was_maximized_on_close,
            "theme": getattr(self.mw, 'theme', 'auto'),
            "restore_unsaved_on_startup": self.mw.restore_unsaved_on_startup,
            "last_opened_path": getattr(self.mw, 'last_opened_path', ""),
            "prompt_editor_enabled": getattr(self.mw, 'prompt_editor_enabled', True),
            "recent_projects": getattr(self.mw, 'recent_projects', []),
            "translation_ai": translation_ai_to_save,
            "translation_config": translation_config_to_save,
            "translation_presets": getattr(self.mw, 'translation_presets', {}) if isinstance(getattr(self.mw, 'translation_presets', {}), dict) else {},
            "current_translation_preset": getattr(self.mw, 'current_translation_preset', 'default') if isinstance(getattr(self.mw, 'current_translation_preset', 'default'), str) else 'default',
            "glossary_ai": getattr(self.mw, 'glossary_ai', {}),
            "spellchecker_enabled": getattr(self.mw, 'spellchecker_enabled', False),
            "spellchecker_language": getattr(self.mw, 'spellchecker_language', 'uk'),
            "preview_enabled": getattr(self.mw, 'preview_enabled', True),
            "warnings_enabled": getattr(self.mw, 'warnings_enabled', True),
            "glossary_enabled": getattr(self.mw, 'glossary_enabled', True),
            "show_archive_size_warnings": getattr(self.mw, 'show_archive_size_warnings', True),
            "last_browse_dir": getattr(self.mw, 'last_browse_dir', str(Path.home())),
            "enable_console_logging": getattr(self.mw, 'enable_console_logging', True),
            "enable_file_logging": getattr(self.mw, 'enable_file_logging', True),
            "settings_window_width": getattr(self.mw, 'settings_window_width', 800),
            "log_file_path": getattr(self.mw, 'log_file_path', ""),
            "enabled_log_categories": getattr(self.mw, 'enabled_log_categories', ["general", "lifecycle", "file_ops", "settings", "ui_action", "ai", "scanner", "plugins"]),
            "bfn_glyph_table_column_widths": getattr(self.mw, 'bfn_glyph_table_column_widths', []),
            "bookmarks": getattr(self.mw, 'bookmarks', []) if isinstance(getattr(self.mw, 'bookmarks', []), list) else [],
            "bfn_auto_sync_enabled": getattr(self.mw, 'bfn_auto_sync_enabled', False),
            "preview_bg_image_path": getattr(self.mw, 'preview_bg_image_path', ""),
            "preview_bg_scale": getattr(self.mw, 'preview_bg_scale', 100),
            "preview_bg_offset_x": getattr(self.mw, 'preview_bg_offset_x', 0),
            "preview_bg_offset_y": getattr(self.mw, 'preview_bg_offset_y', 0),
            "preview_bg_hidden": getattr(self.mw, 'preview_bg_hidden', False),
            "preview_line_spacing": getattr(self.mw, 'preview_line_spacing', 10),
            "preview_text_rect": getattr(self.mw, 'preview_text_rect', [15, 15, 300, 120]),
            "preview_text_color": getattr(self.mw, 'preview_text_color', '#ffffff'),
            "preview_shadow_enabled": getattr(self.mw, 'preview_shadow_enabled', False),
            "preview_shadow_color": getattr(self.mw, 'preview_shadow_color', '#000000'),
            "preview_shadow_alpha": getattr(self.mw, 'preview_shadow_alpha', 178),
            "preview_shadow_angle": getattr(self.mw, 'preview_shadow_angle', 315),
            "preview_shadow_distance": getattr(self.mw, 'preview_shadow_distance', 3),
            "preview_glow_enabled": getattr(self.mw, 'preview_glow_enabled', False),
            "preview_glow_color": getattr(self.mw, 'preview_glow_color', '#ffffff'),
            "preview_glow_alpha": getattr(self.mw, 'preview_glow_alpha', 180),
            "preview_glow_spread": getattr(self.mw, 'preview_glow_spread', 4),
            "preview_fix_font_scale": getattr(self.mw, 'preview_fix_font_scale', False),
            "preview_fixed_font_scale": getattr(self.mw, 'preview_fixed_font_scale', 1.0),
            "mempalace_file_path": settings_dict.get("mempalace_file_path", ""),
            "mempalace_wing_name": settings_dict.get("mempalace_wing_name", ""),
            "mempalace_mapping_scope": settings_dict.get("mempalace_mapping_scope", 0),
            "mempalace_mapping_only": settings_dict.get("mempalace_mapping_only", False),
            "mempalace_selected_blocks": settings_dict.get("mempalace_selected_blocks", []),
            "mempalace_builder_width": settings_dict.get("mempalace_builder_width", 650),
            "mempalace_builder_height": settings_dict.get("mempalace_builder_height", 500),
            "log_ai_traffic": False if type(getattr(self.mw, 'log_ai_traffic', False)).__name__ in ('Mock', 'MagicMock') else bool(getattr(self.mw, 'log_ai_traffic', False)),
            "show_force_alias_warning": True if type(getattr(self.mw, 'show_force_alias_warning', True)).__name__ in ('Mock', 'MagicMock') else bool(getattr(self.mw, 'show_force_alias_warning', True)),
            "variations_window_geometry": getattr(self.mw, 'variations_window_geometry', None) if isinstance(getattr(self.mw, 'variations_window_geometry', None), dict) else None,
            "variations_splitter_state": getattr(self.mw, 'variations_splitter_state', None) if isinstance(getattr(self.mw, 'variations_splitter_state', None), str) else None,
            "hide_empty_strings": False if type(getattr(getattr(self.mw, 'data_store', None), 'hide_empty_strings', False)).__name__ in ('Mock', 'MagicMock') else bool(getattr(getattr(self.mw, 'data_store', None), 'hide_empty_strings', False))
        })

        if self.mw.restore_unsaved_on_startup and self.mw.data_store.edited_data:
            serializable_edited_data = {str(k): v for k, v in self.mw.data_store.edited_data.items()}
            global_data["unsaved_session_data"] = serializable_edited_data
        elif "unsaved_session_data" in global_data:
            del global_data["unsaved_session_data"]

        if self.mw.window_normal_geometry_on_close:
            geom = self.mw.window_normal_geometry_on_close
            global_data["window_normal_geometry"] = {"x": geom.x(), "y": geom.y(), "width": geom.width(), "height": geom.height()}
        
        try:
            if self.mw.main_splitter: global_data["main_splitter_state"] = base64.b64encode(self.mw.main_splitter.saveState().data()).decode('ascii')
            if self.mw.right_splitter: global_data["right_splitter_state"] = base64.b64encode(self.mw.right_splitter.saveState().data()).decode('ascii')
            if self.mw.bottom_right_splitter: global_data["bottom_right_splitter_state"] = base64.b64encode(self.mw.bottom_right_splitter.saveState().data()).decode('ascii')
            if self.mw.editor_preview_splitter: global_data["editor_preview_splitter_state"] = base64.b64encode(self.mw.editor_preview_splitter.saveState().data()).decode('ascii')
        except Exception as e: log_warning(f"Failed to save splitter state(s): {e}")

        try:
            with p_file.open('w', encoding='utf-8') as f:
                json.dump(global_data, f, indent=4, ensure_ascii=False)
            log_debug("Global settings saved.")
        except Exception as e:
            log_error(f"ERROR saving global settings: {e}", exc_info=True)
