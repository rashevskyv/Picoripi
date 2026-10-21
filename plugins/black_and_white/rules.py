"""Black & White (openBlack Switch port): the ADD_TEXT strings of Scripts/InfoScript2.txt as one block.

The source file (English) and the translation file have the same shape. The translation's text replaces the text of
each ADD_TEXT call; the flag, narrator and key of every call come from the newest file the save can see, so the
translation keeps the game's own fields. The build copies the translation file to the SD card's switch/ folder.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning

from . import infoscript
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS

TEXT_FILE = "Scripts/InfoScript2.txt"
SD_TARGET_ID = "openblack_sd"
SD_SUBFOLDER = "switch/openblack/game/Scripts"


class GameRules(BaseGameRules):
    """Black & White text table as one block of strings."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._save_copy: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Black & White (openBlack Switch port)"

    def get_file_formats(self) -> List[Any]:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".txt",), "bytes", "Black & White text table"), *DEFAULT_FORMATS]

    def includes_source_file(self, rel_path: str) -> bool:
        return rel_path.replace("\\", "/").lower() == TEXT_FILE.lower()

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": "base", "label": "Base game (PC data folder or Switch port SD folder)"}]

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "switch", "label": "Nintendo Switch (openBlack port)"}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        if os.path.basename(path).lower() != "infoscript2.txt":
            return None
        try:
            with open(path, "rb") as handle:
                head = handle.read(8192)
        except OSError:
            return None
        if not infoscript.looks_like_table(head):
            return None
        # The PC data folder holds the same file, so the platform is left for the user to pick.
        return {"role": "base", "platform": ""}

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{
            "id": SD_TARGET_ID,
            "label": f"openBlack SD card: {SD_SUBFOLDER}/InfoScript2.txt",
            "platforms": ["switch"],
            "kind": "files",
        }]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != SD_TARGET_ID:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        progress(10, "Reading the translation")
        data = build_sd_file(translation_dir, source_dir)
        if is_cancelled():
            return None
        target_dir = os.path.join(output_dir, *SD_SUBFOLDER.split("/"))
        os.makedirs(target_dir, exist_ok=True)
        target = os.path.join(target_dir, "InfoScript2.txt")
        temporary = target + ".tmp"
        with open(temporary, "wb") as handle:
            handle.write(data)
        os.replace(temporary, target)
        progress(100, "Done")
        return target

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        self._last_loaded = raw
        try:
            lines = infoscript.texts(raw)
        except (UnicodeDecodeError, ValueError) as error:
            log_debug(f"black_and_white: not a text table ({error})")
            return [[]], {"0": "ADD_TEXT"}
        return [lines], {"0": "ADD_TEXT"}

    def prepare_save_context(self, context) -> None:
        """The newest version gives the fields of each call; the translation copy (when it exists) comes first."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_copy = versions[0] if len(versions) > 1 else None

    def save_data_to_json_obj(self, data: List[List[str]], block_names: Dict[str, str]) -> Any:
        template = self._save_copy if self._save_copy is not None else self._save_source
        if template is None:
            template = self._last_loaded
        if template is None:
            return super().save_data_to_json_obj(data, block_names)
        lines = list(data[0]) if data else []
        expected = len(infoscript.keys(template))
        if len(lines) != expected:
            log_warning(f"black_and_white: text count changed ({len(lines)} for {expected}); file not saved")
            return template
        try:
            return infoscript.replace_texts(template, lines)
        except infoscript.InfoScriptError as error:
            log_warning(f"black_and_white: file not saved: {error}")
            return template


def build_sd_file(translation_dir: str, source_dir: str) -> bytes:
    """The translation file as the SD card needs it. It must hold the source's keys in the same order."""
    translation_path = os.path.join(translation_dir, *TEXT_FILE.split("/"))
    source_path = os.path.join(source_dir, *TEXT_FILE.split("/"))
    if not os.path.isfile(translation_path):
        raise ValueError(f"No translation file: {TEXT_FILE}")
    with open(translation_path, "rb") as handle:
        translated = handle.read()
    if os.path.isfile(source_path):
        with open(source_path, "rb") as handle:
            source_keys = infoscript.keys(handle.read())
        if infoscript.keys(translated) != source_keys:
            raise ValueError("The translation's ADD_TEXT keys differ from the source; the build stops")
    infoscript.texts(translated)  # raises when the bytes are not a text table
    return translated
