"""Silent Hill 2 (PC; the same data files serve the Switch homebrew port) plugin: the game's message files.

Each ``data\\etc\\message\\*.mes`` file is one project block; its messages are the block's lines. A line is the
message as text in the PC font charset (byte b shows the character b + 0x20 in Windows-1252): 0x00 is a space, 0x07 an
apostrophe, the bytes the font has no character for are tags ``{XX}``
(kept as it is). Saving rebuilds the file: the messages are encoded again and the table is rewritten, so a
longer message is allowed. A line that cannot be encoded keeps its original bytes (a warning is logged).
"""
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning

from . import mes
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


class GameRules(BaseGameRules):
    """Silent Hill 2 (PC data, Enhanced Edition packs or the retail data; Switch homebrew reads the same files)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Silent Hill 2 (PC / Switch data)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".mes",), "bytes", "Silent Hill 2 message files"), *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            messages = mes.split(data)
        except ValueError as error:
            log_debug(f"silent_hill2_pc: not a message file ({error})")
            return [[]], {}
        return [[mes.decode(m) for m in messages]], {"0": "messages"}

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        originals = mes.split(source)
        lines = (data[0] if data else []) or []
        if len(lines) != len(originals):
            log_warning(f"silent_hill2_pc: message count changed ({len(lines)} for {len(originals)}); file not saved")
            return source
        out = []
        for index, (original, text) in enumerate(zip(originals, lines)):
            if text == mes.decode(original):
                out.append(original)
                continue
            try:
                out.append(mes.encode(text))
            except ValueError as error:
                log_warning(f"silent_hill2_pc: message {index} kept as it was: {error}")
                out.append(original)
        return mes.build(out)

    def get_editor_page_size(self) -> int:
        return 1

    def get_spellcheck_ignore_pattern(self) -> str:
        return r"\{[0-9A-Fa-f]{2}\}"

    def get_tag_tooltip(self, tag: str) -> str:
        return "Game code (byte) kept as it is." if tag.startswith("{") else ""
