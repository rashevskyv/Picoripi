"""Dragon Quest IX: Sentinels of the Starry Skies (DS, European version) plugin: the English text, the fonts and
the pictures with text.

A project's source folder holds the NitroFS files ``1_unpack.bat`` of the workspace copies from the ROM: the GPC2
archives (``*.gp2``, ``gpc2.Gpc2``) whose English members are the game's text -- ``*_en.bin`` tables (NPC talk,
events, quests, menus; ``dqtext`` ``cfg``) and ``*_en.nat`` tables (items, monsters, spells, skills and their
descriptions; ``dqtext`` ``nat``) -- the credits ``data/evspt_lv5/staffroll.bin`` and a few loose tables, the
fonts ``data/pack_lv5/fi_*.bin`` + ``fd_*.bin`` (``font_sources.json``) and the pictures (``texture_sources.json``).

An archive is one file in the editor: a block per English member (big tables ``BLOCK_SIZE`` strings a block).
The other languages stay as they are. Saving re-encodes only the edited strings, rebuilds those members and
packs the archive again; an unedited archive is written back byte for byte.
"""
import re
import struct
from pathlib import PurePath
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from core.containers import ContainerManager

from . import dqtext
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .gpc2 import Gpc2, Gpc2Container
from .pac import PacContainer
from .tag_manager import TagManager

BLOCK_SIZE = 200
FONT_FILE = "dq9_text.json"
ENGLISH = re.compile(r"_en\.(bin|nat)$")
_TOKEN = re.compile(r"\{[^{}\n]+\}|\[(?:LF|x[0-9A-Fa-f]{2})\]|.", re.S)


def line_width(line: str, font_map: dict, default_char_width: int = 6) -> int:
    """Pixels of one line: a tag drawn by a glyph (``{1}`` the apostrophe) counts its width, other tags nothing."""
    total = 0
    for match in _TOKEN.finditer(line):
        piece = match.group()
        entry = font_map.get(piece)
        if isinstance(entry, dict):
            total += entry.get("width", default_char_width)
        elif len(piece) == 1:
            total += default_char_width
    return total


class _Text:
    """The English tables of one file: ``members`` [(member name or "", Table)]."""

    def __init__(self, archive: Optional[Gpc2], members: List[Tuple[str, dqtext.Table]], raw: bytes):
        self.archive, self.members, self.raw = archive, members, raw

    def build(self, strings: List[List[bytes]]) -> bytes:
        changed = False
        for (name, table), new in zip(self.members, strings):
            if new != table.strings:
                changed = True
                data = table.build(new)
                if self.archive is None:
                    return data
                self.archive.write(name, data)
        if not changed:
            return self.raw
        return self.archive.build() if self.archive is not None else self.raw


def parse_file(data: bytes, name: str = "") -> Optional[_Text]:
    data = bytes(data)
    if data[:4] == b"GPC2":
        archive = Gpc2(data)
        members = []
        for member in archive.names:
            if ENGLISH.search(member):
                try:
                    members.append((member, dqtext.parse(member, archive.read(member))))
                except (dqtext.FormatError, ValueError, IndexError) as error:
                    log_debug(f"dq9: {member} is not a text table ({error})")
        return _Text(archive, members, data) if members else None
    for kind in ((".nat",) if name.lower().endswith(".nat") else (".bin", ".nat")):
        try:
            return _Text(None, [("", dqtext.parse("x" + kind, data))], data)
        except (dqtext.FormatError, ValueError, IndexError, struct.error):
            continue
    return None


class GameRules(BaseGameRules):
    """Dragon Quest IX (Nintendo DS, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._text: Optional[_Text] = None
        self._places: List[List[Tuple[int, int]]] = []
        ContainerManager.register(Gpc2Container)      # fonts and pictures inside archives (Textures window)
        ContainerManager.register(PacContainer)

    def get_display_name(self) -> str:
        return "Dragon Quest IX: Sentinels of the Starry Skies"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".gp2", ".bin", ".nat"), "bytes", "Dragon Quest IX text archives and tables"),
                *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    @staticmethod
    def _parse(data: bytes, name: str = "") -> Optional[_Text]:
        try:
            return parse_file(bytes(data), name)
        except (dqtext.FormatError, ValueError, IndexError, struct.error) as error:
            log_debug(f"dq9: not a text file ({error})")
            return None

    @staticmethod
    def _layout(text: _Text) -> Tuple[List[List[Tuple[int, int]]], Dict[str, str]]:
        places, names = [], {}
        for m, (member, table) in enumerate(text.members):
            count = len(table.strings)
            for start in range(0, max(count, 1), BLOCK_SIZE):
                block = [(m, k) for k in range(start, min(count, start + BLOCK_SIZE))]
                label = PurePath(member).stem if member else "Text"
                if count > BLOCK_SIZE:
                    label += f" {start}-{min(count, start + BLOCK_SIZE) - 1}"
                names[str(len(places))] = label
                places.append(block)
        return places or [[]], names

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._text = None
            return self._load_plain(json_obj)
        text = self._parse(json_obj)
        if text is None:
            self._text = None
            return [[]], {}
        self._text = text
        self._places, names = self._layout(text)
        blocks = [[dqtext.to_editor(text.members[m][1].strings[k]) for m, k in places] for places in self._places]
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
        if self._text is None:
            return "\n\n".join("\n".join(str(line) for line in block) for block in data)
        strings = [list(table.strings) for _name, table in self._text.members]
        for n, block in enumerate(data or []):
            if n >= len(self._places):
                break
            for k, text in enumerate(block or []):
                if text is None or k >= len(self._places[n]):
                    continue
                m, s = self._places[n][k]
                # An untouched string keeps its exact bytes.
                if text != dqtext.to_editor(strings[m][s]):
                    strings[m][s] = dqtext.from_editor(text)
        return self._text.build(strings)

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        name = PurePath(str(getattr(context, "relative_path", ""))).name
        for raw in context.existing_versions():
            parsed = self._parse(raw, name)
            if parsed is not None:
                self._text = parsed
                self._places, _names = self._layout(parsed)
                return
            log_warning(f"dq9: cannot read {name}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._text = None
        self._places = []

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        try:
            m, s = self._places[int(block_idx)][int(string_idx)]
        except (IndexError, ValueError):
            return None
        member = self._text.members[m][0] if self._text else ""
        return {"member": member, "string": s} if member else {"string": s}

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        return {"font_file": FONT_FILE}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        return max(line_width(line, font_map or {}, default_char_width) for line in str(text).split("\n"))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
