"""The World Ends with You (DS, European version) plugin: the game's text, fonts and text pictures.

A project's source folder holds the files ``1_unpack.bat`` of the workspace copies from the ROM, by their
NitroFS paths, the text as ``Apl_Fuk/mestxt.mes`` (``mestxt.bin`` of the game: all 25,233 messages; ``mestxt``), shown ``BLOCK_SIZE`` messages a block;
``Apl_Fuk/Grp_Font.bin`` (the four fonts, ``core.font_formats.twewy``, ``font_sources.json``) and the ``Grp_*.bin``
graphics packs with text (``texture_sources.json``; the ``pack`` archive is ``core.containers.twewy_pack``).
Saving encodes only the edited messages; an unedited file is written back byte for byte. The build script makes
``mestable.bin`` again from ``mestxt.bin``.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from core.containers import ContainerManager
from core.containers.twewy_pack import TwewyPack

from . import mestxt
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

BLOCK_SIZE = 500
FONT_FILE = "twewy_text.json"


def line_width(line: str, font_map: dict, default_char_width: int = 10) -> int:
    """Pixels of one line in the text font: tags draw nothing, except ``[g:...]`` (one glyph, 10 px)."""
    total = 0
    for match in re.finditer(r"\[[^\]\n]*\]|.", line):
        piece = match.group()
        if mestxt.TAG_RE.fullmatch(piece):
            total += default_char_width if piece.startswith("[g:") else 0
            continue
        entry = font_map.get(piece)
        total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
    return total


class GameRules(BaseGameRules):
    """The World Ends with You (Nintendo DS, Europe)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._messages: Optional[List[bytes]] = None
        self._original = b""
        ContainerManager.register(TwewyPack)        # the Grp_*.bin graphics packs (Tools -> Textures)

    def get_display_name(self) -> str:
        return "The World Ends with You"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".mes",), "bytes", "The World Ends with You text (mestxt.mes = Apl_Fuk/mestxt.bin)"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            self._messages = None
            return self._load_plain(json_obj)
        try:
            messages = mestxt.split(bytes(json_obj))
        except mestxt.FormatError as error:
            log_debug(f"twewy: not a message file ({error})")
            self._messages = None
            return [[]], {}
        self._messages, self._original = messages, bytes(json_obj)
        blocks = [[mestxt.to_editor(m) for m in messages[i:i + BLOCK_SIZE]]
                  for i in range(0, len(messages), BLOCK_SIZE)]
        names = {str(n): f"Messages {n * BLOCK_SIZE}-{min(len(messages), (n + 1) * BLOCK_SIZE) - 1}"
                 for n in range(len(blocks))}
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
        if self._messages is None:
            return "\n\n".join("\n".join(str(line) for line in block) for block in data)
        messages, changed = list(self._messages), False
        for n, block in enumerate(data or []):
            for k, text in enumerate(block or []):
                index = n * BLOCK_SIZE + k
                # An untouched text keeps its exact bytes, whatever the editor form would encode to.
                if text is not None and index < len(messages) and text != mestxt.to_editor(messages[index]):
                    messages[index] = mestxt.from_editor(text)
                    changed = True
        return mestxt.join(messages) if changed else self._original

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                self._messages, self._original = mestxt.split(bytes(raw)), bytes(raw)
                return
            except mestxt.FormatError as error:
                log_warning(f"twewy: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._messages = None
        self._original = b""

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        return {"id": int(block_idx) * BLOCK_SIZE + int(string_idx)}

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        return {"font_file": FONT_FILE}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 10) -> Optional[int]:
        return max(line_width(line, font_map or {}, default_char_width) for line in str(text).split("\n"))

    def get_tag_tooltip(self, tag: str) -> str:
        return mestxt.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
