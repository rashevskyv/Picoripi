import json
from pathlib import Path
from typing import Dict, Optional, Any, List
from utils.logging_utils import log_debug, log_info, log_error, log_warning

class FontMapLoader:
    def __init__(self, main_window: Any):
        self.mw = main_window

    def load_all_font_maps(self) -> None:
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        self.mw.font_map = {}
        self.mw.all_font_maps = {}
        self.mw.font_map_overrides = {}
        self.mw.icon_sequences = []

        if not plugin_name:
            log_warning("No active plugin. Character width calculations will use fallback.")
            return

        fonts_dir = Path("plugins") / plugin_name / "fonts"
        if not fonts_dir.is_dir():
            log_warning(f"Fonts directory not found at '{fonts_dir}'. Skipping JSON font files loading.")
        else:
            log_debug(f"Loading all font maps from: {fonts_dir}")
            for font_file in fonts_dir.iterdir():
                if not font_file.is_file() or not font_file.suffix.lower() == ".json":
                    continue
    
                try:
                    with font_file.open('r', encoding='utf-8') as f:
                        raw_font_data = json.load(f)
    
                    if "signature" in raw_font_data and raw_font_data["signature"] == "FFNT":
                        parsed_map = self._parse_new_font_format(raw_font_data)
                    else:
                        parsed_map = raw_font_data
                    
                    self.mw.all_font_maps[font_file.name] = parsed_map
                    log_debug(f"Successfully loaded font map '{font_file.name}'.")
    
                except Exception as e:
                    log_error(f"Error reading or parsing font map file '{font_file.name}': {e}.", exc_info=True)

        default_font_filename = getattr(self.mw, 'default_font_file', None)
        if default_font_filename and default_font_filename in self.mw.all_font_maps:
            self.mw.font_map = self.mw.all_font_maps[default_font_filename]
            log_debug(f"Set default font_map to '{default_font_filename}'.")
        elif self.mw.all_font_maps:
            first_font = next(iter(self.mw.all_font_maps))
            self.mw.font_map = self.mw.all_font_maps[first_font]
            log_info(f"Default font file not found, using first available font as default: '{first_font}'.")
        else:
            log_warning("No font maps loaded for the plugin.")

        overrides = self._load_font_overrides(plugin_name)
        if overrides:
            self._apply_font_overrides(overrides)
        self.update_icon_sequences_cache()
        self.refresh_icon_highlighting()

    def _parse_new_font_format(self, font_data: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
        """Parses the new font format and returns a font_map."""
        font_map = {}
        if not isinstance(font_data, dict) or "glyphs" not in font_data:
            return font_map
        for glyph_info in font_data["glyphs"]:
            char = glyph_info.get("char")
            width_info = glyph_info.get("width")
            if char and isinstance(width_info, dict) and "char" in width_info:
                font_map[char] = {"width": width_info["char"]}
        return font_map

    def _load_font_overrides(self, plugin_name: Optional[str]) -> Dict[str, dict]:
        overrides: Dict[str, dict] = {}
        if not plugin_name: return overrides
        override_path = Path('plugins') / plugin_name / 'font_map.json'
        if not override_path.is_file(): return overrides

        try:
            with override_path.open('r', encoding='utf-8') as f:
                raw_data = json.load(f)
            if isinstance(raw_data, dict):
                for key, value in raw_data.items():
                    if isinstance(key, str) and isinstance(value, dict):
                        width = value.get('width')
                        if isinstance(width, (int, float)):
                            overrides[key] = {'width': int(width)}
            log_debug(f"Loaded {len(overrides)} font override entries from '{override_path}'.")
        except Exception as exc:
            log_error(f"Failed to read font override map '{override_path}': {exc}", exc_info=True)
        return overrides

    def _apply_font_overrides(self, overrides: Dict[str, dict]) -> None:
        if not overrides: return
        if not hasattr(self.mw, 'font_map') or self.mw.font_map is None:
            self.mw.font_map = {}

        for font_map in self.mw.all_font_maps.values():
            if isinstance(font_map, dict):
                for key, data in overrides.items():
                    font_map[key] = dict(data)

        for key, data in overrides.items():
            self.mw.font_map[key] = dict(data)

        setattr(self.mw, 'font_map_overrides', overrides)
        self.update_icon_sequences_cache()
        self.refresh_icon_highlighting()

    def refresh_icon_highlighting(self) -> None:
        editors = []
        for attr in ('original_text_edit', 'edited_text_edit', 'preview_text_edit'):
            editor = getattr(self.mw, attr, None)
            if editor and hasattr(editor, 'highlighter') and editor.highlighter:
                editors.append(editor.highlighter)
        for highlighter in editors:
            if hasattr(highlighter, '_invalidate_icon_cache'):
                highlighter._invalidate_icon_cache()
            highlighter.rehighlight()

    def update_icon_sequences_cache(self) -> None:
        sequences = set()
        all_maps = getattr(self.mw, 'all_font_maps', {}) or {}
        if isinstance(all_maps, dict):
            for font_map in all_maps.values():
                if isinstance(font_map, dict):
                    for key, value in font_map.items():
                        if isinstance(key, str) and len(key) > 1 and isinstance(value, dict) and 'width' in value:
                            sequences.add(key)
        
        current_map = getattr(self.mw, 'font_map', {})
        if isinstance(current_map, dict):
            for key, value in current_map.items():
                if isinstance(key, str) and len(key) > 1 and isinstance(value, dict) and 'width' in value:
                    sequences.add(key)
                    
        self.mw.icon_sequences = sorted(sequences, key=len, reverse=True)
