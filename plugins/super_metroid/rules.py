"""Super Metroid (SNES) through its PC port sm_rewrite: ``text.json`` of the workspace.

``1_unpack.bat`` (``_shared/scripts/zt/sm.py``) reads every text the game draws from tilemaps out of the ROM:
message boxes, file select and game over menus, the options screens, the pause map area names, the intro and the
credits. One group is one block; one item is one string (``\\n`` between the rows of a message box or the lines of
an intro page). Each letter is one 8-pixel cell, so a line holds ``width`` letters. Tiles that are not letters are
tags (``[press1]``, ``[#304B]``) and stay where they are. The game has capital letters only; ``2_build.bat`` writes
Ukrainian look-alikes (А, В, Е, І, ...) with the Latin tile and the other Ukrainian letters with the cells the font
has for them (the message-box font only). Saving writes the texts into the existing ``text.json`` by position.

Context comes from the port's C code (``port_context.py`` -> ``context.json``): the source lines and functions
that show an item; the intro pages are Samus's narration.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.utils import clean_spaces

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

FORMAT = "super-metroid-text/1"
CELL = 8
_TAG = re.compile(r"\[[^\[\]]+\]")
ROLES = {"Message boxes": "ItemGet", "File select and game over": "Menu", "Options": "Menu",
         "Pause map": "Menu", "Intro": "Narration", "Credits": "Credits"}


def parse_text_file(text: str) -> Dict[str, Any]:
    doc = json.loads(text)
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ValueError(f"not a Super Metroid text.json ({FORMAT})")
    return doc


def render_text_file(doc: Dict[str, Any]) -> str:
    """The workspace's own layout (zt/sm.py writes it the same way), so an unchanged save is the same file."""
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def cells(line: str) -> int:
    """Tilemap cells a line takes: one per letter and one per tag."""
    return len(_TAG.sub("#", line))


class GameRules(BaseGameRules):
    """Super Metroid (SNES), PC port sm_rewrite."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    show_spaces_as_dots_default = True
    game_name = "Super Metroid (PC port)"
    data_dir = os.path.dirname(os.path.abspath(__file__))

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._doc: Optional[Dict[str, Any]] = None
        self._save_doc: Optional[Dict[str, Any]] = None
        self._context_cache: Optional[Dict[str, Any]] = None

    def get_display_name(self) -> str:
        return self.game_name

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".json",), "text", "Super Metroid text.json")]

    # -- loading and saving ---------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, str):
            return super().load_data_from_json_obj(json_obj)
        doc = parse_text_file(json_obj)
        self._doc = doc
        blocks = [[str(item["text"]) for item in group["items"]] for group in doc["groups"]]
        return blocks, {str(i): group["name"] for i, group in enumerate(doc["groups"])}

    def prepare_save_context(self, context: Any) -> None:
        """Texts go into the existing file (the translation copy, else the source) by position."""
        self._save_doc = None
        for version in context.existing_versions():
            try:
                self._save_doc = parse_text_file(version.decode("utf-8"))
                break
            except (ValueError, UnicodeDecodeError):
                continue

    def save_data_to_json_obj(self, data: list, block_names: Optional[dict] = None) -> Any:
        base = self._save_doc or self._doc
        if base is None:
            raise ValueError("Super Metroid text.json: nothing loaded to save into")
        doc = json.loads(json.dumps(base))
        for group, texts in zip(doc["groups"], data):
            for item, text in zip(group["items"], texts):
                item["text"] = str(text)
        return render_text_file(doc)

    # -- items and context ---------------------------------------------------------------

    def _item(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        doc = self._doc
        try:
            return doc["groups"][block_idx]["items"][string_idx] if doc else {}
        except (IndexError, KeyError, TypeError):
            return {}

    def _group(self, block_idx: int) -> str:
        try:
            return self._doc["groups"][block_idx]["name"] if self._doc else ""
        except (IndexError, KeyError, TypeError):
            return ""

    def _context(self) -> Dict[str, Any]:
        if self._context_cache is None:
            path = os.path.join(self.data_dir, "context.json")
            try:
                with open(path, encoding="utf-8") as handle:
                    self._context_cache = json.load(handle)
            except (OSError, ValueError):
                self._context_cache = {}
        return self._context_cache

    def _entry(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        item_id = self._item(block_idx, string_idx).get("id")
        return self._context().get("items", {}).get(item_id, {}) if item_id else {}

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution"} if self._context().get("items") else set()

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return self._entry(block_idx, string_idx).get("speaker")

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        group = self._group(block_idx)
        role = ROLES.get(group)
        if not role:
            return {}
        result: Dict[str, Any] = {"content_role": role, "has_speaker": role == "Narration"}
        width = self._item(block_idx, string_idx).get("width")
        if width:
            result["role_instruction"] = (f"{group.upper()}: capital letters only, at most {width} letters per line; "
                                          "keep every [tag] where it is.")
        return result

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        entry = self._entry(block_idx, string_idx)
        result: Dict[str, Any] = {"scene": self._group(block_idx)}
        if entry.get("refs"):
            result["resource"] = entry["refs"][0]
            result["flow_ids"] = list(entry.get("functions", []))
        if entry.get("speaker"):
            result["candidate_actors"] = [entry["speaker"]]
        return result

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        entry = self._entry(block_idx, string_idx)
        if not entry.get("refs"):
            return None
        shown = ", ".join(f"{f} ({r})" for f, r in zip(entry.get("functions", []), entry["refs"]))
        return f"Shown by {shown} in the sm_rewrite PC port source."

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Items one function shows are translated together; else the group."""
        functions = self._entry(block_idx, string_idx).get("functions") or []
        return functions[0] if len(functions) == 1 else (self._group(block_idx) or None)

    # -- width and editing ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        item = self._item(block_idx, string_idx)
        if not item.get("width"):
            return None
        width = int(item["width"]) * CELL
        return {"max_width": width, "warn_width": width, "lines_per_page": int(item.get("lines") or 1)}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        return cells(text) * CELL

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""
