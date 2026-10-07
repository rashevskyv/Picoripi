"""Ocarina of Time 3D plugin: the English text of ``eu.qm``, the name-entry keyboards and the default player name.

A project's source folder holds the workspace's ``source`` tree (``1_unpack.bat`` fills it):

- ``romfs/message/eu/eu.qm`` -- every message (dialogue, items, menus, credits, area names), English
  slot only, one block per id range. Saving encodes again only the edited texts; an unedited file is
  written back byte for byte.
- ``romfs/menu/ltn16_*.list`` -- the name-entry keyboard pages (UTF-16, one key per character; the
  number of keys must stay the same).
- ``exefs/code.bin`` -- the default player name (``Link``), at most ``NAME_LENGTH`` characters.

Fonts (``ltn16.qbf``, ``sys8.qbf``) and the textures with text are listed in ``font_sources.json`` and
``texture_sources.json``. The Russian build's ``eu.qm`` and the game's other languages are the
reference texts.
"""
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import qm
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

# (first id, block, role). Ids are those of N64 Ocarina of Time; 3DS-only ranges are named by content.
BLOCKS = (
    (0x0000, "Items received", "Item get message"),
    (0x0100, "Navi's hints", "Navi's hint about the place"),
    (0x0200, "Doors and system", "System or door message"),
    (0x0300, "Signs", "Sign text"),
    (0x0400, "Gossip Stones", "Gossip Stone hint"),
    (0x0500, "Staff credits", "Staff credits"),
    (0x0600, "Navi on enemies", "Navi's note about an enemy"),
    (0x0700, "Item descriptions", "Item description in the pause menu"),
    (0x0800, "Menus and songs", "Menu or ocarina message"),
    (0x0900, "File select, options, Boss Challenge", "Menu text"),
    (0x1000, "Dialogue 0x1000", "Dialogue"),
    (0x2000, "Dialogue 0x2000", "Dialogue"),
    (0x3000, "Dialogue 0x3000", "Dialogue"),
    (0x4000, "Dialogue 0x4000", "Dialogue"),
    (0x5000, "Dialogue 0x5000", "Dialogue"),
    (0x6000, "Dialogue 0x6000", "Dialogue"),
    (0x7000, "Dialogue 0x7000", "Dialogue"),
    (0x8000, "Sheikah Stone visions", "Title of a hint vision"),
    (0x8100, "Area names", "Area name"),
)
FONT_FILE = "ltn16.json"
MAX_LINE_WIDTH = 285          # widest retail English line in ltn16 advances (credits left out)
# ponytail: the EU 1.0 code.bin only (by its size); add a build when another one turns up.
CODE_BIN = {4567040: (0x328148, 0x4497A8)}
NAME_LENGTH = 4               # UTF-16 units; the copy at 0x4497A8 has no room for more
_TAG_RE = re.compile(r"\{[^{}]*\}")
_BOM = b"\xff\xfe"


def block_of(message_id: int) -> int:
    """Index in BLOCKS of a message id."""
    return max(index for index, block in enumerate(BLOCKS) if message_id >= block[0])


def split_blocks(ids: List[int]) -> List[List[int]]:
    """Message indices per block (file order); empty blocks are dropped."""
    groups: List[List[int]] = [[] for _ in BLOCKS]
    for index, message_id in enumerate(ids):
        groups[block_of(message_id)].append(index)
    return [group for group in groups if group]


def group_names(ids: List[int], groups: List[List[int]]) -> List[str]:
    """The BLOCKS name of each group of ``split_blocks``."""
    return [BLOCKS[block_of(ids[group[0]])][1] for group in groups]


def kind_of(data: bytes) -> str:
    """``qm``, ``list`` (a keyboard page), ``code`` (code.bin) or ``""``."""
    if data[:4] == b"QM\0\0":
        return "qm"
    if data[:2] == _BOM and len(data) % 2 == 0 and len(data) < 4096:
        return "list"
    if len(data) in CODE_BIN:
        return "code"
    return ""


