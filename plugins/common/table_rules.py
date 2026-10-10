"""Base rules for games whose text lives in binary tables, one table per source file.

A subclass names its file formats and implements ``parse_table(raw)``, which returns an object with
``texts() -> list[str]``, ``ids() -> list[str]`` (a label per string) and ``build(texts) -> bytes`` (the
table with new strings; unchanged strings keep their bytes) -- or None for a file that is not a text
table. Every table is one block. Fonts and textures come from ``font_sources.json`` and
``texture_sources.json`` next to the subclass, narrowed to the entries the project's source folder has.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces


class TableRules(BaseGameRules):
    """A table-per-file game (see the module docstring)."""

    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    display_name = ""
    file_formats: Tuple[Tuple[Tuple[str, ...], str], ...] = ()    # ((".eng",), "TEXT table"), ...
    default_script_name: Optional[str] = None
    lines_per_page = 4
    spellcheck_ignore = ""                                        # regex of the markup the spell checker skips

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, List[str]]]] = {}

    # -- to implement ------------------------------------------------------------

    def parse_table(self, raw: bytes):
        raise NotImplementedError

    # -- identity --------------------------------------------------------------

    def get_display_name(self) -> str:
        return self.display_name

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [*(FileFormat(exts, "bytes", label) for exts, label in self.file_formats), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        table = self.parse_table(self._last_loaded)
        if table is None:
            log_debug(f"{type(self).__module__}: not a text table")
            return [[]], {}
        return [table.texts()], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        table = self.parse_table(source)
        if table is None:
            return source
        return table.build([str(s) for s in (data[0] if data else [])])

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._save_source = self._last_loaded = None

    # -- context ---------------------------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, List[str]]]:
        """``(relative source path, string ids)`` of a block."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            rel = str(block.source_file).replace("\\", "/")
            table = self.parse_table(Path(pm.get_absolute_path(block.source_file)).read_bytes())
            found = (rel, table.ids()) if table is not None else None
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"{type(self).__module__}: no text file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._locate(block_idx)
        if not found or not 0 <= int(string_idx) < len(found[1]):
            return None
        return {"file": found[0], "id": found[1][int(string_idx)]}

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._locate(block_idx)
        return found[0] if found else None

    # -- fonts and textures: only the entries the project's source folder has ---

    def _present(self, name: str) -> List[Dict[str, Any]]:
        sources = self._plugin_json_list(name)
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        root = (getattr(getattr(pm, "project", None), "metadata", None) or {}).get("source_path")
        if not root or not Path(root).is_dir():
            return sources
        return [s for s in sources if any(Path(root).glob(s["path"]))] or sources

    def get_font_sources(self) -> List[Dict[str, Any]]:
        return self._present("font_sources.json")

    def get_texture_sources(self) -> List[Dict[str, Any]]:
        return self._present("texture_sources.json")

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return self.spellcheck_ignore

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return self.lines_per_page

    def get_default_script_name(self) -> Optional[str]:
        return self.default_script_name
