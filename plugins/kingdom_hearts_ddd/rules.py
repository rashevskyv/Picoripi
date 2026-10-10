"""Kingdom Hearts 3D: Dream Drop Distance plugin (3DS, EUR English): the game's message files, its bitmap fonts and
the pictures that depend on the language.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it), at the game's romfs paths
plus the member's language folder (the game keeps its files in ``.rbin`` archives, one file of each language):

- ``romfs/message/en/<name>.ctd`` -- the English message files (``ctXXnnn.ctd``: menus, reports, events of every
  world, missions). One block per file, one string per message; ``{UE026}`` stands for a private-area icon or
  colour character (``ctd.py``). An unedited file is written back byte for byte.
- ``romfs/font/*.bcfnt`` -- the game's CFNT fonts (``font_sources.json``).
- ``romfs/menu/en/*.ctt`` -- the English ``CTRT`` pictures of the menus and help pages (``texture_sources.json``).
"""
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import ctd
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

# What a message file holds, by the two letters after "ct".
ROLES = {"mn": "Menu text", "rp": "Report (Chronicles) text", "it": "Item names and descriptions",
         "00": "System messages"}


class GameRules(BaseGameRules):
    """Kingdom Hearts 3D: Dream Drop Distance (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._ctd: Optional[ctd.Ctd] = None
        self._members: Dict[int, Tuple[Optional[str], Optional[ctd.Ctd]]] = {}

    def get_display_name(self) -> str:
        return "Kingdom Hearts 3D: Dream Drop Distance"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".ctd",), "bytes", "DDD message file"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._ctd = None
            return super().load_data_from_json_obj(json_obj)
        self._ctd = ctd.Ctd(json_obj)
        return [[ctd.to_editor(text) for text in self._ctd.texts]], {}

    def prepare_save_context(self, context) -> None:
        """A file is rebuilt from the newest version that parses (ids and layouts stay as they were)."""
        self._ctd = None
        if not str(getattr(context, "relative_path", "")).lower().endswith(".ctd"):
            return
        for raw in context.existing_versions():
            try:
                self._ctd = ctd.Ctd(raw)
                return
            except (ValueError, IndexError, struct.error) as error:
                log_warning(f"kingdom_hearts_ddd: cannot read {context.relative_path}: {error}; trying the next version")

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._ctd is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = data[0] if data and isinstance(data[0], list) else []
        new = []
        for index, original in enumerate(self._ctd.texts):
            shown = texts[index] if index < len(texts) else None
            if shown is None or str(shown) == ctd.to_editor(original):
                new.append(original)
            else:
                new.append(ctd.from_editor(str(shown)))
        return self._ctd.build(new)

    def reset_runtime_state(self) -> None:
        self._ctd = None
        self._members.clear()

    # -- where a string comes from -----------------------------------------------

    def _member(self, block_idx: int) -> Tuple[Optional[str], Optional[ctd.Ctd]]:
        if block_idx in self._members:
            return self._members[block_idx]
        found: Tuple[Optional[str], Optional[ctd.Ctd]] = (None, None)
        try:
            pm = self.mw.project_manager
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            source = str(pm.project.blocks[project_idx].source_file)
            if source.lower().endswith(".ctd"):
                found = (Path(source).as_posix(), ctd.Ctd(Path(pm.get_absolute_path(source)).read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"kingdom_hearts_ddd: no message file behind block {block_idx}: {error}")
        self._members[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        rel_path, parsed = self._member(block_idx)
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return None
        if parsed is None or not 0 <= index < len(parsed.ids):
            return None
        stem = Path(rel_path).stem
        world = stem[2:4]
        return {"path": rel_path, "file": Path(rel_path).name, "id": f"{parsed.ids[index]:08X}", "world": world,
                "role": ROLES.get(world) or f"Messages of group {world}"}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        return {"content_role": f"{found['role']} ({found['file']})", "has_speaker": False}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        return {"resource": found["path"], "label": found["id"]}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        return f"Message {found['id']} in {found['file']}" if found else None

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return f"Private-area character {str(tag).strip('{}')[1:]}: a button icon, a colour switch or a variable of the game"

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
