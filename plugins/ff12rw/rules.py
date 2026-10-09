"""Final Fantasy XII: Revenant Wings (DS, European version) plugin: the English text, fonts and text pictures.

A project's source folder holds the NitroFS files ``1_unpack.bat`` of the workspace copies from the ROM: the
English text set ``data/**/E/`` (``rwtext``: menus, characters, items, abilities, reports, tutorials, airship talks,
event dialogue, mission objectives, the world map, the opening scroll), ``data/FontPack.dpk`` (four NFTR fonts,
``font_sources.json``) and the pictures with text (``texture_sources.json``; ``.dpk`` packs are opened by
``dpk.DpkContainer``, NARCs by ``core.containers.nitro.NarcContainer``).

A file is one block, except the event packs (a block per event) and the big data files (``BLOCK_SIZE`` strings a
block). Saving re-encodes only the edited strings and lays the file out again; an unedited file is written back
byte for byte.
"""
import re
from pathlib import PurePath
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from core.containers import ContainerManager
from core.containers.nitro import NarcContainer

from . import rwtext
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .dpk import DpkContainer
from .tag_manager import TagManager

BLOCK_SIZE = 100
FONT_FILE = "ff12rw_text.json"
TEXT_EXTENSIONS = (".btx", ".btk", ".brt", ".bst", ".hscd", ".bch", ".bit", ".bsk", ".bmw", ".dpk")


def line_width(line: str, font_map: dict, default_char_width: int = 6) -> int:
    """Pixels of one line in the text font: tags draw nothing."""
    total = 0
    for match in re.finditer(r"\[[^\]\n]*\]|.", line):
        piece = match.group()
        if rwtext.TAG_RE.fullmatch(piece):
            continue
        entry = font_map.get(piece)
        total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
    return total


class GameRules(BaseGameRules):
    """Final Fantasy XII: Revenant Wings (Nintendo DS, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[rwtext.TextFile] = None
        self._places: List[List[int]] = []
        ContainerManager.register(DpkContainer)      # fonts and mission title pictures (Font Editor, Textures)
        ContainerManager.register(NarcContainer)     # the picture archives (Tools -> Textures)

    def get_display_name(self) -> str:
        return "Final Fantasy XII: Revenant Wings"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat(TEXT_EXTENSIONS, "bytes", "Final Fantasy XII: Revenant Wings text files"),
                *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def _parse(self, data: bytes, name: str = "") -> Optional[rwtext.TextFile]:
        parser = rwtext.parser_for(name) if name else None
        parser = parser or rwtext.detect(data)
        if parser is None:
            return None
        try:
            return parser(bytes(data))
        except (rwtext.FormatError, ValueError, IndexError) as error:
            log_debug(f"ff12rw: not a text file ({error})")
            return None

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._file = None
            return self._load_plain(json_obj)
        text_file = self._parse(bytes(json_obj))
        if text_file is None:
            self._file = None
            return [[]], {}
        self._file = text_file
        self._places, names = self._layout(text_file)
        blocks = [[rwtext.to_editor(text_file.strings[i]) for i in places] for places in self._places]
        return blocks, names

    @staticmethod
    def _layout(text_file: rwtext.TextFile) -> Tuple[List[List[int]], Dict[str, str]]:
        """Which string each editor line is, block by block, and the block names."""
        labels, count = text_file.labels, len(text_file.strings)
        if labels and all(label.isdigit() or label.startswith("stage ") for label in labels if label):
            groups: Dict[str, List[int]] = {}
            for index, label in enumerate(labels):
                groups.setdefault(label, []).append(index)
            if len(groups) > 1 and not all(label.startswith("stage ") for label in groups):
                places = list(groups.values())
                return places, {str(n): f"Event {label}" for n, label in enumerate(groups)}
        places = [list(range(i, min(count, i + BLOCK_SIZE))) for i in range(0, count, BLOCK_SIZE)] or [[]]
        if len(places) == 1:
            return places, {"0": "Text"}
        return places, {str(n): f"Strings {p[0]}-{p[-1]}" for n, p in enumerate(places) if p}

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
        strings, changed = list(self._file.strings), False
        for n, block in enumerate(data or []):
            if n >= len(self._places):
                break
            for k, text in enumerate(block or []):
                if text is None or k >= len(self._places[n]):
                    continue
                index = self._places[n][k]
                # An untouched text keeps its exact bytes, whatever the editor form would encode to.
                if text != rwtext.to_editor(strings[index]):
                    strings[index] = rwtext.from_editor(text)
                    changed = True
        return self._file.build(strings) if changed else self._file.build(self._file.strings)

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        name = PurePath(str(getattr(context, "relative_path", ""))).name
        for raw in context.existing_versions():
            parsed = self._parse(bytes(raw), name)
            if parsed is not None:
                self._file = parsed
                self._places, _names = self._layout(parsed)
                return
            log_warning(f"ff12rw: cannot read {name}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._file = None
        self._places = []

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        try:
            index = self._places[int(block_idx)][int(string_idx)]
        except (IndexError, ValueError):
            return None
        label = self._file.labels[index] if self._file else ""
        return {"string": index, "kind": label} if label and not label.isdigit() else {"string": index}

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        return {"font_file": FONT_FILE}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        return max(line_width(line, font_map or {}, default_char_width) for line in str(text).split("\n"))

    def get_tag_tooltip(self, tag: str) -> str:
        return rwtext.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
