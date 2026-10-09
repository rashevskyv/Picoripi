"""Xenoblade Chronicles X: Definitive Edition (Switch, update 1.0.2).

The workspace's ``1_unpack.bat`` (``_shared/scripts/zt/xc3.py``, game ``XENOBLADE_X_DE``) takes from the game's
archive ``sts.ard`` (index ``sts.arh``: hashed paths, named from a public hash list) into the source folder,
at the archive paths: the English text tables ``bdat/us/*.bdat`` (modern BDAT, ``plugins/common/bdat``; one
project block per file, every text cell of its tables is a line: ``common_ms`` = menus, system, names and
descriptions of skells, arts, items, enemies, locations, tutorials; ``xs*`` = story events; ``qev*`` = quest
events; ``tev*`` = talk events), the credits roll ``ui/credit/endroll.crt`` (``crt``), the fonts
``ui/font/*.wifnt`` (LAFT), the layouts ``ui/image/*.wilay`` and the English pictures ``ui/stream/us/*.wilay``
(the title logo ``strm_title_thumb001``, tips). ``2_build.bat`` writes changed files as loose files under
``romfs/mod/`` of a LayeredFS mod together with masagrator's XCXDE-ModLoader (exefs), which makes the game
read them instead of the archive entries.

Tags are the game's ``[ML:...]``, ``[ST:...]`` and ``[System:...]`` codes inside the text.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common import bdat
from plugins.common.tag_manager import GenericTagManager

from . import crt
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

TAG_RE = re.compile(r"\[/?(?:ML|ST|System):[^\[\]]*\]")


class TagManager(GenericTagManager):
    """``[ML:icon icon=A ]``, ``[ST:col p1=green ]``, ``[System:Color ...]`` and the other bracket codes."""

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None


def _format(raw: bytes):
    """The module that reads this file (``bdat`` or ``crt``), or None."""
    if bdat.is_bdat(raw):
        return bdat
    if crt.is_crt(raw):
        return crt
    return None


class GameRules(BaseGameRules):
    """Xenoblade Chronicles X: Definitive Edition (Nintendo Switch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[bytes] = None      # the last file loaded
        self._base: Optional[bytes] = None        # the file a save writes over

    def get_display_name(self) -> str:
        return "Xenoblade Chronicles X: Definitive Edition (Switch)"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".bdat",), "bytes", "Monolith Soft BDAT tables"),
                FileFormat((".crt",), "bytes", "Credits roll")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        fmt = _format(raw)
        if fmt is None:
            return [[]], {}
        self._loaded = raw
        return [fmt.read(raw)], {}

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._base = next((raw for raw in context.existing_versions() if _format(raw)), None)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        base = self._base if self._base is not None else self._loaded
        if base is None:
            return super().save_data_to_json_obj(data, block_names)
        fmt = _format(base)
        texts = [str(text) for block in data for text in block]
        count = len(fmt.read(base))
        if len(texts) != count:
            raise ValueError(f"the file has {count} text cells, the project {len(texts)}")
        return fmt.write(base, texts)

    def reset_runtime_state(self) -> None:
        self._loaded, self._base = None, None

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
