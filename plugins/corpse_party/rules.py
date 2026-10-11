"""Corpse Party plugin (3DS; the 2021 Switch version is Unity, see ``unity.py``): messages, lists, fonts, pictures.

``1_unpack.bat`` (``zt/cp3ds.py``) writes the game's ``romfs\\data`` into ``source\\data``:

- ``chapN\\chapN_scriptlist.MSG`` and ``extraNNN\\extraNNN_scriptlist.MSG`` (``msg.py``): every message of the story,
  128-byte slots, a block per file; text may not outgrow a message's slots;
- ``itemdatalist.txt``, ``deaddatalist.txt``, ``endinglist.txt``, ``playersettinglist.txt`` (``txtlist.py``): quoted
  strings of the game's text lists;
- ``font\\*.bffnt`` (Tools -> Font Editor) and ``font\\*.ctpk`` / ``g*\\*.ctpk`` pictures (Tools -> Textures).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import msg, txtlist
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager


def _plain_load(json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
    if isinstance(json_obj, str):
        blocks = [[line for line in raw.splitlines() if line.strip()] for raw in re.split(r"\n\s*\n", json_obj.strip())]
        blocks = [block for block in blocks if block] or [[]]
    elif isinstance(json_obj, list) and all(isinstance(block, list) for block in json_obj):
        blocks = json_obj or [[]]
    elif isinstance(json_obj, list):
        blocks = [[str(item) for item in json_obj]]
    else:
        blocks = [[]]
    return blocks, {str(i): f"Block {i + 1}" for i in range(len(blocks))}


def _kind(raw: bytes) -> str:
    if msg.is_msg(raw):
        return "msg"
    return "list" if txtlist.is_list(raw) else ""


class GameRules(BaseGameRules):
    """Corpse Party (3DS, English)."""

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

    def get_display_name(self) -> str:
        return "Corpse Party"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msg",), "bytes", "Corpse Party messages"),
                FileFormat((".txt",), "bytes", "Corpse Party text list"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return _plain_load(json_obj)
        raw = bytes(json_obj)
        self._last_loaded = raw
        kind = _kind(raw)
        try:
            if kind == "msg":
                return [msg.Msg(raw).texts()], {}
            if kind == "list":
                return [txtlist.texts(raw)], {}
        except ValueError as error:
            log_debug(f"corpse_party: {error}")
        return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        texts = [str(s) for s in (data[0] if data else [])]
        kind = _kind(source) if source else ""
        if kind == "msg":
            return msg.Msg(source).rebuild(texts)
        if kind == "list":
            return txtlist.rebuild(source, [t for t in texts])
        return "\n\n".join("\n".join(str(line) for line in block) for block in data)

    def reset_runtime_state(self) -> None:
        self._save_source = self._last_loaded = None

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_default_script_name(self) -> Optional[str]:
        return "corpse_party_script.md"
