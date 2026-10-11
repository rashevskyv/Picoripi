"""Stella Glow plugin (3DS, EUR English): string tables, event-flow dialogue, fonts and layout pictures.

The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``,
``_shared/scripts/zt/stella3ds.py``):

- ``romfs/param/*.str`` -- the string tables (items, skills, missions, shop and tavern lines, world map notes;
  one UTF-16 string per line, the game reads them by index). Internal names (``SWRD1A``) sit among them.
- ``romfs/event/*.flw`` -- the event flows: every dialogue string of a flow is one line. A line keeps the room
  of the original string (see ``flw.py``): a longer text is cut to it on saving, a shorter one is padded with
  spaces.
- ``romfs/font/*.bffnt`` -- the fonts (``font_sources.json``).
- ``romfs/<folder>/**/*.arc`` -- SARC layout archives with BFLIM pictures (``texture_sources.json``).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import flw
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager


class GameRules(BaseGameRules):
    """Stella Glow (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._parsed: Optional[Any] = None       # flw.Flow or flw.StrTable of the last load / save context
        self._rooms: Dict[int, Optional[List[int]]] = {}

    def get_display_name(self) -> str:
        return "Stella Glow"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".flw", ".str"), "bytes", "Stella Glow flow / string table"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    @staticmethod
    def _parse(raw: bytes):
        return flw.Flow(raw) if raw[:4] == flw.MAGIC else flw.StrTable(raw)

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._parsed = None
            return super().load_data_from_json_obj(json_obj)
        try:
            self._parsed = self._parse(bytes(json_obj))
        except (flw.FormatError, ValueError) as error:
            log_debug(f"stella_glow: not a flow or string table ({error})")
            self._parsed = None
            return [[]], {}
        return [list(self._parsed.strings)], {}

    def prepare_save_context(self, context) -> None:
        """A file is rebuilt from an existing copy (the translation, else the source): the newest that parses."""
        self._parsed = None
        for raw in context.existing_versions():
            try:
                self._parsed = self._parse(raw)
                return
            except (flw.FormatError, ValueError) as error:
                log_warning(f"stella_glow: cannot read {context.relative_path}: {error}; trying the next version")

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        parsed = self._parsed
        if parsed is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = [str(t) for t in (data[0] if data and isinstance(data[0], list) else [])]
        texts += parsed.strings[len(texts):]
        texts = texts[:len(parsed.strings)]
        if isinstance(parsed, flw.Flow):
            texts, cut = parsed.fit(texts)
            if cut:
                log_warning(f"stella_glow: {cut} texts are longer than the original strings and were cut")
        return parsed.build(texts)

    def reset_runtime_state(self) -> None:
        self._parsed = None
        self._rooms.clear()

    # -- where a string comes from -----------------------------------------------

    def _room_list(self, block_idx: int) -> Optional[List[int]]:
        if block_idx in self._rooms:
            return self._rooms[block_idx]
        found: Optional[List[int]] = None
        try:
            pm = self.mw.project_manager
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            source = str(pm.project.blocks[project_idx].source_file)
            if source.lower().endswith(".flw"):
                parsed = flw.Flow(Path(pm.get_absolute_path(source)).read_bytes())
                found = [parsed.room(i) for i in range(len(parsed.slots))]
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"stella_glow: no flow behind block {block_idx}: {error}")
        self._rooms[block_idx] = found
        return found

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        rooms = self._room_list(block_idx)
        try:
            room = rooms[int(string_idx)] if rooms else None
        except (IndexError, TypeError, ValueError):
            room = None
        if room is None:
            return {}
        return {"content_role": "Dialogue",
                "role_instruction": f"The text may have at most {room} characters (the room of the original line)."}

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
