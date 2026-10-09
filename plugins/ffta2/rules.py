"""Final Fantasy Tactics A2 (DS, European version) plugin: the English text, the font and the text pictures.

A project's source folder holds what ``1_unpack.bat`` of the workspace takes out of ``master/pc.bin``: the five
English message packs as ``.a2msg`` files (``a2text``: menus, names and descriptions, quests, rumours, notices,
event dialogue), the font (``menu/font``, ``core.font_formats.ffta2``, ``font_sources.json``), the menu pictures
(``menu/nc_rom/us/nc.a2pak``, the ``A2PakContainer`` archive) and the title logo (``*.efx``,
``core.texture_formats.ffta2_efx``; ``texture_sources.json``).

A string table is one block; a pack of single strings (quests, rumours, notices) is shown ``BLOCK_SIZE`` strings
a block. Saving re-encodes only the edited strings; an unedited file is written back byte for byte.
"""
import re
import struct
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from core.containers import ContainerManager
from core.containers.base_container import BaseArchiveContainer

from . import a2text
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

BLOCK_SIZE = 50
FONT_FILE = "ffta2_text.json"
# Names of the 55 tables of JD_message (after FFTA2 Editor's MessageId).
TABLE_NAMES = (
    "Character names", "Job names", "Ability set names", "Ability names", "Region names", "Location names",
    "Quest names", "Clan titles, auction text", "Rumour titles", "Menu text", "Notice titles", "Item names",
    "Status names", "Clan names", "Law names", "Clan privilege names", "Auction menu text", "Quest menu text",
    "Item types and effects", "Name entry 1", "Name entry 2", "Name entry 3", "Table 22", "Table 23",
    "Bazaar text", "Table 25", "Table 26", "Table 27", "Table 28", "Table 29", "Ability set descriptions",
    "Ability descriptions", "Region descriptions", "Location descriptions", "Table 34", "Quest descriptions",
    "Table 36", "Battle text", "Job descriptions", "Item descriptions", "Ally death text", "Status descriptions",
    "Law descriptions", "Clan privilege descriptions", "Auction house text", "Pub text", "Table 46",
    "Ability help text", "Dismissal and intro text", "New notice text", "Shop text", "Opportunity text",
    "Menu text and job requirements", "Bazaar category descriptions", "Clan descriptions",
)
PACK_TITLES = {"JD_message": "Menus", "JH_questtext": "Quests", "JH_uwasatext": "Rumours",
               "JH_freepapermes": "Notices", "ev_msg": "Events"}


class A2PakContainer(BaseArchiveContainer):
    """An index + data pair kept as one workspace file (``.a2pak``, ``a2text.MAGIC`` kind ``P``): members ``#n``."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return bytes(data[:5]) == a2text.MAGIC + b"P"

    def __init__(self, data: bytes) -> None:
        self._original = bytes(data)
        _kind, self._index, pak = a2text.split_file(data)
        self._members = a2text.members(self._index, pak)
        self._unit = 32 if all(((w >> 3) & 0xFFFFFF) % 8 == 0 for w, _h in a2text._records(self._index)
                               if not w & 7) else 4
        self._changed = False

    def list_files(self) -> list[str]:
        return [f"#{i}" for i, member in enumerate(self._members) if member]

    def read_file(self, path: str) -> bytes:
        return bytes(self._members[int(path.lstrip("#"))] or b"")

    def write_file(self, path: str, data: bytes) -> None:
        number = int(path.lstrip("#"))
        if bytes(data) != self._members[number]:
            self._members[number] = bytes(data)
            self._changed = True

    def has_pending_changes(self) -> bool:
        return self._changed

    def pack(self) -> bytes:
        if not self._changed:
            return self._original
        index, pak = a2text.pack_members(self._members, self._index, self._unit)
        return a2text.join_file("P", index, pak)


def line_width(line: str, font_map: dict, default_char_width: int = 8) -> int:
    """Pixels of one line: tags draw nothing except ``[xNN]`` (one glyph)."""
    total = 0
    for match in re.finditer(r"\[[^\]\n]*\]|.", line):
        piece = match.group()
        if a2text.TAG_RE.fullmatch(piece):
            total += default_char_width if piece.startswith("[x") else 0
            continue
        entry = font_map.get(piece)
        total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
    return total


class GameRules(BaseGameRules):
    """Final Fantasy Tactics A2: Grimoire of the Rift (Nintendo DS, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._pack: Optional[a2text.Pack] = None
        self._places: List[List[Tuple[int, int]]] = []
        ContainerManager.register(A2PakContainer)     # the menu pictures (Tools -> Textures)

    def get_display_name(self) -> str:
        return "Final Fantasy Tactics A2"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".a2msg",), "bytes", "Final Fantasy Tactics A2 message pack (.a2msg)"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._pack = None
            return self._load_plain(json_obj)
        try:
            pack = a2text.Pack(bytes(json_obj))
        except (a2text.FormatError, struct.error) as error:
            log_debug(f"ffta2: not a message pack ({error})")
            self._pack = None
            return [[]], {}
        self._pack = pack
        self._places = self._layout(pack)
        blocks = [[a2text.to_editor(pack.groups[m][s]) for m, s in places] for places in self._places]
        return blocks, self._names(pack)

    @staticmethod
    def _layout(pack: a2text.Pack) -> List[List[Tuple[int, int]]]:
        """Which (member, string) each editor line is, block by block."""
        if pack.kind == "T":
            return [[(m, s) for s in range(len(group))] for m, group in enumerate(pack.groups) if group]
        flat = [(m, 0) for m, group in enumerate(pack.groups) if group]
        return [flat[i:i + BLOCK_SIZE] for i in range(0, len(flat), BLOCK_SIZE)] or [[]]

    def _names(self, pack: a2text.Pack) -> Dict[str, str]:
        names = {}
        menus = len(pack.groups) == len(TABLE_NAMES)
        for n, places in enumerate(self._places):
            if not places:
                continue
            first = places[0][0]
            if pack.kind == "T":
                names[str(n)] = (f"{first:02d} {TABLE_NAMES[first]}" if menus else f"Event {first:04d}")
            else:
                names[str(n)] = f"{first:03d}-{places[-1][0]:03d}"
        return names

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
        if self._pack is None:
            return "\n\n".join("\n".join(str(line) for line in block) for block in data)
        pack, edited = self._pack, {}
        for n, block in enumerate(data or []):
            if n >= len(self._places):
                break
            for k, text in enumerate(block or []):
                if text is None or k >= len(self._places[n]):
                    continue
                m, s = self._places[n][k]
                raw = pack.groups[m][s]
                # An untouched text keeps its exact bytes, whatever the editor form would encode to.
                if text != a2text.to_editor(raw):
                    edited[(m, s)] = a2text.from_editor(text, a2text.split_tail(raw)[1])
        return pack.build(edited)

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                self._pack = a2text.Pack(bytes(raw))
                self._places = self._layout(self._pack)
                return
            except (a2text.FormatError, struct.error) as error:
                log_warning(f"ffta2: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._pack = None
        self._places = []

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        try:
            member, string = self._places[int(block_idx)][int(string_idx)]
        except (IndexError, ValueError):
            return None
        return {"member": member, "string": string}

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        return {"font_file": FONT_FILE}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        return max(line_width(line, font_map or {}, default_char_width) for line in str(text).split("\n"))

    def get_tag_tooltip(self, tag: str) -> str:
        return a2text.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
