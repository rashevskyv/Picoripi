"""Castlevania: Harmony of Dissonance (GBA, Europe) and Aria of Sorrow (GBA, USA): text, fonts and text pictures.

A project's source folder holds what ``1_unpack.bat`` of the workspace takes out of the ROM
(``_shared/scripts/zt/cvgba.py``):

- ``text/strings.cvtext`` -- every English string as its raw bytes (JSON: ``format``, ``game`` = ``hod`` /
  ``aos``, ``strings`` = hex). The plugin shows them in blocks by kind (``BLOCKS``) through ``codec`` and
  saves the edited ones as bytes again; an unedited string keeps its bytes. The build puts a changed string
  in place or in the free end of the ROM.
- ``fonts/<game>_*.bin`` -- the 1-bit fonts (``core.font_formats.cv_gba``; ``get_font_sources``).
- ``gfx/<game>_<offset>.bin`` -- the text pictures, unpacked 4bpp tiles (``texture_sources.json``).
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from . import codec
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

TEXT_FORMAT = "castlevania-gba-text"
FONT_FILES = {"aos": "aos_text.json", "hod": "hod_text.json"}
TITLES = {"aos": "Castlevania: Aria of Sorrow", "hod": "Castlevania: Harmony of Dissonance"}

# (first, last, name, line width limit in pixels or 0) of the English strings, by kind: the widest English line
# of the kind, rounded up.
BLOCKS: Dict[str, List[Tuple[int, int, str, int]]] = {
    "aos": [(0, 10, "Characters", 76), (11, 90, "Story", 208), (91, 122, "Item names", 84),
            (123, 181, "Weapon names", 84), (182, 226, "Armor and accessory names", 84), (227, 347, "Soul names", 84),
            (348, 379, "Item descriptions", 200), (380, 438, "Weapon descriptions", 200),
            (439, 483, "Armor and accessory descriptions", 200), (484, 604, "Soul descriptions", 200),
            (605, 717, "Enemy names", 84), (718, 830, "Enemy descriptions", 200), (831, 841, "Money", 0),
            (842, 914, "System and menus", 0), (915, 947, "Sound mode", 0), (948, 950, "Shop", 176),
            (951, 964, "Area names", 120)],
    "hod": [(0, 9, "Characters", 76), (10, 33, "Story", 184), (34, 70, "Item names", 84),
            (71, 215, "Equipment, book and relic names", 84), (216, 246, "Furniture names", 84),
            (247, 459, "Descriptions", 212), (460, 584, "Enemy names", 88), (585, 591, "Money", 0),
            (592, 639, "System and menus", 0), (640, 651, "Merchant and events", 192), (652, 682, "Sound mode", 0)],
}

# The small 8x8 font of HoD: glyph index -> character.
_HOD_SMALL = {**{chr(65 + i): i for i in range(26)}, **{chr(97 + i): 32 + i for i in range(26)},
              **{chr(48 + i): 64 + i for i in range(10)}, "/": 74, "-": 75}


def font_descriptors() -> List[Dict[str, Any]]:
    """The four fonts of both games (only the game whose files are in the source folder matches)."""
    aos_chars = {char: code - 0x20 for code, char in codec.AOS.chars.items() if 0x20 <= code < 0xFD}
    glyph = {code: index for index, code in enumerate(codec.hod_glyph_codes())}
    hod_chars, hod_widths = {}, {}
    for code, char in codec.HOD.chars.items():
        target, _x, width = codec.ALIASES.get(code, (code, 0, codec.HOD_DEFAULT_WIDTH))
        if target in glyph:
            hod_chars[char] = glyph[target]
            if code in codec.ALIASES:
                hod_widths[str(glyph[target])] = width
    aos_widths = {"stride": 4, "byte": 1}
    return [
        {"label": "Aria of Sorrow: text font 8x12", "format": "cv_gba", "path": "fonts/aos_dialogue.bin",
         "companion": "fonts/aos_dialogue_widths.bin", "font_map": FONT_FILES["aos"],
         "params": {"glyphs": 221, "record": 14, "rows": 12, "keep_mask": 1, "widths": aos_widths,
                    "chars": aos_chars}},
        {"label": "Aria of Sorrow: small font 8x8", "format": "cv_gba", "path": "fonts/aos_small.bin",
         "companion": "fonts/aos_small_widths.bin", "font_map": "aos_small.json",
         "params": {"glyphs": 221, "record": 10, "rows": 8, "keep_mask": 1, "widths": aos_widths,
                    "chars": aos_chars}},
        {"label": "Harmony of Dissonance: text font 8x12", "format": "cv_gba", "path": "fonts/hod_dialogue.bin",
         "font_map": FONT_FILES["hod"],
         "params": {"glyphs": 752, "record": 14, "rows": 12, "advance": codec.HOD_DEFAULT_WIDTH,
                    "glyph_widths": hod_widths, "chars": hod_chars}},
        {"label": "Harmony of Dissonance: small font 8x8", "format": "cv_gba", "path": "fonts/hod_small.bin",
         "font_map": "hod_small.json",
         "params": {"glyphs": 87, "record": 10, "rows": 8, "advance": 8, "chars": _HOD_SMALL}},
    ]


class GameRules(BaseGameRules):
    """Castlevania: Harmony of Dissonance / Aria of Sorrow (GBA)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._bank: Optional[Dict[str, Any]] = None
        self._game = "aos"

    def get_display_name(self) -> str:
        return "Castlevania GBA (Harmony of Dissonance / Aria of Sorrow)"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".cvtext",), "json", "Castlevania GBA strings (text/strings.cvtext)"), *DEFAULT_FORMATS]

    def get_font_sources(self) -> List[Dict[str, Any]]:
        return font_descriptors()

    # -- load and save ---------------------------------------------------------

    def _blocks(self, count: int) -> List[Tuple[int, int, str, int]]:
        blocks = [b for b in BLOCKS.get(self._game, []) if b[1] < count]
        covered = blocks[-1][1] + 1 if blocks else 0
        return blocks + ([(covered, count - 1, "Other", 0)] if covered < count else [])

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not (isinstance(json_obj, dict) and json_obj.get("format") == TEXT_FORMAT
                and json_obj.get("game") in codec.CODECS):
            self._bank = None
            return self._load_plain(json_obj)
        self._bank, self._game = json_obj, json_obj["game"]
        game_codec = codec.CODECS[self._game]
        strings = [bytes.fromhex(str(h)) for h in json_obj.get("strings") or []]
        blocks = [[game_codec.decode(s) for s in strings[first:last + 1]]
                  for first, last, _name, _width in self._blocks(len(strings))]
        names = {str(n): f"{name} ({first}-{last})" for n, (first, last, name, _w) in enumerate(self._blocks(len(strings)))}
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
        game_codec = codec.CODECS[self._game]
        strings = list(self._bank.get("strings") or [])
        for (first, _last, _name, _w), block in zip(self._blocks(len(strings)), data or []):
            for k, text in enumerate(block or []):
                index = first + k
                if text is None or index >= len(strings):
                    continue
                old = bytes.fromhex(strings[index])
                # An untouched text keeps its exact bytes.
                if text == game_codec.decode(old):
                    continue
                unknown = game_codec.unknown_chars(text)
                if unknown:
                    log_warning(f"{TITLES[self._game]}: string {index}: no letter in the font for "
                                f"{' '.join(unknown)}; saved as '?'")
                strings[index] = game_codec.encode(text, strict=False).hex()
        return {**self._bank, "strings": strings}

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        import json
        for raw in context.existing_versions():
            try:
                bank = json.loads(bytes(raw).decode("utf-8-sig"))
            except ValueError as error:
                log_warning(f"castlevania_gba: cannot read {context.relative_path}: {error}; trying the next version")
                continue
            if isinstance(bank, dict) and bank.get("format") == TEXT_FORMAT:
                self._bank, self._game = bank, bank.get("game", self._game)
                return

    def reset_runtime_state(self) -> None:
        self._bank = None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        blocks = self._blocks(len((self._bank or {}).get("strings") or []))
        if 0 <= int(block_idx) < len(blocks):
            return {"id": blocks[int(block_idx)][0] + int(string_idx)}
        return None

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        layout: Dict[str, Any] = {"font_file": FONT_FILES.get(self._game, FONT_FILES["aos"])}
        blocks = self._blocks(len((self._bank or {}).get("strings") or []))
        if 0 <= int(block_idx) < len(blocks) and blocks[int(block_idx)][3]:
            layout["max_width"] = layout["warn_width"] = blocks[int(block_idx)][3]
        return layout

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        return codec.line_width(text, font_map or {}, default_char_width)

    def get_tag_tooltip(self, tag: str) -> str:
        return codec.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