def read_name(data: bytes) -> str:
    start = CODE_BIN[len(data)][0]
    return data[start:start + 2 * NAME_LENGTH].decode("utf-16-le").split("\0")[0]


def write_name(data: bytes, name: str) -> bytes:
    if len(name) > NAME_LENGTH or "\n" in name:
        raise ValueError(f"The default player name holds at most {NAME_LENGTH} characters: {name!r}")
    out = bytearray(data)
    for start in CODE_BIN[len(data)]:
        out[start:start + 2 * NAME_LENGTH] = name.encode("utf-16-le").ljust(2 * NAME_LENGTH, b"\0")
    return bytes(out)


class GameRules(BaseGameRules):
    """The Legend of Zelda: Ocarina of Time 3D (3DS, European version)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._kind = ""
        self._file: Optional[qm.Qm] = None
        self._original = b""
        self._located: Dict[int, Optional[Tuple[qm.Qm, List[int]]]] = {}

    def get_display_name(self) -> str:
        return "Zelda: Ocarina of Time 3D"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".qm",), "bytes", "Ocarina of Time 3D messages"),
                FileFormat((".list",), "bytes", "Ocarina of Time 3D name-entry keyboard"),
                FileFormat((".bin",), "bytes", "3DS code.bin (default player name)"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        kind = kind_of(data)
        self._kind, self._original = kind, data
        try:
            if kind == "qm":
                messages = qm.Qm(data)
                groups = split_blocks(messages.ids)
                blocks = [[qm.to_editor(messages.texts[i][qm.ENGLISH] or b"") for i in group] for group in groups]
                self._file = messages
                return blocks, {str(n): name for n, name in enumerate(group_names(messages.ids, groups))}
            if kind == "list":
                return [[data[2:].decode("utf-16-le")]], {"0": "Name-entry keyboard"}
            if kind == "code":
                return [[read_name(data)]], {"0": "Default player name"}
        except (qm.FormatError, UnicodeDecodeError) as error:
            log_debug(f"zelda_oot3d: cannot read the file ({error})")
        self._kind = ""
        return [[]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        kind, original = self._kind, self._original
        if kind == "list":
            text = str((data or [[""]])[0][0] or "")
            return _BOM + text.encode("utf-16-le")
        if kind == "code":
            name = str((data or [[""]])[0][0] or "")
            return original if name == read_name(original) else write_name(original, name)
        if kind != "qm" or self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        messages, changed = self._file, False
        groups = split_blocks(messages.ids)
        names = group_names(messages.ids, groups)
        for position, block in enumerate(data or []):
            # A project splits the file into one block per range (named like it) or keeps it whole.
            name = (block_names or {}).get(str(position))
            group = groups[names.index(name)] if name in names else groups[position]
            for index, text in zip(group, block or []):
                raw = messages.texts[index][qm.ENGLISH] or b""
                # An untouched text keeps its exact bytes, whatever the editor form would encode to.
                if text is not None and text != qm.to_editor(raw):
                    messages.texts[index][qm.ENGLISH] = qm.from_editor(text)
                    changed = True
        return messages.build() if changed else original

    def prepare_save_context(self, context) -> None:
        """Each file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            raw = bytes(raw)
            kind = kind_of(raw)
            try:
                self._file = qm.Qm(raw) if kind == "qm" else None
            except qm.FormatError as error:
                log_warning(f"zelda_oot3d: cannot read {context.relative_path}: {error}; trying the next version")
                continue
            if kind:
                self._kind, self._original = kind, raw
                return

    def reset_runtime_state(self) -> None:
        self._kind = ""
        self._file = None
        self._original = b""
        self._located.clear()

    # -- where a string comes from -----------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[qm.Qm, List[int]]]:
        """``(parsed source eu.qm, message indices)`` of a data block; cached per load."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            project_idx = block_map.get(block_idx, block_idx)
            sub = sum(1 for d, p in block_map.items() if p == project_idx and d < block_idx)
            block = pm.project.blocks[project_idx]
            if str(block.source_file).lower().endswith(".qm"):
                messages = qm.Qm(Path(pm.get_absolute_path(block.source_file)).read_bytes())
                groups = split_blocks(messages.ids)
                if block.internal_key:
                    sub = group_names(messages.ids, groups).index(block.internal_key)
                found = (messages, groups[sub])
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"zelda_oot3d: no QM file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int) -> Optional[Tuple[qm.Qm, int]]:
        located = self._locate(block_idx)
        try:
            return (located[0], located[1][int(string_idx)]) if located else None
        except (IndexError, TypeError, ValueError):
            return None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        messages, index = found
        box_type, box_position = messages.attributes(index)
        return {"message_id": messages.ids[index], "textbox_type": box_type, "textbox_position": box_position}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        role = BLOCKS[block_of(found[0].ids[found[1]])][2]
        return {"content_role": role} if role == "Dialogue" else {"content_role": role, "has_speaker": False}

    def get_capabilities(self) -> Set[str]:
        return {"external_reference"}

    def get_external_reference_url(self, term: str) -> Optional[str]:
        if not term or not term.strip():
            return None
        return f"https://zeldawiki.wiki/wiki/Special:Search?search={urllib.parse.quote(term.strip())}"

    # -- reference languages -------------------------------------------------------

    def supports_reference_patch(self) -> bool:
        """The Russian build's ``eu.qm`` and the game's other languages are the references."""
        return True

    def get_reference_language_label(self) -> str:
        return "Russian (RU)"

    def load_reference_patch(self, patch_path: str, block_names=None) -> Dict[Tuple[int, int], str]:
        return self.load_multi_reference(patch_path, block_names).get(self.get_reference_language_label(), {})

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """Every language of the ``eu.qm`` at ``patch_path`` (the file, or a folder holding
        ``romfs/message/eu/eu.qm``), matched by message id. An English slot written in Cyrillic is
        the Russian translation."""
        where: Dict[int, Tuple[int, int]] = {}
        for key in (block_names or {}):
            located = self._locate(int(key))
            if located:
                for string_idx, index in enumerate(located[1]):
                    where[located[0].ids[index]] = (int(key), string_idx)
        result: Dict[str, Dict[Tuple[int, int], str]] = {}
        for path in _reference_files(Path(patch_path)):
            try:
                messages = qm.Qm(path.read_bytes())
            except (OSError, qm.FormatError) as error:
                log_warning(f"zelda_oot3d: reference {path}: {error}")
                continue
            for slot in range(qm.SLOTS):
                decoded = {}
                for message_id, raw in qm.slot_texts(messages, slot).items():
                    try:
                        decoded[message_id] = qm.to_editor(raw)
                    except qm.FormatError:
                        continue
                if not decoded:
                    continue
                cyrillic = any("Ѐ" <= ch <= "ӿ" for text in decoded.values() for ch in text)
                label = "Russian (RU)" if slot == qm.ENGLISH and cyrillic else qm.LANGUAGES[slot]
                if not label or label in result or (slot == qm.ENGLISH and not cyrillic):
                    continue
                result[label] = {where[i]: text for i, text in decoded.items() if i in where}
        return result

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        if not self._message(block_idx, string_idx):
            return None
        return {"warn_width": MAX_LINE_WIDTH, "max_width": MAX_LINE_WIDTH, "font_file": FONT_FILE}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 10) -> Optional[int]:
        """Widest line in font advances; tags take no room.
        ponytail: both branches of {mq}...{mq-else}...{mq-end} are counted; measure them apart if it matters."""
        widest = 0
        for line in str(text).split("\n"):
            total = 0
            for ch in _TAG_RE.sub("", line):
                entry = (font_map or {}).get(ch)
                total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
            widest = max(widest, total)
        return widest

    def get_tag_tooltip(self, tag: str) -> str:
        return qm.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE


def _reference_files(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    for folder in (path, path / "message" / "eu", path / "romfs" / "message" / "eu"):
        if (folder / "eu.qm").is_file():
            return [folder / "eu.qm"]
    return []
