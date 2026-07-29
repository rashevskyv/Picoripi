import json
from pathlib import Path
from typing import Dict, Optional, Any
from utils.logging_utils import log_debug, log_info, log_error, log_warning

class FontMapLoader:
    """Font map loader implementation."""
    def __init__(self, main_window: Any):
        """Initialize a new instance."""
        self.mw = main_window

    def load_all_font_maps(self) -> None:
        """Load all font maps."""
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        self.mw.font_map = {}
        self.mw.all_font_maps = {}
        
        preserved_bfn = {}
        if hasattr(self.mw, 'all_bfn_fonts') and isinstance(self.mw.all_bfn_fonts, dict):
            preserved_bfn = dict(self.mw.all_bfn_fonts)
        self.mw.all_bfn_fonts = preserved_bfn
        
        self.mw.font_map_overrides = {}
        self.mw.icon_sequences = []

        if not plugin_name:
            log_warning("No active plugin. Character width calculations will use fallback.")
            return

        fonts_dirs = [Path("plugins") / plugin_name / "fonts"]
        custom_fonts_path = getattr(self.mw, 'fonts_dir_path', None)
        if custom_fonts_path:
            custom_dir = Path(custom_fonts_path)
            if custom_dir.is_dir():
                fonts_dirs.append(custom_dir)

        loaded_any = False
        for fonts_dir in fonts_dirs:
            if not fonts_dir.is_dir():
                continue
            log_debug(f"Loading all font maps from: {fonts_dir}")
            loaded_any = True
            for font_file in fonts_dir.iterdir():
                if not font_file.is_file():
                    continue
                suffix = font_file.suffix.lower()

                # Check for archives containing fonts
                if suffix in (".arc", ".rarc", ".u8"):
                    try:
                        from core.containers import ContainerManager
                        archive_data = font_file.read_bytes()
                        if ContainerManager.is_supported(archive_data):
                            container = ContainerManager.open(archive_data)
                            if container:
                                for inner_path in container.list_files():
                                    inner_suffix = Path(inner_path).suffix.lower()
                                    if inner_suffix not in (".json", ".bfn"):
                                        continue
                                    try:
                                        inner_bytes = container.read_file(inner_path)
                                        font_key = f"{font_file.name}/{Path(inner_path).name}"
                                        
                                        parsed_map = None
                                        if inner_suffix == ".json":
                                            parsed_map = json.loads(inner_bytes.decode('utf-8'))
                                            if "signature" in parsed_map and parsed_map["signature"] == "FFNT":
                                                parsed_map = self._parse_new_font_format(parsed_map)
                                        elif inner_suffix == ".bfn":
                                            from core.bfn_core import BfnCore
                                            bfn = BfnCore()
                                            bfn.load(inner_bytes)
                                            self.mw.all_bfn_fonts[font_key] = bfn
                                            
                                            # Load translation_map from active plugin if available
                                            translation_map = None
                                            project_dir = None
                                            if self.mw and hasattr(self.mw, 'project_manager') and self.mw.project_manager:
                                                project_dir = self.mw.project_manager.project_dir
                                            
                                            mapping_path = None
                                            if project_dir:
                                                proj_map_path = Path(project_dir) / 'translation_map.json'
                                                if not proj_map_path.exists():
                                                    try:
                                                        plugin_map = Path("plugins") / plugin_name / 'translation_map.json'
                                                        if plugin_map.exists():
                                                            import shutil
                                                            shutil.copy2(plugin_map, proj_map_path)
                                                            log_info(f"Copied translation_map.json to project: {proj_map_path}")
                                                        else:
                                                            with proj_map_path.open('w', encoding='utf-8') as f:
                                                                f.write("{}")
                                                    except Exception as e:
                                                        log_warning(f"Failed to copy/create translation_map.json in project: {e}")
                                                mapping_path = proj_map_path
                                            else:
                                                plugin_dir = Path("plugins") / plugin_name
                                                mapping_path = plugin_dir / 'translation_map.json'
                                                
                                            if mapping_path and mapping_path.exists():
                                                try:
                                                    with mapping_path.open('r', encoding='utf-8') as f:
                                                        translation_map = json.load(f)
                                                except Exception as e:
                                                    log_warning(f"Could not load translation mapping for BFN metrics: {e}")
                                            
                                            parsed_map = bfn.to_font_map(translation_map)
                                            
                                        if parsed_map is not None:
                                            self.mw.all_font_maps[font_key] = parsed_map
                                            log_debug(f"Successfully loaded font map '{font_key}' from archive '{font_file.name}'.")
                                    except Exception as e:
                                        log_error(f"Error reading or parsing font map '{inner_path}' from archive '{font_file.name}': {e}", exc_info=True)
                    except Exception as e:
                        log_error(f"Error processing archive file '{font_file.name}': {e}", exc_info=True)
                    continue

                if suffix not in (".json", ".bfn"):
                    continue
    
                try:
                    if suffix == ".json":
                        with font_file.open('r', encoding='utf-8') as f:
                            raw_font_data = json.load(f)
        
                        if "signature" in raw_font_data and raw_font_data["signature"] == "FFNT":
                            parsed_map = self._parse_new_font_format(raw_font_data)
                        else:
                            parsed_map = raw_font_data
                    elif suffix == ".bfn":
                        from core.bfn_core import BfnCore
                        bfn = BfnCore()
                        bfn.load_file(str(font_file))
                        self.mw.all_bfn_fonts[font_file.name] = bfn
                        
                        # Load translation_map from active plugin if available
                        translation_map = None
                        project_dir = None
                        if self.mw and hasattr(self.mw, 'project_manager') and self.mw.project_manager:
                            project_dir = self.mw.project_manager.project_dir
                        
                        mapping_path = None
                        if project_dir:
                            proj_map_path = Path(project_dir) / 'translation_map.json'
                            if not proj_map_path.exists():
                                try:
                                    plugin_map = Path("plugins") / plugin_name / 'translation_map.json'
                                    if plugin_map.exists():
                                        import shutil
                                        shutil.copy2(plugin_map, proj_map_path)
                                        log_info(f"Copied translation_map.json to project: {proj_map_path}")
                                    else:
                                        with proj_map_path.open('w', encoding='utf-8') as f:
                                            f.write("{}")
                                except Exception as e:
                                    log_warning(f"Failed to copy/create translation_map.json in project: {e}")
                            mapping_path = proj_map_path
                        else:
                            plugin_dir = Path("plugins") / plugin_name
                            mapping_path = plugin_dir / 'translation_map.json'
                            
                        if mapping_path and mapping_path.exists():
                            try:
                                with mapping_path.open('r', encoding='utf-8') as f:
                                    translation_map = json.load(f)
                            except Exception as e:
                                log_warning(f"Could not load translation mapping for BFN metrics: {e}")
                                
                        parsed_map = bfn.to_font_map(translation_map)
                    
                    self.mw.all_font_maps[font_file.name] = parsed_map
                    log_debug(f"Successfully loaded font map '{font_file.name}'.")
    
                except Exception as e:
                    log_error(f"Error reading or parsing font map file '{font_file.name}': {e}.", exc_info=True)

        # Dynamically load BFN fonts from all active project blocks (including inside archives)
        pm = getattr(self.mw, 'project_manager', None)
        if pm and pm.project:
            for block in pm.project.blocks:
                is_archive_member = block.metadata.get('is_archive_member', False)
                if is_archive_member:
                    archive_rel_path = block.metadata.get('archive_rel_path', '')
                    inner_file_name = block.metadata.get('archive_file_name', '')
                    if inner_file_name.lower().endswith(".bfn"):
                        try:
                            from core.containers import ContainerManager
                            container = pm.get_archive_container(archive_rel_path, is_translation=False)
                            if container:
                                bfn_bytes = container.read_file(inner_file_name)
                                if bfn_bytes:
                                    from core.bfn_core import BfnCore
                                    bfn = BfnCore()
                                    bfn.load(bfn_bytes)
                                    # Add to cache with both inner file name and archive-prefixed key
                                    self.mw.all_bfn_fonts[inner_file_name] = bfn
                                    font_key = f"{Path(archive_rel_path).name}/{inner_file_name}"
                                    self.mw.all_bfn_fonts[font_key] = bfn
                        except Exception:
                            pass
                else:
                    source_file = getattr(block, 'source_file', '')
                    if source_file and source_file.lower().endswith(".bfn"):
                        try:
                            src_abs = pm.get_absolute_path(source_file, is_translation=False)
                            if Path(src_abs).is_file():
                                from core.bfn_core import BfnCore
                                bfn = BfnCore()
                                bfn.load_file(str(src_abs))
                                self.mw.all_bfn_fonts[Path(source_file).name] = bfn
                        except Exception:
                            pass

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
        if hasattr(self.mw, 'ui_updater') and hasattr(self.mw.ui_updater, 'update_preview_visibility'):
            self.mw.ui_updater.update_preview_visibility()

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
        """Internal helper to load font overrides."""
        overrides: Dict[str, dict] = {}
        if not plugin_name: return overrides
        override_path = Path('plugins') / plugin_name / 'font_map.json'
        if not override_path.is_file():
            override_path = Path('plugins') / 'common' / 'defaults' / 'font_map.json'
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
        """Internal helper to apply font overrides."""
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
        """Update the icon highlighting."""
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
        """Update the icon sequences cache."""
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
