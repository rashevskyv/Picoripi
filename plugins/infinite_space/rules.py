"""Infinite Space (DS, European version) plugin: the script text, the dialogue font and the pictures with text.

A project's source folder holds the NitroFS files ``1_unpack.bat`` of the workspace copies from the ROM:
``data/Event/SpaceShip.scx`` (every line of text, ``scx``), ``data/Cg/Obd/T000OBJ.obd`` (the dialogue font,
``font_sources.json``) and the pictures (``data/Cg/Bgd/*.bgd`` screens and the title logo, ``data/Cg/Obd/*.obd``
menu sprites, ``data/Cg/Texture/*.tex`` the opening text and the ship plans; ``texture_sources.json``).

The editor lists only the script lines that hold letters (about 6 000 of 9 349; the others are bare commands),
``BLOCK_SIZE`` a block. Saving re-encodes only the edited lines and lays the text out again; an unedited file is
written back byte for byte.
"""
import re
from pathlib import PurePath
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import scx
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

BLOCK_SIZE = 100
ADVANCE = 8                      # every glyph of the dialogue font is 8 pixels wide


def line_width(line: str) -> int:
    """Pixels of one line: commands draw nothing, every letter takes ``ADVANCE``."""
    return ADVANCE * len(scx.TAG_RE.sub("", line))


class GameRules(BaseGameRules):
    """Infinite Space (Nintendo DS, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._script: Optional[scx.Script] = None
        self._places: List[List[int]] = []

    def get_display_name(self) -> str:
        return "Infinite Space"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".scx",), "bytes", "Infinite Space script text"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    @staticmethod
    def _parse(data: bytes) -> Optional[scx.Script]:
        try:
            return scx.parse(bytes(data))
        except (scx.FormatError, ValueError, IndexError, UnicodeError) as error:
            log_debug(f"infinite_space: not a script ({error})")
            return None

    @staticmethod
    def _layout(script: scx.Script) -> List[List[int]]:
        """The lines with letters, ``BLOCK_SIZE`` a block."""
        shown = [n for n, line in enumerate(script.strings) if scx.has_letters(line)]
        return [shown[i:i + BLOCK_SIZE] for i in range(0, len(shown), BLOCK_SIZE)] or [[]]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._script = None
            return self._load_plain(json_obj)
        script = self._parse(json_obj)
        if script is None:
            self._script = None
            return [[]], {}
        self._script = script
        self._places = self._layout(script)
        blocks = [[scx.to_editor(script.strings[i]) for i in places] for places in self._places]
        names = {str(n): f"Lines {p[0]}-{p[-1]}" for n, p in enumerate(self._places) if p}
        return blocks, names

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
        if self._script is None:
            return "\n\n".join("\n".join(str(line) for line in block) for block in data)
        strings = list(self._script.strings)
        for n, block in enumerate(data or []):
            if n >= len(self._places):
                break
            for k, text in enumerate(block or []):
                if text is None or k >= len(self._places[n]):
                    continue
                index = self._places[n][k]
                # An untouched line keeps its exact bytes.
                if text != scx.to_editor(strings[index]):
                    strings[index] = scx.from_editor(text)
        return self._script.build(strings)

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            parsed = self._parse(raw)
            if parsed is not None:
                self._script = parsed
                self._places = self._layout(parsed)
                return
            log_warning(f"infinite_space: cannot read {PurePath(str(getattr(context, 'relative_path', ''))).name}")

    def reset_runtime_state(self) -> None:
        self._script = None
        self._places = []

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        try:
            return {"line": self._places[int(block_idx)][int(string_idx)]}
        except (IndexError, ValueError):
            return None

    # -- editor ----------------------------------------------------------------

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        return max(line_width(line) for line in str(text).split("\n"))

    def get_tag_tooltip(self, tag: str) -> str:
        return scx.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
