"""Castlevania: Symphony of the Night for the Sega Saturn, in the "Dracula X Ultimate" English build: text, fonts
and text pictures.

A project's source folder holds what ``1_unpack.bat`` of the workspace takes off the disc
(``_shared/scripts/zt/sotnsat.py``):

- ``text/<FILE>.sotnstext`` -- the strings of one program file (JSON: ``format``, ``file``, ``strings`` =
  offset ``o``, encoding ``e``, bytes ``hex``). The plugin shows them through ``codec`` and saves an edited
  string as bytes again; an unedited string keeps its bytes. The build puts a changed string in place or packs
  its group of strings again and moves their pointers.
- ``fonts/MENU_12x12.BIN`` (the title, data-select and save menus: 1 bit 12x12 from ``GAME.PRG``; the game
  shrinks it to 8 px with grey edges), ``fonts/SYSTEM_8x8.BIN`` (the in-game font, 4 bit 8x8) and
  ``fonts/ASCII.FON`` (1 bit 8x16); ``font_sources.json``, read through the ``raw`` and ``tiles`` texture formats.
- ``dialogue/<EVENT>.BIN`` -- the cutscene dialogue is pictures of its lines (4 bit 8x16 cells, 32 a line);
  ``title/TITLE_LOGO.BIN`` -- the title screen as one picture (its 40x32 pattern name map and 8 bit 8x8 cells)
  and ``title/TITLE_MENUS.BIN`` -- the eight menu screens with the gothic headings (the 40x256 map and 4 bit
  cells of VDP2 NBG3), both through the ``tilemap`` texture format; ``texture_sources.json``. The workspace
  build packs the cells into their LZ chunks of ``TITLE.MAP`` again and moves the chunk table in ``TITLE.PRG``.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from . import codec
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

TEXT_FORMAT = "sotn-saturn-text"
BLOCK_SIZE = 300
KINDS = {"a": "text", "c": "names", "n": "speakers"}


class GameRules(BaseGameRules):
    """Castlevania: Symphony of the Night (Sega Saturn, Dracula X Ultimate English build)."""

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
        return "Castlevania: Symphony of the Night (Saturn)"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".sotnstext",), "json", "Symphony of the Night (Saturn) strings (text/*.sotnstext)"),
                *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def _groups(self) -> List[Tuple[str, int, int]]:
        """(kind, first, last) runs of strings of one kind, at most BLOCK_SIZE each."""
        strings = (self._bank or {}).get("strings") or []
        groups: List[Tuple[str, int, int]] = []
        for index, entry in enumerate(strings):
            kind = entry.get("e", "a")
            if groups and groups[-1][0] == kind and index - groups[-1][1] < BLOCK_SIZE:
                groups[-1] = (kind, groups[-1][1], index)
            else:
                groups.append((kind, index, index))
        return groups

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not (isinstance(json_obj, dict) and json_obj.get("format") == TEXT_FORMAT):
            self._bank = None
            return self._load_plain(json_obj)
        self._bank = json_obj
        strings = json_obj.get("strings") or []
        blocks, names = [], {}
        for n, (kind, first, last) in enumerate(self._groups()):
            blocks.append([codec.decode(s.get("e", "a"), bytes.fromhex(s["hex"])) for s in strings[first:last + 1]])
            names[str(n)] = f"{KINDS.get(kind, kind).capitalize()} ({first}-{last})"
        return (blocks or [[]]), names

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
        strings = [dict(s) for s in self._bank.get("strings") or []]
        for (kind, first, _last), block in zip(self._groups(), data or []):
            for k, text in enumerate(block or []):
                index = first + k
                if text is None or index >= len(strings):
                    continue
                entry = strings[index]
                old = bytes.fromhex(entry["hex"])
                if text == codec.decode(kind, old):          # untouched: keep the exact bytes
                    continue
                raw, unknown = codec.encode(kind, text)
                if unknown:
                    log_warning(f"{self._bank.get('file')}: string {index}: no letter in the font for "
                                f"{' '.join(sorted(set(unknown)))}; saved as '?'")
                if kind == "n" and len(raw) != len(old):
                    log_warning(f"{self._bank.get('file')}: speaker name {index} keeps {len(old)} letters "
                                f"(padded with spaces or cut)")
                    raw = raw[:len(old)].ljust(len(old), b"\0")
                entry["hex"] = raw.hex()
        return {**self._bank, "strings": strings}

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        import json
        for raw in context.existing_versions():
            try:
                bank = json.loads(bytes(raw).decode("utf-8-sig"))
            except ValueError as error:
                log_warning(f"castlevania_sotn_saturn: cannot read {context.relative_path}: {error}; trying the next one")
                continue
            if isinstance(bank, dict) and bank.get("format") == TEXT_FORMAT:
                self._bank = bank
                return

    def reset_runtime_state(self) -> None:
        self._bank = None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        groups = self._groups()
        if 0 <= int(block_idx) < len(groups):
            index = groups[int(block_idx)][1] + int(string_idx)
            strings = (self._bank or {}).get("strings") or []
            if index < len(strings):
                return {"id": index, "file": self._bank.get("file"), "offset": f"0x{strings[index]['o']:X}"}
        return None

    # -- editor ----------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return codec.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
