"""Metal Gear Solid: Peace Walker -- Master Collection Version (Switch, PC) plugin.

A project's source folder is the workspace's ``source\\`` (``1_unpack.bat``, ``_shared\\scripts\\zt\\mgmc2.py``):
``text\\*.olang`` -- the English strings of the Multilingual Pack's language files (``MLG/Text``; layout in
``olang.py``): menus, mission and item names, help, one block per file -- and ``launcher\\text\\**\\*.mctext``,
the collection launcher's menus, credits, Master Book and Screenplay Book (``plugins.common.mgmc_launcher``).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common import mgmc_launcher
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import olang
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


def load_bytes(data: bytes) -> Tuple[List[List[str]], Dict[str, str]]:
    """Blocks and block names of an .olang or .mctext file (shared with the tests)."""
    if mgmc_launcher.is_launcher_text(data):
        return [[text for _path, text in mgmc_launcher.lines(data)]], {"0": "Launcher"}
    return [olang.lines(data)], {"0": "Strings"}


def save_bytes(source: bytes, data: list) -> bytes:
    texts = (data or [[]])[0] if data else []
    if mgmc_launcher.is_launcher_text(source):
        return mgmc_launcher.build(source, texts)
    return olang.build(source, texts)


class GameRules(BaseGameRules):
    """Metal Gear Solid: Peace Walker (Master Collection Version)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Metal Gear Solid: Peace Walker (Master Collection)"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".olang",), "bytes", "Peace Walker text"),
                FileFormat((mgmc_launcher.EXTENSION,), "bytes", "Launcher text")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            return load_bytes(data)
        except (ValueError, KeyError, UnicodeDecodeError) as error:
            log_debug(f"metal_gear_pw: not a Peace Walker text file ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = bytes(versions[-1]) if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        return save_bytes(source, data)

    def reset_runtime_state(self) -> None:
        self._save_source = self._last_loaded = None

    def get_tag_tooltip(self, tag: str) -> str:
        tag = str(tag)
        if tag.startswith("<I="):
            return "Button or icon picture (keep it)"
        if tag.startswith("<C="):
            return "Text colour"
        return ""

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
