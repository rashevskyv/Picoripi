"""Marvelous farm games on 3DS (EUR): Harvest Moon 3D: A New Beginning, Story of Seasons, Story of Seasons: Trio of
Towns (one lineage: XBB archives of ``PAPA`` record tables) and Harvest Moon 3D: The Tale of Two Towns (the older
DS engine: message packs with 16-bit codes and an 8x16 cell font).

The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``): one ``.papa`` file per text
table of every XBB archive (``romfs/Msg.xbb/<Table>.papa``: dialogue, events, tutorials, menus;
``romfs/GameData/<X>.xbb/<Table>.papa``: item, crop, animal, recipe, place and title names), or one ``.mes`` file
per entry of the two Tale of Two Towns packs (``romfs/mes_data.bin/NNNN.mes``, ``romfs/event_mes_data.bin/``).
Each file is one block; saving rebuilds the table (unchanged fields keep their bytes); ``2_build.bat`` puts the
tables back into their archives and packs. Fonts (``font_sources.json``) and the layout pictures
(``texture_sources.json``) are loose files or archive folders under the same paths.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import papa, ttt
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager

_SPEAKER_TABLE = re.compile(r"(?:^|/)(?:Talk|Event_RESIDENT|Event_GREETING|Event_LOVE|EV_LOVE)_([A-Z]+)")


def parse(raw: bytes):
    """The table of a source file: a ``papa.Table`` or a ``ttt.Table`` (None for a file that is neither)."""
    if raw[:4] == papa.MAGIC:
        return papa.Table(raw)
    try:
        table = ttt.Table(raw)
    except (ValueError, IndexError):
        return None
    return table if table.is_text() else None


class GameRules(BaseGameRules):
    """Harvest Moon 3D / Story of Seasons (3DS, European English)."""

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
        self._located: Dict[int, Optional[Tuple[str, List[str]]]] = {}

    def get_display_name(self) -> str:
        return "Harvest Moon 3D / Story of Seasons (3DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".papa",), "bytes", "PAPA text table (A New Beginning, Story of Seasons)"),
                FileFormat((".mes",), "bytes", "Message table (The Tale of Two Towns)"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution"}

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        table = parse(self._last_loaded)
        if table is None:
            log_debug("story_of_seasons_3ds: not a text table")
            return [[]], {}
        return [table.texts()], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        table = parse(source)
        if table is None:
            return source
        return table.build([str(s) for s in (data[0] if data else [])])

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._save_source = self._last_loaded = None

    # -- context ---------------------------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, List[str]]]:
        """``(relative source path, string ids)`` of a block."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            rel = str(block.source_file).replace("\\", "/")
            table = parse(Path(pm.get_absolute_path(block.source_file)).read_bytes())
            ids = table.ids() if isinstance(table, papa.Table) else [str(i) for i in range(len(table.texts()))]
            found = (rel, ids)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"story_of_seasons_3ds: no text file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._locate(block_idx)
        if not found or int(string_idx) >= len(found[1]):
            return None
        return {"file": found[0], "id": found[1][int(string_idx)]}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._locate(block_idx)
        if not found:
            return {}
        name = Path(found[0]).stem
        if "GameData" in found[0]:
            return {"role": "Name", "description": f"A name from the game's data table {name} (keep it short)."}
        if name.startswith(("Talk_", "Event", "EV_", "FREE_EV")):
            return {"role": "Dialogue", "description": "A line of dialogue or an event scene; <...> tags stay as they are."}
        return {"role": "Menu text", "description": "Menu, tutorial or system text."}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """The character a ``Talk_<NAME>`` / ``Event_RESIDENT_<NAME>`` table belongs to (A New Beginning lineage)."""
        found = self._locate(block_idx)
        match = _SPEAKER_TABLE.search(found[0]) if found else None
        return match.group(1).capitalize() if match else None

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._locate(block_idx)
        return found[0] if found else None

    # -- fonts and textures: only the entries the project's source folder has ---

    def _present(self, name: str) -> List[Dict[str, Any]]:
        sources = self._plugin_json_list(name)
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        root = (getattr(getattr(pm, "project", None), "metadata", None) or {}).get("source_path")
        if not root or not Path(root).is_dir():
            return sources
        return [s for s in sources if any(Path(root).glob(s["path"]))] or sources

    def get_font_sources(self) -> List[Dict[str, Any]]:
        return self._present("font_sources.json")

    def get_texture_sources(self) -> List[Dict[str, Any]]:
        return self._present("texture_sources.json")

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_default_script_name(self) -> Optional[str]:
        return "story_of_seasons_3ds_script.md"
