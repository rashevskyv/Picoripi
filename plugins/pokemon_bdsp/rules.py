"""Pokémon Brilliant Diamond / Shining Pearl plugin: the English message tables unpacked from the Unity bundles.

A project's source folder is the workspace's ``source\\`` (``1_unpack.bat``, ``_shared\\scripts\\zt\\pokemon_bdsp.py``):
``message\\english_<table>.bdmsg`` (a message table as JSON, see ``msg.py``), ``font\\<bundle>\\`` (TextMesh Pro
SDF fonts: ``<asset>.json`` + ``<asset>.png``, and the font files of the dynamic fallback) and
``texture\\<bundle>\\*.png`` (the English picture bundles: logos, menu words). Each table is one block, each
label one string. ``2_build.bat`` puts every edited file back into its bundle, for both games.
"""
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.utils import clean_spaces

from . import msg
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

_GROUPS = {1: "a name or word the game fills in", 2: "a number the game fills in",
           19: "a word form the game picks (by gender or number); the forms follow after |"}


class GameRules(BaseGameRules):
    """Pokémon Brilliant Diamond / Shining Pearl (Switch, update 1.3.0)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._table: Optional[Tuple[Dict[str, Any], List[int]]] = None

    def get_display_name(self) -> str:
        return "Pokémon Brilliant Diamond / Shining Pearl"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".bdmsg",), "bytes", "Message tables")]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        table, indices, texts = msg.load_table(json_obj)
        self._table = (table, indices)
        return [texts], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._table is None:
            return super().save_data_to_json_obj(data, block_names)
        table, indices = self._table
        texts = list(data[0]) if data and isinstance(data[0], list) else []
        texts += [None] * (len(indices) - len(texts))
        return msg.save_table(table, indices, texts)

    def prepare_save_context(self, context) -> None:
        """A table is rebuilt from the existing file: load the newest version that parses."""
        for raw in context.existing_versions():
            try:
                table, indices, _texts = msg.load_table(raw)
            except (ValueError, KeyError, IndexError):
                continue
            self._table = (table, indices)
            return

    def reset_runtime_state(self) -> None:
        self._table = None

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        tag = str(tag)
        if tag.startswith("{tag:"):
            try:
                data = msg.parse_tag(tag)
            except ValueError as error:
                return str(error)
            return f"Game tag (argument {data['tagIndex']}): {_GROUPS.get(data['groupID'], 'game data')}"
        return {"{scroll}": "Wait for the button, then scroll one line", "{clear}": "Wait for the button, then a new window"
                }.get(tag, "Wait (seconds)" if tag.startswith("{wait:") else "")

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
