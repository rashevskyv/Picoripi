"""Xenoblade Chronicles (Wii, USA) and Xenoblade Chronicles 3D (New 3DS, EUR): one plugin, one translation.

The workspace's ``1_unpack.bat`` (``_shared/scripts/zt/xcwii.py`` for the Wii, ``zt/xc3d.py`` for the 3DS port)
puts the English BDAT table files into the source folder: ``bdat/bdat_common.bin`` (120 tables: menus, items,
arts, skills, enemies, NPC and place names, system messages, battle chatter), ``bdat/common/*.bdat`` (quests,
item and arts descriptions, tutorials, skill trees, achievements, story log), ``bdat/map/*.bdat`` (NPC
auto-talk and trade talk, gimmick messages per map) and ``bdat/code_mes_en.bdat`` (the disc messages of
``main.dol``). Each file opens as one block per table that has text cells (``plugins/common/bdat_wii``: the
Wii tables are big-endian, the 3DS ones little-endian; the module reads the byte order from the file). The
Wii HOME Menu text is ``hbm/hbm.arc/hbm/home.csv`` (``plugins/common/wii_home_menu``). Fonts are NW4R
``RFNA`` archived fonts (``brfnt`` format of the Font Editor); pictures are TPL files of the menu layouts.

Tags are the game's ``<...>`` codes (``<n>`` line break in talk text, ``<col=s2>``, ``<wait=key>``, ``<p>``,
``<type=anger>``, ``<trust=...>``); menu and description text breaks lines with ``@``. Both are kept as they are.
Cutscenes of the Wii game have no subtitles, so no event text exists on the disc.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common import bdat_wii as bdat
from plugins.common.tag_manager import GenericTagManager
from plugins.common.wii_home_menu import HomeCsv, is_home_csv

from . import sbscript
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

TAG_RE = re.compile(r"<[^<>]+>")


class TagManager(GenericTagManager):
    """``<n>``, ``<col=s2>``, ``<col=def3>``, ``<wait=key>``, ``<p>``, ``<type=anger>``, ``<trust=f:13:20>``..."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None


def _blocks(raw: bytes) -> List[Tuple[str, List[str]]]:
    """The tables that have text cells (the project shows only those)."""
    return [(name, texts) for name, texts in bdat.read(raw) if texts]


class GameRules(BaseGameRules):
    """Xenoblade Chronicles (Wii / New 3DS)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "angle"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[bytes] = None      # the last table file loaded
        self._base: Optional[bytes] = None        # the table file a save writes over
        self._home: Optional[HomeCsv] = None

    def get_display_name(self) -> str:
        return "Xenoblade Chronicles (Wii / 3DS)"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".bdat", ".bin"), "bytes", "Monolith Soft BDAT tables"),
                FileFormat((".sb",), "bytes", "Xenoblade scripts (SB)"),
                FileFormat((".csv",), "bytes", "Wii HOME Menu text")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        self._home = None
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if is_home_csv(raw):
            self._home = HomeCsv(raw)
            return [self._home.messages], {"0": "HOME Menu"}
        if sbscript.is_script(raw):
            self._loaded = raw
            return [sbscript.read(raw)], {"0": "Script lines"}
        if not bdat.is_bdat(raw):
            return [[]], {}
        self._loaded = raw
        blocks = _blocks(raw)
        return [texts for _name, texts in blocks] or [[]], {str(i): name for i, (name, _t) in enumerate(blocks)}

    def prepare_save_context(self, context) -> None:
        """A table file is written over its newest version (the translation, else the source); a script over
        its oldest (the source), so repeated saves do not pile up moved strings."""
        self._home, self._base = None, None
        for raw in context.existing_versions():
            if is_home_csv(raw):
                self._home = HomeCsv(raw)
                return
            if bdat.is_bdat(raw):
                self._base = raw
                return
            if sbscript.is_script(raw):
                self._base = raw                      # keep going: the last one is the source

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._home is not None:
            texts = data[0] if data and isinstance(data[0], list) else []
            old = self._home.messages
            return self._home.build([str(texts[i]) if i < len(texts) and texts[i] is not None else old[i]
                                     for i in range(len(old))])
        base = self._base if self._base is not None else self._loaded
        if base is None:
            return super().save_data_to_json_obj(data, block_names)
        if sbscript.is_script(base):
            texts = data[0] if data and isinstance(data[0], list) else []
            return sbscript.write(base, [str(t) for t in texts])
        blocks = iter(data)
        tables = [[str(t) for t in next(blocks)] if texts else [] for _name, texts in bdat.read(base)]
        return bdat.write(base, tables)

    def reset_runtime_state(self) -> None:
        self._loaded, self._base, self._home = None, None, None

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
