"""Ever Oasis plugin (3DS, EUR English): the GMSG v3 message file, the game font and the pictures with text.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it, ``_shared/scripts/zt/eo3ds.py``):

- ``romfs/data/Region_EU/English/main.gmsg`` -- every message of the game (names, menus, items, dialogue, 8 515
  messages) as one block. The game takes the folder from the console's language; the other languages' folders are
  not copied. An unedited message is written back byte for byte (``gmsg.py``); control codes are tags.
- ``romfs/data/Region_EU/main.gzf`` -- the game font, shared by every language (``font_sources.json``).
- ``romfs/data/Region_EU/English/<archive>.gar/<name>.ctxb`` -- the CTXB pictures of the English GAR archives
  (``texture_sources.json``); ``2_build.bat`` packs a changed one back into its archive.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import gmsg
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


class GameRules(BaseGameRules):
    """Ever Oasis (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[gmsg.Gmsg] = None
        self._ids: Dict[int, Optional[List[int]]] = {}

    def get_display_name(self) -> str:
        return "Ever Oasis"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".gmsg",), "bytes", "Grezzo GMSG"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._file = None
            return super().load_data_from_json_obj(json_obj)
        self._file = gmsg.Gmsg(bytes(json_obj))
        return [self._file.texts()], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = data[0] if data and isinstance(data[0], list) else []
        texts = [str(t) for t in texts] + self._file.texts()[len(texts):]
        return self._file.build(texts)

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from an existing copy (ids, flags, style rows): the newest that parses."""
        self._file = None
        if not str(getattr(context, "relative_path", "")).lower().endswith(".gmsg"):
            return
        for raw in context.existing_versions():
            try:
                self._file = gmsg.Gmsg(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"ever_oasis: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._file = None
        self._ids.clear()

    # -- where a string comes from -------------------------------------------------

    def _message_ids(self, block_idx: int) -> Optional[List[int]]:
        if block_idx in self._ids:
            return self._ids[block_idx]
        found: Optional[List[int]] = None
        try:
            pm = self.mw.project_manager
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            source = str(pm.project.blocks[project_idx].source_file)
            if source.lower().endswith(".gmsg"):
                found = gmsg.Gmsg(Path(pm.get_absolute_path(source)).read_bytes()).ids
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"ever_oasis: no GMSG file behind block {block_idx}: {error}")
        self._ids[block_idx] = found
        return found

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        ids = self._message_ids(block_idx)
        try:
            return f"Message {ids[int(string_idx)]:#x} in main.gmsg" if ids else None
        except (IndexError, TypeError, ValueError):
            return None

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return gmsg.TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
