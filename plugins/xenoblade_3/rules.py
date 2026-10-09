"""Xenoblade Chronicles 3 + the 4 DLC waves incl. Future Redeemed (Switch).

The workspace's ``1_unpack.bat`` (``_shared/scripts/zt/xc3.py``) takes from the game's archives (``bf3.ard``
and the DLC ``bf3_dlc0N.ard``, newest copy first) into the source folder, at the archive paths: the English text
tables ``bdat/gb/game/*.bdat`` (menus, system, battle, quests) and ``bdat/gb/evt/<kind>/*.bdat`` (story, NPC
talk, quests; one project block per file, every text cell of its tables is a line); the fonts
``menu/font/*.wifnt`` (LAFT); the layouts ``menu/image/*.wilay`` with text pictures (the title logo
``mnu001_cont01_en``, menus) and ``menu/image/gb/*.wilay`` (tutorial pictures, JPEG). ``2_build.bat`` writes
changed files as loose romfs files of a LayeredFS mod with each archive's index patched around them.

Tags are the game's ``[ML:...]`` / ``[System:...]`` codes inside the text.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common import bdat
from plugins.common.tag_manager import GenericTagManager

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

TAG_RE = re.compile(r"\[(?:ML|System):[^\[\]]*\]")


class TagManager(GenericTagManager):
    """``[ML:Feeling kind=Anger ]``, ``[System:Color ...]``, ``[ML:Dash ]`` and the other bracket codes."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None


class GameRules(BaseGameRules):
    """Xenoblade Chronicles 3 (Nintendo Switch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[bytes] = None      # the last table file loaded
        self._base: Optional[bytes] = None        # the table file a save writes over

    def get_display_name(self) -> str:
        return "Xenoblade Chronicles 3 (Switch)"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".bdat",), "bytes", "Monolith Soft BDAT tables")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if not bdat.is_bdat(raw):
            return [[]], {}
        self._loaded = raw
        return [bdat.read(raw)], {}

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._base = next((raw for raw in context.existing_versions() if bdat.is_bdat(raw)), None)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        base = self._base if self._base is not None else self._loaded
        if base is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = [str(text) for block in data for text in block]
        count = len(bdat.read(base))
        if len(texts) != count:
            raise ValueError(f"the table file has {count} text cells, the project {len(texts)}")
        return bdat.write(base, texts)

    def reset_runtime_state(self) -> None:
        self._loaded, self._base = None, None

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
