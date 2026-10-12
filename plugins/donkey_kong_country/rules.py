"""Donkey Kong Country (SNES, USA v1.0): ``text.json`` of the workspace.

``1_unpack.bat`` (``_shared/scripts/zt/dkc.py``) reads the English text strings out of the ROM: level and map names,
the Kong hints, the cast and credits. One group is one block; one item is one string. A string keeps the byte length
of its ROM slot, so a translated line must not be longer than ``max_bytes`` (the build refuses a longer one).
``2_build.bat`` writes the texts and the ``gfx`` sheets back into the ROM.
"""
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

FORMAT = "donkey-kong-country-text/1"


def parse_text_file(text: str) -> Dict[str, Any]:
    doc = json.loads(text)
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ValueError(f"not a Donkey Kong Country text.json ({FORMAT})")
    return doc


def render_text_file(doc: Dict[str, Any]) -> str:
    """The workspace's own layout (zt/dkc.py writes it the same way), so an unchanged save is the same file."""
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


class GameRules(BaseGameRules):
    """Donkey Kong Country (SNES), USA v1.0."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    show_spaces_as_dots_default = True
    game_name = "Donkey Kong Country (SNES)"
    data_dir = os.path.dirname(os.path.abspath(__file__))

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._doc: Optional[Dict[str, Any]] = None
        self._save_doc: Optional[Dict[str, Any]] = None

    def get_display_name(self) -> str:
        return self.game_name

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".json",), "text", "Donkey Kong Country text.json")]

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
            raise ValueError("Donkey Kong Country text.json: nothing loaded to save into")
        doc = json.loads(json.dumps(base))
        for group, texts in zip(doc["groups"], data):
            for item, text in zip(group["items"], texts):
                item["text"] = str(text)
        return render_text_file(doc)
