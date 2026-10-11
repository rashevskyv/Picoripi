"""Paper Mario: Sticker Star plugin (3DS, EUR English): the game's MSBT text, its two bitmap fonts and the pictures
that depend on the language.

A project's source folder is the workspace's ``source`` tree (``1_unpack.bat`` fills it), at the game's romfs paths:

- ``romfs/messages/EU_English/*.msbt`` -- the 46 English message files (dialogue per stage ``stgW_L``, ``global``,
  town files, the sticker museum, credits). One block per file, one string per message; an unedited file is
  written back byte for byte (``plugins.common.msbt``).
- ``romfs/Font/pop_120px.bcfnz`` and ``pop_240px.bcfnz`` -- the two CFNT fonts, unpacked from the game's BLZ
  packing (``font_sources.json``).
- ``romfs/Lang/EUR_en.bin/*.bcres`` (the logo, Press Start, game over...), ``romfs/NWTexture/EUR_en.bin/``,
  ``romfs/Effect/main/EUR_en.bctez``, ``romfs/Graphics/**`` -- CGFX pictures (``texture_sources.json``).
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

# What a message file holds, by its file name.
ROLES = {"global": "Menus, items, shops, system messages", "global_event": "Event messages",
         "Enemy": "Enemy names and battle text", "SealHelp": "Sticker descriptions", "SealMuseum": "Sticker museum",
         "StaffCredit": "Staff credits", "intermission": "Chapter intermission text",
         "worldmap": "World map text", "porttown_harbor": "Port Prisma harbour"}


class GameRules(BaseGameRules):
    """Paper Mario: Sticker Star (Nintendo 3DS, European English)."""

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
        return "Paper Mario: Sticker Star"

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
                log_warning(f"paper_mario_ss: cannot read {context.relative_path}: {error}; trying the next version")

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
            log_debug(f"paper_mario_ss: no MSBT behind block {block_idx}: {error}")
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
        role = ROLES.get(stem)
        if role is None and stem.startswith("stg"):
            role = "Dialogue of stage " + stem[3:].replace("_", "-")
        elif role is None and stem.startswith("town"):
            role = f"Town text ({stem})"
        return {"path": rel_path, "file": Path(rel_path).name, "label": msbt.labels.get(index, ""), "role": role}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found or not found["role"]:
            return {}
        return {"content_role": found["role"], "has_speaker": found["role"].startswith(("Dialogue", "Town"))}

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
