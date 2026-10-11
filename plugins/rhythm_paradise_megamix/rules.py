"""Rhythm Paradise Megamix plugin (3DS, EUR English): the game's MSBT text, its bitmap fonts and the pictures that
depend on the language.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it). The game keeps its files
in ``.zlib`` archives (a big-endian size and a zlib stream around a SARC); the unpack writes each as a folder of
members at the path a LayeredFS mod replaces one member with (``2_build.bat`` packs the archive again):

- ``romfs/EUENmessage/pajama.zlib/arc/*.msbt`` -- the 18 English message files: the rhythm games' texts per
  origin (``ctr``, ``agb``, ``rvl``, ``ntr`` and their ``*_result`` files), the cafe (``coffee``), the map, the
  treasure and bonus shops, the remix menu and the game list. ``arc/pajama.msbp`` (the message project) names
  the control tags (``msbp.json``). An unedited file is written back byte for byte (``plugins.common.msbt``).
- ``romfs/**/font/*.bffnt`` -- the ten bitmap fonts (``font_sources.json``); a font several archives hold with
  the same bytes is written once and the build puts the translation into all of them.
- ``romfs/EUENlayout/**/timg/*.bflim``, ``romfs/EUENcellanim/**/*.ctpk`` and ``romfs/EUENmodel/*.cgfx`` -- the
  English pictures (``texture_sources.json``).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.msbt import Msbt
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import tags
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

# What a file holds, by its name.
ROLES = {
    "ctr": "Rhythm game text (3DS originals)", "ctr_result": "Rhythm game result comments (3DS originals)",
    "agb": "Rhythm game text (GBA games)", "agb_result": "Rhythm game result comments (GBA games)",
    "rvl": "Rhythm game text (Wii games)", "rvl_result": "Rhythm game result comments (Wii games)",
    "ntr": "Rhythm game text (DS games)", "ntr_result": "Rhythm game result comments (DS games)",
    "remix": "Remix menu text", "remix_result": "Remix result comments", "coffee": "Cafe conversation and menu text",
    "map": "Overworld conversation and menu text", "treasure": "Treasure game and shop text",
    "bonus": "Bonus content text (items, music, games)", "game_info": "Game descriptions and ranks",
    "common": "Common menu and system text", "layout": "Layout labels", "debug_menu": "Debug menu (not shown)"}


class GameRules(BaseGameRules):
    """Rhythm Paradise Megamix (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._msbt: Optional[Msbt] = None
        self._members: Dict[int, Tuple[Optional[str], Optional[Msbt]]] = {}

    def get_display_name(self) -> str:
        return "Rhythm Paradise Megamix"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msbt",), "bytes", "MSBT"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._msbt = None
            return super().load_data_from_json_obj(json_obj)
        msbt = Msbt(json_obj)
        self._msbt = msbt
        return [[tags.to_editor(tokens, msbt.little) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._msbt is None:
            return super().save_data_to_json_obj(data, block_names)
        msbt = self._msbt
        texts = data[0] if data and isinstance(data[0], list) else []
        rebuilt = []
        for index, original in enumerate(msbt.messages):
            text = texts[index] if index < len(texts) else None
            if text is None or text == tags.to_editor(original, msbt.little):
                rebuilt.append(original)
            else:
                rebuilt.append(tags.from_editor(str(text), msbt.little))
        return msbt.build(rebuilt)

    def prepare_save_context(self, context) -> None:
        """An MSBT is rebuilt from the existing file (labels, attributes): load the newest that parses."""
        self._msbt = None
        if not str(getattr(context, "relative_path", "")).lower().endswith(".msbt"):
            return
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"rhythm_paradise_megamix: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._msbt = None
        self._members.clear()

    # -- where a string comes from -----------------------------------------------

    def _member(self, block_idx: int) -> Tuple[Optional[str], Optional[Msbt]]:
        if block_idx in self._members:
            return self._members[block_idx]
        found: Tuple[Optional[str], Optional[Msbt]] = (None, None)
        try:
            pm = self.mw.project_manager
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            source = str(pm.project.blocks[project_idx].source_file)
            if source.lower().endswith(".msbt"):
                found = (Path(source).as_posix(), Msbt(Path(pm.get_absolute_path(source)).read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"rhythm_paradise_megamix: no MSBT behind block {block_idx}: {error}")
        self._members[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        rel_path, msbt = self._member(block_idx)
        try:
            index = int(string_idx)
        except (TypeError, ValueError):
            return None
        if msbt is None or not 0 <= index < len(msbt.messages):
            return None
        stem = Path(rel_path).stem
        return {"path": rel_path, "file": Path(rel_path).name, "label": msbt.labels.get(index, ""),
                "role": ROLES.get(stem)}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found or not found["role"]:
            return {}
        return {"content_role": found["role"], "has_speaker": False}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        return {"resource": found["path"], "label": found["label"]}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        return f"Message {found['label']} in {found['file']}"

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return tags.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
