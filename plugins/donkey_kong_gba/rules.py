"""Donkey Kong Country 3 (GBA, Europe): ``text.json`` of the workspace.

``1_unpack.bat`` (``_shared/scripts/zt/dkc3gba.py``) reads every text string the ROM points to, one group per run of
strings packed together in the ROM. One item is one string; its ``id`` is the ROM offset and must stay. Bytes that
are not ASCII are ``{XX}`` tags, ``\\n`` is a line feed. Saving writes the texts into the existing ``text.json``
by position, so the other keys of an item (``id``, ``candidate``) stay.
"""
import json
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.utils import clean_spaces

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

FORMAT = "dkc3-gba-text/1"


def parse_text_file(text: str) -> Dict[str, Any]:
    doc = json.loads(text)
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ValueError(f"not a Donkey Kong Country 3 text.json ({FORMAT})")
    return doc


def render_text_file(doc: Dict[str, Any]) -> str:
    """The layout zt/dkc3gba.py writes, so an unchanged save is the same file."""
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


class GameRules(BaseGameRules):
    """Donkey Kong Country 3 (GBA, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True
    game_name = "Donkey Kong Country 3 (GBA)"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._doc: Optional[Dict[str, Any]] = None
        self._save_doc: Optional[Dict[str, Any]] = None

    def get_display_name(self) -> str:
        return self.game_name

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".json",), "text", "Donkey Kong Country 3 text.json")]

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
            raise ValueError("Donkey Kong Country 3 text.json: nothing loaded to save into")
        doc = json.loads(json.dumps(base))
        for group, texts in zip(doc["groups"], data):
            for item, text in zip(group["items"], texts):
                item["text"] = str(text)
        return render_text_file(doc)

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""
