"""Silent Hill 3 (PC, English) plugin: one project block per ``*_eng_msg.mes`` file, one row per message.

The project's source folder is the ``source`` folder that ``1_unpack.bat`` fills from ``data\\msg.arc``.
Saving writes the same file into the translation folder; the build packs every changed file back into
``msg.arc`` and keeps the other entries byte for byte. A message keeps its own bytes until it is edited.
"""
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning

from . import doc
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


class GameRules(BaseGameRules):
    """Silent Hill 3 (PC, English messages)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Silent Hill 3 (PC)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".mes",), "bytes", "Silent Hill 3 messages"), *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            lines = doc.texts(data)
        except ValueError as error:
            log_debug(f"silent_hill_3_pc: not a message table: {error}")
            return [[]], {}
        return [lines], {"0": "messages"}

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        rows = data[0] if data and isinstance(data[0], list) else (data or [])
        out, problems = doc.build(source, rows)
        for problem in problems:
            log_warning(f"silent_hill_3_pc: {problem}")
        return out

    def get_editor_page_size(self) -> int:
        return 1

    def get_spellcheck_ignore_pattern(self) -> str:
        return r"\{[0-9A-F]{2}\}"

    def get_tag_tooltip(self, tag: str) -> str:
        return "Game control byte (message start, end or code); keep it as it is."
