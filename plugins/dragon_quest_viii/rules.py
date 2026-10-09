"""Dragon Quest VIII: Journey of the Cursed King (3DS, EUR) plugin: binE tables, word tables, BFFNT, BFLIM.

The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``): the English slot
``romfs/data/Message/eng/*.binE`` (menus, items, spells, monsters, battle, church, casino, quests...) and
``romfs/data/Script/field/message/eng/**/*.binE`` (events, NPC talk, party chat, records; a block = a table, a
string = an entry, ids in ``get_message_attributes``), ``romfs/data/Params/WordTable/eng/*.txt`` (item and word
tables as tab-separated lines: a string = a line), the ``rom/Font/*.bffnt`` fonts and the layout pictures
(BFLIM inside SARC ``data/Layout/**/*.arc``). The other slots (fre, ger, ita, spa) stay untouched.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import bine
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager

CRLF = "\r\n"


def table_lines(raw: bytes) -> Tuple[List[str], bool]:
    text = raw.decode("utf-8")
    trailing = text.endswith(CRLF)
    return (text[:-2].split(CRLF) if trailing else text.split(CRLF)), trailing


def table_build(raw: bytes, lines: List[str]) -> bytes:
    _old, trailing = table_lines(raw)
    return (CRLF.join(lines) + (CRLF if trailing else "")).encode("utf-8")


class GameRules(BaseGameRules):
    """Dragon Quest VIII: Journey of the Cursed King (3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, List[int]]]] = {}

    def get_display_name(self) -> str:
        return "Dragon Quest VIII (3DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bine",), "bytes", "binE message table"),
                FileFormat((".txt",), "bytes", "word table"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    @staticmethod
    def _is_table(raw: bytes) -> bool:
        return not raw[:3] == b"\xef\xbb\xbf" and not raw[:2] == b"[["

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            if self._is_table(self._last_loaded):
                return [bine.Table(self._last_loaded).texts()], {}
            return [table_lines(self._last_loaded)[0]], {}
        except (bine.FormatError, ValueError) as error:
            log_debug(f"dragon_quest_viii: not a text file ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = [str(s) for s in (data[0] if data else [])]
        if self._is_table(source):
            return bine.Table(source).build(texts)
        return table_build(source, texts)

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._save_source = self._last_loaded = None

    # -- context ---------------------------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, List[int]]]:
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            raw = Path(pm.get_absolute_path(block.source_file)).read_bytes()
            ids = bine.Table(raw).ids if self._is_table(raw) else []
            found = (str(block.source_file).replace("\\", "/"), ids)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"dragon_quest_viii: no table behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._locate(block_idx)
        if not found or int(string_idx) >= len(found[1]):
            return None
        return {"file": found[0], "id": found[1][int(string_idx)]}

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._locate(block_idx)
        return found[0] if found else None

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_default_script_name(self) -> Optional[str]:
        return "dragon_quest_viii_script.md"
