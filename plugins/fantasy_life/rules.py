"""Fantasy Life plugin (3DS, EUR English): Level-5 text tables, FNT fonts and ztex pictures.

The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``,
``_shared/scripts/zt/fl3ds.py``). The game keeps its files unnamed in ``romfs/_file_archive.bin``; the unpack writes
the ones Picoripi opens at ``romfs/_file_archive/<number>.<ext>`` (decompressed):

- ``.l5txt`` -- an English text file (one block): UTF-16 strings of items, quests, dialogue, menus. The game holds
  two English sets (American and British spelling) next to the other languages; both are written. Control
  sequences are ``{c:XXXX.XXXX}`` tags; a line break is a real new line. Two kinds of file exist: an index table
  of strings (items, quests, dialogue) and a table of rows with string pointers (menus, system messages);
  a longer string of the second kind moves to the end of the file.
- ``.fnt`` -- the bitmap fonts (``font_sources.json``).
- ``.ztex`` -- the pictures with words: title, buttons, font sheets (``texture_sources.json``).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import l5text
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager


class GameRules(BaseGameRules):
    """Fantasy Life (Nintendo 3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[Any] = None

    def get_display_name(self) -> str:
        return "Fantasy Life"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".l5txt",), "bytes", "Level-5 text table"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return set()

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._file = None
            return super().load_data_from_json_obj(json_obj)
        try:
            self._file = l5text.open_text(bytes(json_obj))
        except (l5text.FormatError, ValueError) as error:
            log_debug(f"fantasy_life: not a text table ({error})")
            self._file = None
            return [[]], {}
        return [list(self._file.strings)], {}

    def prepare_save_context(self, context) -> None:
        """A file is rebuilt from an existing copy (the translation, else the source): the newest that parses."""
        self._file = None
        for raw in context.existing_versions():
            try:
                self._file = l5text.open_text(raw)
                return
            except (l5text.FormatError, ValueError) as error:
                log_warning(f"fantasy_life: cannot read {context.relative_path}: {error}; trying the next version")

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = [str(t) for t in (data[0] if data and isinstance(data[0], list) else [])]
        texts += self._file.strings[len(texts):]
        return self._file.build(texts[:self._file.count])

    def reset_runtime_state(self) -> None:
        self._file = None

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return l5text.TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
