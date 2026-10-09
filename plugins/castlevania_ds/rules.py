"""Castlevania DS: Dawn of Sorrow, Portrait of Ruin, Order of Ecclesia (USA): text, fonts and text pictures.

A project's source folder holds what ``1_unpack.bat`` of the workspace takes out of the ROM
(``_shared/scripts/zt/cvds.py``), under a folder per game (``dos``, ``por``, ``ooe``):

- ``<game>/strings.cvdstext`` -- the game's string table (names, descriptions, menus, system, quests, dialogue)
  as raw bytes (JSON: ``format``, ``game``, ``regions`` = ``[name, first id, last id]``, ``strings`` = hex). The
  plugin shows one block per region through ``codec`` and saves the edited strings as bytes again; an unedited
  string keeps its bytes. The build lays the strings out again and grows into free space when they get longer.
- ``<game>/font/LD_font_u8.DAT`` and ``LD_font_u12.DAT`` -- the fonts (``core.font_formats.cv_nds``).
- ``<game>/sc/*.dat``, ``bc/*.dat``, ``sc2/*.dat`` -- the pictures with text (``texture_sources.json``:
  ``tiles``, the sprite pictures ``linear``).
"""
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from . import codec
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

TEXT_FORMAT = "castlevania-ds-text"
FONT_FILE = "cvds_text.json"
GAMES = {"dos": "Dawn of Sorrow", "por": "Portrait of Ruin", "ooe": "Order of Ecclesia"}
# The text font advances by its cell's left half; the small font by its cell.
TEXT_ADVANCE, SMALL_ADVANCE = 8, 8


def font_descriptors() -> List[Dict[str, Any]]:
    """The two fonts of each game (only the game whose folder is in the source matches)."""
    chars = codec.font_chars()
    out = []
    for key, title in GAMES.items():
        out.append({"label": f"{title}: text font 16x12", "format": "cv_nds", "path": f"{key}/font/LD_font_u12.DAT",
                    "font_map": FONT_FILE, "params": {"cell": [16, 12], "advance": TEXT_ADVANCE, "chars": chars}})
        out.append({"label": f"{title}: small font 8x8", "format": "cv_nds", "path": f"{key}/font/LD_font_u8.DAT",
                    "font_map": "cvds_small.json", "params": {"cell": [8, 8], "advance": SMALL_ADVANCE, "chars": chars}})
    return out


class GameRules(BaseGameRules):
    """Castlevania: Dawn of Sorrow / Portrait of Ruin / Order of Ecclesia (Nintendo DS, USA)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._bank: Optional[Dict[str, Any]] = None

    def get_display_name(self) -> str:
        return "Castlevania DS (Dawn of Sorrow / Portrait of Ruin / Order of Ecclesia)"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".cvdstext",), "json", "Castlevania DS string table (<game>/strings.cvdstext)"),
                *DEFAULT_FORMATS]

    def get_font_sources(self) -> List[Dict[str, Any]]:
        return font_descriptors()

    # -- load and save ---------------------------------------------------------

    def _blocks(self) -> List[Tuple[int, int, str]]:
        return codec.split_regions((self._bank or {}).get("regions") or [])

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not (isinstance(json_obj, dict) and json_obj.get("format") == TEXT_FORMAT):
            self._bank = None
            return self._load_plain(json_obj)
        self._bank = json_obj
        strings = [bytes.fromhex(str(h)) for h in json_obj.get("strings") or []]
        blocks = [[codec.decode(s) for s in strings[first:last + 1]] for first, last, _name in self._blocks()]
        names = {str(n): f"{name} ({first:X}-{last:X})" for n, (first, last, name) in enumerate(self._blocks())}
        return blocks, names

    @staticmethod
    def _load_plain(json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        """A list of string lists (samples and tests) or plain text split by blank lines."""
        if isinstance(json_obj, list) and all(isinstance(block, list) for block in json_obj):
            blocks = json_obj
        elif isinstance(json_obj, str):
            blocks = [[line for line in raw.splitlines() if line.strip()] for raw in re.split(r"\n\s*\n", json_obj.strip())]
            blocks = [block for block in blocks if block] or [[]]
        else:
            blocks = [[]]
        return blocks, {str(i): f"Block {i + 1}" for i in range(len(blocks))}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._bank is None:
            return data
        strings = list(self._bank.get("strings") or [])
        for (first, _last, _name), block in zip(self._blocks(), data or []):
            for k, text in enumerate(block or []):
                index = first + k
                if text is None or index >= len(strings):
                    continue
                if text == codec.decode(bytes.fromhex(strings[index])):
                    continue                              # an untouched text keeps its exact bytes
                unknown = codec.unknown_chars(text)
                if unknown:
                    log_warning(f"Castlevania DS: string {index:X}: no letter in the font for {' '.join(unknown)}; "
                                f"saved as '?'")
                try:
                    strings[index] = codec.encode(text, strict=False).hex()
                except codec.EncodeError as error:
                    log_warning(f"Castlevania DS: string {index:X} not saved: {error}")
        return {**self._bank, "strings": strings}

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                bank = json.loads(bytes(raw).decode("utf-8-sig"))
            except ValueError as error:
                log_warning(f"castlevania_ds: cannot read {context.relative_path}: {error}; trying the next version")
                continue
            if isinstance(bank, dict) and bank.get("format") == TEXT_FORMAT:
                self._bank = bank
                return

    def reset_runtime_state(self) -> None:
        self._bank = None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        blocks = self._blocks()
        if 0 <= int(block_idx) < len(blocks):
            return {"id": blocks[int(block_idx)][0] + int(string_idx)}
        return None

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        return {"font_file": FONT_FILE}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        return codec.line_width(text, font_map or {}, default_char_width)

    def get_tag_tooltip(self, tag: str) -> str:
        return codec.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
