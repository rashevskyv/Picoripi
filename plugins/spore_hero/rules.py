"""Spore Hero (Wii, Europe RQOP69) plugin: the English text, the system messages and the HOME Menu messages.

``game/localization/localization/ENG_US.rpk`` (decompressed by the workspace's ``1_unpack.bat``) holds every
English string of the game -- menus, quests, dialogue, creature and part names, credits headings, the disc and
save messages (``locbin``): 2,285 strings, shown in the order they were written, a hundred to a block. In a
string ``&`` breaks the line, ``<c>...</c>`` colours, ``[PLAYER_NAME]`` is the creature's name and ``\\[A]``-style
codes are button and item icons. A letter the fonts have no glyph for is written as the character of its glyph
slot in the project's ``translation_map.json`` (the Font Editor's translation map), else it gets a byte of its
own. ``sys/main.dol`` keeps the disc and Wii memory messages the game shows before its text is loaded (two English
sets, each message within its own bytes); ``Game.rpk/home*.csv`` are the Wii HOME Menu messages. The workspace's
``2_build.bat`` packs everything back into the disc.
"""
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.tag_manager import GenericTagManager
from plugins.common.wii_home_menu import HomeCsv, is_home_csv

from . import locbin
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

BLOCK = 100
TAG_PATTERN = r"\\\[[A-Za-z0-9+\-]+\]|</?c>|\[PLAYER_NAME(?:_\d)?\]"


class TagManager(GenericTagManager):
    """The game's codes: icons ``\\[Moon]``, colour ``<c>``/``</c>``, ``[PLAYER_NAME]``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_PATTERN}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        import re
        return isinstance(tag_to_check, str) and re.fullmatch(TAG_PATTERN, tag_to_check) is not None


class GameRules(BaseGameRules):
    """Spore Hero (Wii, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._kind: Optional[str] = None            # "text", "dol" or "home" -- what the last load was
        self._loaded: Optional[bytes] = None
        self._base: Optional[bytes] = None          # the file a save writes over
        self.translation_map: Dict[str, str] = {}   # letter -> font slot (the project's translation_map.json)

    def load_translation_map(self) -> None:
        """The project's ``translation_map.json`` (the Font Editor writes it): letter -> the glyph's character."""
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        path = os.path.join(getattr(pm, "project_dir", "") or "", "translation_map.json")
        try:
            raw = json.loads(open(path, encoding="utf-8").read()) if os.path.isfile(path) else {}
        except (OSError, ValueError):
            raw = {}
        self.translation_map = {k: v for k, v in raw.items() if isinstance(v, str) and len(k) == 1 and len(v) == 1}

    def _shown(self) -> Dict[str, str]:
        """Font slot -> letter; a look-alike slot (a Latin letter) stays itself."""
        return {v: k for k, v in self.translation_map.items() if not (v.isascii() and v.isalnum())}

    def get_display_name(self) -> str:
        return "Spore Hero"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".rpk",), "bytes", "Spore Hero text (decompressed ENG_US.rpk)"),
                FileFormat((".dol",), "bytes", "Spore Hero main.dol system messages"),
                FileFormat((".csv",), "bytes", "Wii HOME Menu messages")]

    @staticmethod
    def _kind_of(raw: bytes) -> Optional[str]:
        if is_home_csv(raw):
            return "home"
        if locbin.is_dol(raw):
            return "dol"
        if locbin.is_package(raw):
            return "text"
        return None

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._kind = None
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        self._kind, self._loaded = self._kind_of(raw), raw
        if self._kind == "home":
            return [HomeCsv(raw).messages], {"0": "HOME Menu"}
        if self._kind == "dol":
            return locbin.dol_texts(raw), {str(i): name for i, (_a, _b, name) in enumerate(locbin.DOL_SETS)}
        if self._kind == "text":
            self.load_translation_map()
            texts = locbin.texts(raw, self._shown())
            blocks = [texts[i:i + BLOCK] for i in range(0, len(texts), BLOCK)]
            return blocks, {str(i): f"Strings {i * BLOCK + 1}-{i * BLOCK + len(b)}" for i, b in enumerate(blocks)}
        return [[]], {}

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._base = None
        for raw in context.existing_versions():
            if self._kind_of(raw) == self._kind:
                self._base = raw
                return

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        base = self._base if self._base is not None else self._loaded
        if self._kind is None or base is None:
            return super().save_data_to_json_obj(data, block_names)
        if self._kind == "home":
            home = HomeCsv(base)
            texts = data[0] if data and isinstance(data[0], list) else []
            old = home.messages
            return home.build([str(texts[i]) if i < len(texts) and texts[i] is not None else old[i]
                               for i in range(len(old))])
        if self._kind == "dol":
            return locbin.build_dol(base, [[str(t) for t in block] for block in data])
        self.load_translation_map()
        return locbin.build(base, [str(text) for block in data for text in block], self.translation_map, self._shown())

    def reset_runtime_state(self) -> None:
        self._kind, self._loaded, self._base = None, None, None

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
