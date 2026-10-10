"""Dragon Quest Builders and Dragon Quest Builders 2 (Nintendo Switch).

The workspace's ``1_unpack.bat`` (``_shared/scripts/zt/dqb.py``) writes the English string tables into the source
folder as loose ``.bin`` files: Builders 1 ``text/<Table>.en.bin`` (from ``excel.nxarc``), Builders 2
``text/<index>.bin`` (the English member of each five-language group of ``LINKDATA.BIN``). A table (see
``excel.py``) is a block and each non-empty text a line; the Japanese lookup-key column of a Builders 1 table is
not shown. The fonts and the localized UI pictures sit next to them (``font/``, ``texture/``).

Tags are the game's ``<key>`` (end of page), ``<br>`` (line break), ``<pname>``, ``<speaker(Name)>``,
``<color(0xAARRGGBB)>`` ... ``</color>``, ``<icon(n)>`` codes inside the text.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.tag_manager import GenericTagManager

from . import excel
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

TAG_RE = re.compile(r"</?[A-Za-z][^<>\n]{0,80}>")


class TagManager(GenericTagManager):
    """``<key>``, ``<br>``, ``<pname>``, ``<speaker(Rollo)>``, ``<color(0xFFFC9016)>``, ``</color>``, ``<icon(1)>``."""

    def get_syntax_highlighting_rules(self):
        return [(r"(" + TAG_RE.pattern + r")", self.curly_tag_format), *super().get_syntax_highlighting_rules()]

    def get_legitimate_tags(self) -> Set[str]:
        return {TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and TAG_RE.fullmatch(tag_to_check) is not None


class GameRules(BaseGameRules):
    """Dragon Quest Builders 1 and 2 (Nintendo Switch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[bytes] = None      # the last table file loaded
        self._base: Optional[bytes] = None        # the table file a save writes over

    def get_display_name(self) -> str:
        return "Dragon Quest Builders 1 + 2 (Switch)"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".bin",), "bytes", "Square Enix excel string table")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        table = excel.parse(raw)
        if table is None:
            return [[]], {}
        self._loaded = raw
        return [table.texts()], {}

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._base = next((raw for raw in context.existing_versions() if excel.parse(raw) is not None), None)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        base = self._base if self._base is not None else self._loaded
        if base is None:
            return super().save_data_to_json_obj(data, block_names)
        table = excel.parse(base)
        texts = [str(text) for block in data for text in block]
        if len(texts) != len(table.texts()):
            raise ValueError(f"the table file has {len(table.texts())} texts, the project {len(texts)}")
        return excel.write(table, texts)

    def reset_runtime_state(self) -> None:
        self._loaded, self._base = None, None

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
