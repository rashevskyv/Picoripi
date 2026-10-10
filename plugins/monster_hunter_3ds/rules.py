"""Monster Hunter 3 Ultimate, 4 Ultimate and Stories (3DS, European versions) plugin.

All three run on Capcom's MT Framework Mobile. A project's source folder holds what the workspace's
``1_unpack.bat`` takes out of the game's ``.arc`` archives and romfs (``zt/mhmt.py``): the English and
language-neutral text tables (``.gmd`` MH3U, ``.lmd`` MH4U and Stories), the quests (``.quest`` MH3U, ``.mib``
MH4U; their English slot), the fonts (``.gfd`` / ``.lfd`` with ``.tex`` pages, ``font_sources.json``) and the
UI textures (``.tex``, ``texture_sources.json``). Formats: ``mttext``. A file is one block; saving re-encodes
only the edited strings, so an unedited file is written back byte for byte.
"""
import re
from struct import error as struct_error
from pathlib import PurePath
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import mttext
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

TEXT_EXTENSIONS = (".gmd", ".lmd", ".quest", ".mib")


class GameRules(BaseGameRules):
    """Monster Hunter 3 Ultimate, 4 Ultimate and Stories (Nintendo 3DS, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    analyze_whole_string_first = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[mttext.TextFile] = None

    def get_display_name(self) -> str:
        return "Monster Hunter (3DS: 3 Ultimate, 4 Ultimate, Stories)"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat(TEXT_EXTENSIONS, "bytes", "Monster Hunter 3DS text tables and quests"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    @staticmethod
    def _parse(data: bytes) -> Optional[mttext.TextFile]:
        try:
            return mttext.parse(bytes(data))
        except (mttext.FormatError, ValueError, IndexError, struct_error) as error:
            log_debug(f"monster_hunter_3ds: not a text file ({error})")
            return None

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._file = None
            return self._load_plain(json_obj)
        self._file = self._parse(json_obj)
        if self._file is None:
            return [[]], {}
        return [[mttext.to_editor(text) for text in self._file.strings]], {"0": "Text"}

    @staticmethod
    def _load_plain(json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        """Plain text (blocks split by blank lines) or a list of string lists: for samples and tests."""
        if isinstance(json_obj, str):
            blocks = [[line for line in raw.splitlines() if line.strip()]
                      for raw in re.split(r"\n\s*\n", json_obj.strip())]
            blocks = [block for block in blocks if block] or [[]]
        elif isinstance(json_obj, list) and all(isinstance(block, list) for block in json_obj):
            blocks = json_obj
        else:
            blocks = [[]]
        return blocks, {str(i): f"Block {i + 1}" for i in range(len(blocks))}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return "\n\n".join("\n".join(str(line) for line in block) for block in data)
        strings = list(self._file.strings)
        for k, text in enumerate((data or [[]])[0] or []):
            if text is None or k >= len(strings):
                continue
            # An untouched text keeps its exact bytes, whatever the editor form would encode to.
            if text != mttext.to_editor(strings[k]):
                strings[k] = mttext.from_editor(text, self._file.kind in ("gmd", "quest"))   # MH3U: CR LF
        return self._file.build(strings)

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        name = PurePath(str(getattr(context, "relative_path", ""))).name
        for raw in context.existing_versions():
            parsed = self._parse(raw)
            if parsed is not None:
                self._file = parsed
                return
            log_warning(f"monster_hunter_3ds: cannot read {name}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._file = None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        if self._file is None or not 0 <= int(string_idx) < len(self._file.strings):
            return None
        label = self._file.labels[int(string_idx)]
        return {"string": int(string_idx), "label": label} if label else {"string": int(string_idx)}

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return mttext.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
