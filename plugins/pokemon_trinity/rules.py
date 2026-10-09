"""Pokémon Scarlet/Violet (+ The Teal Mask, The Indigo Disk) and Pokémon Legends: Z-A (+ Mega Dimension) (Switch).

Both run on Game Freak's Trinity engine. The workspace's ``1_unpack.bat`` (``_shared/scripts/zt/trinity.py``)
takes from the game's packs (``arc/data.trpfs``) into the source folder, at the game's paths:
the English text ``message/dat/English/{common,script}/*.dat`` (Legends: Z-A: ``ik_message/dat/English/...``),
one project block per file (``gfmsg``: every menu, name, Pokédex entry, battle and story line, DLC included);
the fonts (``.bfotf`` Switch OpenType, ``.bffnt``); the English layout archives (``*_eng.arc``: SARC with BFLYT and
the BNTX text pictures: title logo, menus). ``2_build.bat`` writes changed files into a LayeredFS mod and a
``data.trpfd`` that no longer points the game to the packed originals.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.tag_manager import GenericTagManager

from . import gfmsg
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS


class TagManager(GenericTagManager):
    """Variables and grammar branches as ``{PAGE}``, ``{VAR 0102 0000}``, ``{GENDER 00FF|he|she}``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {gfmsg.TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and gfmsg.TAG_RE.fullmatch(tag_to_check) is not None


class GameRules(BaseGameRules):
    """Pokémon Scarlet/Violet, Pokémon Legends: Z-A (Nintendo Switch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[bytes] = None      # the last message file loaded
        self._base: Optional[bytes] = None        # the message file a save writes over (line flags)

    def get_display_name(self) -> str:
        return "Pokémon Scarlet/Violet, Legends: Z-A (Switch)"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".dat",), "bytes", "Game Freak messages (gfmsg)")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if not gfmsg.is_gfmsg(raw):
            return [[]], {}
        self._loaded = raw
        return [[gfmsg.to_editor(units) for units, _flags in gfmsg.read(raw)]], {}

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._base = next((raw for raw in context.existing_versions() if gfmsg.is_gfmsg(raw)), None)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        base = self._base if self._base is not None else self._loaded
        if base is None:
            return super().save_data_to_json_obj(data, block_names)
        old = gfmsg.read(base)
        texts = [text for block in data for text in block]
        if len(texts) != len(old):
            raise ValueError(f"the message file has {len(old)} lines, the project {len(texts)}")
        return gfmsg.write([(gfmsg.from_editor(str(text)), flags) for text, (_units, flags) in zip(texts, old)])

    def reset_runtime_state(self) -> None:
        self._loaded, self._base = None, None

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
