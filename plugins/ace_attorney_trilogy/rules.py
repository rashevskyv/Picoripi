"""Ace Attorney Trilogy plugin (3DS and Switch): the English script files of ``pack.dat``, the game font and the pictures.

``1_unpack.bat`` (``zt/aat3ds.py``) writes the game's resource pack ``pack.dat`` (hash-named, LZ-compressed
entries) as loose files: ``script/<NN>.bin`` (one English script per day of the three games: every sentence of
the dialogue, cross-examination and investigation scenes), ``font/*.bcfnt`` (the two game fonts, Font Editor)
and ``texture/*.bch`` (every picture: titles, menus, evidence, tutorials; Tools -> Textures). Saving writes the
same files into the translation folder and ``2_build.bat`` packs them back into a Luma / Azahar romfs mod.

A script block is one file; a string is a message (see ``gsscript``): ``\n`` is a line break, ``{page}`` waits
for a tap, ``{wait:N}`` pauses N frames, ``{xNNN}`` is a game character this plugin has no letter for.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import gsscript
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager


def _plain_load(json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
    """Plain text (blocks split by blank lines) or JSON lists: what the app's tests and the importers hand over."""
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


class GameRules(BaseGameRules):
    """Ace Attorney Trilogy (3DS, European English)."""

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
        return "Ace Attorney Trilogy"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin", ".mdt"), "bytes", "Ace Attorney script"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return _plain_load(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [gsscript.Script(self._last_loaded).texts()], {}
        except gsscript.ScriptError as error:
            log_debug(f"ace_attorney_trilogy: not a script ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return "\n\n".join("\n".join(str(line) for line in block) for block in data)
        return gsscript.Script(source).rebuild([str(s) for s in (data[0] if data else [])])

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
        return "ace_attorney_trilogy_script.md"
