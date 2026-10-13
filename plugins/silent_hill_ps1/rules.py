"""Silent Hill (PlayStation, USA 1.1) plugin: map and menu messages, item texts and the title menu.

The project's source folder is the ``source`` folder that ``1_unpack.bat`` fills from the disc:
``VIN\\*.BIN`` (map overlays: the message tables), ``1ST\\BODYPROG.BIN`` (decrypted: item names and
descriptions, title menu). Saving writes the same file into the translation folder; the build step
encrypts BODYPROG again and writes every changed file back over its sectors on the disc. A string
keeps its room: the translation may not be longer than the English (see ``doc.py``).
"""
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning

from . import doc, pc_keys
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


class GameRules(BaseGameRules):
    """Silent Hill (PlayStation, USA 1.1, SLUS-00707)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._pc_doc: Optional[Dict[str, Any]] = None   # the PC-port keys document (pc_keys.py), when loaded
        self._last_kind: Optional[str] = None           # "disc" (bytes) or "pc" (the keys document): what a save writes

    def get_display_name(self) -> str:
        return "Silent Hill (PlayStation)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Silent Hill overlays and BODYPROG"), *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if pc_keys.is_document(json_obj):
            self._pc_doc = json_obj
            self._last_kind = "pc"
            return pc_keys.blocks(json_obj)
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_kind = "disc"
        self._last_loaded = data
        groups = doc.parse(data)
        if not groups:
            log_debug("silent_hill_ps1: no text tables in this file")
            return [[]], {}
        blocks = [[slot.text for slot in group.slots] for group in groups]
        names = {str(i): group.label for i, group in enumerate(groups)}
        return blocks, names

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._last_kind == "pc" and self._pc_doc is not None:
            return pc_keys.with_texts(self._pc_doc, data or [])
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        out, problems = doc.build(source, data or [])
        for problem in problems:
            log_warning(f"silent_hill_ps1: not written, {problem}")
        return out

    def get_editor_page_size(self) -> int:
        return 1

    def get_spellcheck_ignore_pattern(self) -> str:
        return r"~[A-Z]\d*(?:\(\d+(?:\.\d+)?\))?|\\[nt]"

    def get_tag_tooltip(self, tag: str) -> str:
        return {"~N": "Line break inside a message.", "~E": "End of the message."}.get(tag, "Game control code.")
