"""Metal Gear + Metal Gear 2 Master Collection: the English text of english.raw, one line per text unit.

``1_unpack.bat`` (``_shared/scripts/zt/mg12text.py``) writes ``source/text/mg1_english.json``:
``{"format": "mg12-text", "blocks": [{"name": "english.raw", "lines": [...]}]}``. A line is one dialogue record or one
menu string, decoded as Latin-1 so that every byte survives. ``2_build.bat`` writes each translated line back into the
same place, padded with spaces to its length budget. A line longer than its budget stops the build.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules

FORMAT = "mg12-text"


def is_text_document(value: Any) -> bool:
    return isinstance(value, dict) and value.get("format") == FORMAT and isinstance(value.get("blocks"), list)


class GameRules(BaseGameRules):
    """Metal Gear + Metal Gear 2 Master Collection: ``source/text/*.json`` text units (see the module docstring)."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_doc: Optional[dict] = None
        self._save_doc: Optional[dict] = None

    def get_display_name(self) -> str:
        return "Metal Gear + Metal Gear 2 (Master Collection)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".json",), "json", "Metal Gear + Metal Gear 2 text units"), *DEFAULT_FORMATS[1:]]

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
