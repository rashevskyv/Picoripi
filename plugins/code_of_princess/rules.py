"""Code of Princess plugin (3DS and Switch EX): the English text compiled into the executable, fonts and pictures.

Both versions keep every message, menu word and item name as a NUL-terminated wide string in the executable
(``pool.py``): ``source/exefs/code.bin`` (3DS, UTF-16) or ``source/exefs/main`` (Switch NSO, UTF-32). A block is one
area of strings, a string is one text; ``{x08}`` is the control unit that ends a message and must stay. A string
is written back in place and may not be longer than the original (a shorter text is padded). ``font/*.fnt`` are the
``FD`` fonts (Tools -> Font Editor) and ``rtex/**/*.rtx`` the pictures (Tools -> Textures).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import pool
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


class GameRules(BaseGameRules):
    """Code of Princess (3DS, USA; Switch: Code of Princess EX)."""

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
        return "Code of Princess"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Code of Princess executable (3DS code.bin)"),
                FileFormat((".nso",), "bytes", "Code of Princess EX executable (Switch main)"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return _plain_load(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            blocks = pool.Pool(self._last_loaded).texts()
        except pool.PoolError as error:
            log_debug(f"code_of_princess: not an executable ({error})")
            return [[]], {}
        names = {str(i): f"Text {i + 1}" for i in range(len(blocks))}
        return blocks, names

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return "\n\n".join("\n".join(str(line) for line in block) for block in data)
        return pool.Pool(source).rebuild([[str(s) for s in block] for block in data])

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
        return "code_of_princess_script.md"
