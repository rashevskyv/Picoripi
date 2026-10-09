"""Castlevania: The Dracula X Chronicles (PSP, English, ULKS-46155) plugin: remake dialogue, save strings, SotN text.

The project's source folder is the workspace's ``source`` (``1_unpack.bat``):

- ``remake/text/stdNN.txt`` -- the English dialogue of the 2.5D Rondo of Blood remake (one per event pack);
- ``remake/program/BOOT.BIN`` -- the program; only its English save-data strings open as text;
- ``sotn/PSPBIN/*.bin`` -- the PSP overlays of Symphony of the Night: menus, item / enemy / spell names and
  descriptions (``dra.bin``), the dialogue of each stage and the ending texts (``sel.bin``).

The fonts (``font_sources.json``) and the text pictures of the remake, the PC Engine Rondo of Blood, Symphony of
the Night and Peke (``texture_sources.json``) live under the same folder. See ``text.py`` for the byte formats.
"""
from typing import Any, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_warning

from . import text
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

ELF = b"\x7fELF"


class GameRules(BaseGameRules):
    """Castlevania: The Dracula X Chronicles (PSP, USA)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_loaded: Optional[bytes] = None
        self._save_source: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Castlevania: The Dracula X Chronicles"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".txt", ".bin"), "bytes", "Castlevania: The Dracula X Chronicles text"),
                *[f for f in DEFAULT_FORMATS if ".txt" not in f.extensions]]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[list, dict]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        if data[:4] == text.OVERLAY_MAGIC:
            return [text.overlay_texts(data)], {}
        if data[:4] == ELF:
            return [text.boot_texts(data)], {}
        return [text.std_lines(data)], {}

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        texts: List[Optional[str]] = list(data[0]) if data else []
        missing: Set[str] = set()
        too_long: List[str] = []
        if source[:4] == text.OVERLAY_MAGIC:
            out = text.overlay_build(source, texts, missing, too_long)
        elif source[:4] == ELF:
            out = text.boot_build(source, texts, too_long)
        else:
            out = text.std_build(source, texts, missing)
        if missing:
            log_warning("castlevania_dxc: the game cannot store these characters, they were written as '?': "
                        + "".join(sorted(missing)))
        for line in too_long:
            log_warning(f"castlevania_dxc: the text does not fit its place in the file and was cut: {line!r}")
        return out
