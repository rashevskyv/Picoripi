"""Dragon Quest Monsters: Joker 3 (3DS, Japanese game + English fan patch 1.02) plugin: .mes tables, credits, BFFNT, BFLIM.

The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``): ``romfs/data/Message/**/*.mes``
(menus, items, skills, monsters, scouting, synthesis, help, trivia) and ``romfs/data/Script/Field/**/*.mes``
(events and demo scenes; a block = a table, a string = an entry, its label in ``get_message_attributes``),
``romfs/data/Menu/EndRoll/*.nut`` (credits: the quoted strings of the Squirrel scripts), the ``*.bffnt`` fonts and
the layout pictures (BFLIM inside SARC ``data/Layout/**/*.arc``). Control characters in a text are shown as
``{01}`` tags.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import mes
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f]")
_CONTROL_TAG = re.compile(r"\{([0-9A-F]{2})\}")
_NUT_STRING = re.compile(rb'"((?:[^"\\\r\n]|\\.)*)"')
_NUT_ENCODING = "cp932"


def decode_text(text: str) -> str:
    return _CONTROL.sub(lambda m: "{%02X}" % ord(m.group()), text)


def encode_text(text: str) -> str:
    return _CONTROL_TAG.sub(lambda m: chr(int(m.group(1), 16)), text)


def nut_strings(raw: bytes) -> List[str]:
    return [m.group(1).decode(_NUT_ENCODING, "surrogateescape") for m in _NUT_STRING.finditer(raw)]


def nut_build(raw: bytes, texts: List[str]) -> bytes:
    found = list(_NUT_STRING.finditer(raw))
    if len(found) != len(texts):
        raise ValueError(f"{len(texts)} strings for {len(found)} quoted literals")
    out, at = bytearray(), 0
    for m, text in zip(found, texts):
        out += raw[at:m.start(1)] + str(text).encode(_NUT_ENCODING, "surrogateescape")
        at = m.end(1)
    return bytes(out + raw[at:])


class GameRules(BaseGameRules):
    """Dragon Quest Monsters: Joker 3 (3DS, English fan patch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, List[str]]]] = {}

    def get_display_name(self) -> str:
        return "Dragon Quest Monsters: Joker 3 (3DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".mes",), "bytes", "message table"),
                FileFormat((".nut",), "bytes", "Squirrel script (credits)"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    @staticmethod
    def _is_script(raw: bytes) -> bool:
        return raw[:2] == b"//"

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            if self._is_script(self._last_loaded):
                return [nut_strings(self._last_loaded)], {}
            return [[decode_text(t) for t in mes.Table(self._last_loaded).texts()]], {}
        except (mes.FormatError, ValueError) as error:
            log_debug(f"dq_monsters_joker3: not a text file ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = [str(s) for s in (data[0] if data else [])]
        if self._is_script(source):
            return nut_build(source, texts)
        return mes.Table(source).build([encode_text(t) for t in texts])

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._save_source = self._last_loaded = None

    # -- context ---------------------------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, List[str]]]:
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            raw = Path(pm.get_absolute_path(block.source_file)).read_bytes()
            labels = [] if self._is_script(raw) else mes.Table(raw).labels
            found = (str(block.source_file).replace("\\", "/"), labels)
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"dq_monsters_joker3: no table behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._locate(block_idx)
        if not found or int(string_idx) >= len(found[1]):
            return None
        return {"file": found[0], "label": found[1][int(string_idx)]}

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
        return "dq_monsters_joker3_script.md"
