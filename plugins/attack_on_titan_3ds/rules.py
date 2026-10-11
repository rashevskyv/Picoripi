"""Attack on Titan: Humanity in Chains plugin (3DS; Spike Chunsoft engine): the text file and the pictures.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it): the game's files are
loose in the RomFS, so a mod replaces whole files.

- ``romfs/_catfiles_lists/system.cf`` -- all the game's text: 5,501 UTF-16 strings (menus, mission texts, the
  story's page-by-page narration; ``@`` ends a page). The strings are written back **in place**: a translation must
  not be longer than the original string (``cf``).
- ``romfs/**/*.ctpk`` (``texture_sources.json``, format ``ctpk``) -- the staff roll, signboards, loading pictures and
  battle pictures; the UI layouts' ``.rhg`` pictures are not opened.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import cf
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


class GameRules(BaseGameRules):
    """Attack on Titan: Humanity in Chains (Nintendo 3DS, English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._file: Dict[int, Tuple[Optional[str], Optional[cf.SystemCf]]] = {}

    def get_display_name(self) -> str:
        return "Attack on Titan: Humanity in Chains"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".cf",), "bytes", "Spike Chunsoft catalogue file (system text)"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [list(cf.SystemCf(self._last_loaded).texts)], {}
        except cf.FormatError as error:
            log_debug(f"attack_on_titan_3ds: not the system text file ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        return cf.SystemCf(source).build([str(s) for s in (data[0] if data else [])])

    def reset_runtime_state(self) -> None:
        self._file.clear()
        self._save_source = self._last_loaded = None

    # -- where a string comes from -----------------------------------------------

    def _located(self, block_idx: int) -> Tuple[Optional[str], Optional[cf.SystemCf]]:
        if block_idx in self._file:
            return self._file[block_idx]
        found: Tuple[Optional[str], Optional[cf.SystemCf]] = (None, None)
        try:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            found = (str(block.source_file).replace("\\", "/"),
                     cf.SystemCf(Path(pm.get_absolute_path(block.source_file)).read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"attack_on_titan_3ds: no system file behind block {block_idx}: {error}")
        self._file[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        path, system = self._located(block_idx)
        if system is None:
            return None
        try:
            offset, room = system.spans[int(string_idx)]
        except (IndexError, ValueError, TypeError):
            return None
        return {"file": path, "offset": f"{offset:06X}", "max_characters": room // 2}

    # -- editor ----------------------------------------------------------------

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
