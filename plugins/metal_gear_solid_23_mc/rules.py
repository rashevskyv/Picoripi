"""Metal Gear Solid 2 and 3 -- Master Collection Version (Switch and PC) plugin.

``1_unpack.bat`` (``_shared/scripts/zt/mgs23mc.py``) writes the game's English text into ``source/text/<group>.json``:
``{"format": "mgs23mc-text", "group": ..., "blocks": [{"name": <game file>, "lines": [...]}]}``, one block per game
file, each English string once per group (the codec, scenario, demo, movie and vox groups repeat many strings
across files). ``2_build.bat`` puts each translated line into every place its English string stands. This plugin
shows the blocks and writes the same document back with the translated lines.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug

FORMAT = "mgs23mc-text"
_KEEP = ("Keep the line breaks, the | marks (a pause between subtitle parts or the end of an item name) and the "
         "button symbols as they are.")
_ROLES = {
    "codec": ("Codec call", "A line of a codec (radio) conversation. " + _KEEP),
    "scenario": ("Game message", "An item description, tutorial or in-game message. " + _KEEP),
    "demo": ("Cutscene subtitle", "A subtitle of a cutscene. " + _KEEP),
    "movie": ("Cutscene subtitle", "A subtitle of a video or a codec scene. " + _KEEP),
    "vox": ("Voice subtitle", "A subtitle of a voiced radio or in-game line. " + _KEEP),
    "books": ("Master Book or Screenplay Book page", "A line of the Master Book or Screenplay Book pages (titles "
              "and text areas). " + _KEEP),
}


def is_text_document(value: Any) -> bool:
    return isinstance(value, dict) and value.get("format") == FORMAT and isinstance(value.get("blocks"), list)


class GameRules(BaseGameRules):
    """Metal Gear Solid 2 / 3 Master Collection: ``source/text/*.json`` text groups (see the module docstring)."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_doc: Optional[dict] = None
        self._save_doc: Optional[dict] = None

    def get_display_name(self) -> str:
        return "Metal Gear Solid 2 / 3 (Master Collection)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".json",), "json", "Metal Gear Solid 2 / 3 text groups"), *DEFAULT_FORMATS[1:]]

    def get_enter_char(self) -> str:
        return "\n"

    def get_shift_enter_char(self) -> str:
        return "\n"

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not is_text_document(json_obj):
            return super().load_data_from_json_obj(json_obj)
        self._last_doc = json_obj
        blocks = [[str(line) for line in block.get("lines", [])] for block in json_obj["blocks"]]
        names = {str(i): str(block.get("name", i)) for i, block in enumerate(json_obj["blocks"])}
        return blocks or [[]], names

    def prepare_save_context(self, context) -> None:
        """The document is written from its source version (block names and order)."""
        self._save_doc = None
        for version in reversed(list(context.existing_versions())):
            try:
                doc = json.loads(bytes(version).decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                continue
            if is_text_document(doc):
                self._save_doc = doc
                return

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        doc = self._save_doc if self._save_doc is not None else self._last_doc
        if doc is None or not data or not all(isinstance(block, list) for block in data):
            return super().save_data_to_json_obj(data, block_names)
        out = {key: value for key, value in doc.items() if key != "blocks"}
        out["blocks"] = []
        for index, block in enumerate(doc["blocks"]):
            lines = list(block.get("lines", []))
            if index < len(data):
                new = [str(line) for line in data[index]]
                lines = new + lines[len(new):]
            out["blocks"].append({"name": block.get("name", ""), "lines": lines})
        return out

    def reset_runtime_state(self) -> None:
        self._last_doc = self._save_doc = None

    # -- context -----------------------------------------------------------------

    def _block_place(self, block_idx: int) -> Optional[Tuple[str, str]]:
        """``(group, game file)`` of a block, or None."""
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            group = Path(str(block.source_file)).stem
            name = str(getattr(block, "name", "") or "")
            return group, name
        except (AttributeError, IndexError, KeyError, TypeError) as error:
            log_debug(f"metal_gear_solid_23_mc: no place for block {block_idx}: {error}")
            return None

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        place = self._block_place(block_idx)
        if place is None or place[0] not in _ROLES:
            return super().get_translation_context_for_string(block_idx, string_idx)
        role, instruction = _ROLES[place[0]]
        out = {"content_role": role, "role_instruction": instruction}
        if place[1]:
            out["where"] = place[1]
        return out
