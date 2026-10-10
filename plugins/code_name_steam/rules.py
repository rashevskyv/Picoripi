"""Code Name: S.T.E.A.M. plugin (3DS, EUR English): message archives, bfnt / CFNT fonts, BCH pictures.

The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``,
``_shared/scripts/zt/steam3ds.py``):

- ``romfs/mess/EU_English/*.bin`` -- the message archives decompressed (one block each): speech balloons, radio
  chatter, briefings, comics, library entries, menus, mission texts. The label of a message (``MID_...``) is its id.
  Icons and run-time values stay in the text as tags (``$Ap$<icon>,``, ``%USER``).
- ``romfs/fonts/*.bfnt`` and ``cbf_std.bcfnt`` -- the fonts (``font_sources.json``).
- ``romfs/arc/EU_English.arc/<folder>/<name>.bch`` -- the BCH models whose textures carry English words (title,
  menus, tutorial slides, chapter cards; ``texture_sources.json``). Saving writes the same paths into the
  translation folder; ``2_build.bat`` packs them again (LZ13, and the RASI archive around them).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from .archive import Archive, FormatError
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager


class GameRules(BaseGameRules):
    """Code Name: S.T.E.A.M. (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, Archive]]] = {}

    def get_display_name(self) -> str:
        return "Code Name: S.T.E.A.M."

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Message archive (mess/*/*.bin)"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [Archive(self._last_loaded).texts], {}
        except (FormatError, ValueError) as error:
            log_debug(f"code_name_steam: not a message archive ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        return Archive(source).build([str(s) for s in (data[0] if data else [])])

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._save_source = self._last_loaded = None

    # -- where a string comes from ---------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, Archive]]:
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = self.mw.project_manager
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            path = Path(pm.get_absolute_path(block.source_file))
            found = (str(block.source_file).replace("\\", "/"), Archive(path.read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"code_name_steam: no archive behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        located = self._locate(block_idx)
        if not located:
            return None
        try:
            return {"file": located[0], "label": located[1].labels[int(string_idx)]}
        except (IndexError, TypeError, ValueError):
            return None

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self.get_message_attributes(block_idx, string_idx)
        return f"Message {found['label']} in {Path(found['file']).name}" if found else None

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
