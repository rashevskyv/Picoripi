"""Digimon World: Re:Digitize Decode plugin (3DS, English fan translation): ``BTX `` text tables of ``KCAP`` files.

The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``,
``_shared/scripts/zt/digi3ds.py``). The unpack writes every file of ``ARCV0.BIN`` that holds text at
``romfs/ARCV/<path in the archive>.btxt`` (decompressed). A file holds one or many text tables; each table is one
block of strings. A string may change its length: the containers are rebuilt. A file with data behind its container
keeps the string lengths.
"""
from __future__ import annotations

from struct import error as struct_error
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import btxt
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


class GameRules(BaseGameRules):
    """Digimon World: Re:Digitize Decode (Nintendo 3DS, English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[btxt.DigiText] = None

    def get_display_name(self) -> str:
        return "Digimon World: Re:Digitize Decode"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".btxt",), "bytes", "Digimon text container"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._file = None
            return super().load_data_from_json_obj(json_obj)
        try:
            self._file = btxt.DigiText(bytes(json_obj))
        except (btxt.FormatError, ValueError, struct_error) as error:
            log_debug(f"digimon_redigitize: not a text container ({error})")
            self._file = None
            return [[]], {}
        names = {str(i): f"Table {i + 1}" for i in range(len(self._file.blocks))}
        return self._file.strings, names

    def prepare_save_context(self, context) -> None:
        """A file is rebuilt from an existing copy (the translation, else the source): the newest that parses."""
        self._file = None
        for raw in context.existing_versions():
            try:
                self._file = btxt.DigiText(raw)
                return
            except (btxt.FormatError, ValueError, struct_error) as error:
                log_warning(f"digimon_redigitize: cannot read {context.relative_path}: {error}; trying the next version")

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = []
        for i, old in enumerate(self._file.strings):       # a missing string or block keeps its old text
            new = [str(t) for t in data[i]] if i < len(data) and isinstance(data[i], list) else []
            texts.append((new + old[len(new):])[:len(old)])
        return self._file.build(texts)

    def reset_runtime_state(self) -> None:
        self._file = None

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return btxt.TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
