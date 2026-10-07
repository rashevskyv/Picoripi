"""Majora's Mask 3D plugin: the English text of ``eue.gmsg``, one block per id range.

A project's source folder holds the workspace's ``source`` tree (``1_unpack.bat`` fills it):
``romfs/message/eu/eue.gmsg`` has every message (dialogue, items, signs, Bombers' Notebook, place names,
credits, file select, fishing, Sheikah Stone, objectives). Saving encodes again only the edited texts;
an unedited file is written back byte for byte. The base game and the v1040 update read the same file
(``rom:`` / ``patch:``), so one LayeredFS file replaces both.

The font (``ltn16.gzf``) and the textures with text are listed in ``font_sources.json`` and
``texture_sources.json``. The Russian build's ``eue.gmsg`` and the game's other languages are the
reference texts.
"""
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import gmsg
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

# (first id, block, role). Ids below 0x4E20 are those of N64 Majora's Mask; the rest are 3DS-only.
BLOCKS = (
    (0x0000, "Items received", "Item get message"),
    (0x0100, "Messages 0x0100", "Dialogue"),
    (0x1000, "Messages 0x1000", "Dialogue"),
    (0x1700, "Item descriptions", "Item description in the pause menu"),
    (0x1800, "Messages 0x1800", "Dialogue"),
    (0x2000, "Messages 0x2000", "Dialogue"),
    (0x3000, "Messages 0x3000", "Dialogue"),
    (0x4E20, "Region names and notices", "Region name or notice"),
    (0x4E84, "Bombers' Notebook", "Bombers' Notebook entry"),
    (0x55F0, "Staff credits", "Staff credits"),
    (0x571C, "File select and system", "Menu text"),
    (0x5780, "Ordinal suffixes", "English ordinal suffix"),
    (0x59D8, "Fishing", "Dialogue"),
    (0x5DC0, "Messages 0x5DC0", "Dialogue"),
    (0x5FB4, "Sheikah Stone", "Sheikah Stone hint"),
    (0x6018, "Objectives", "Objective in the hint list"),
    (0x60E0, "Location list", "Location name in a list"),
)
FONT_FILE = "ltn16.json"
MAX_LINE_WIDTH = 280          # widest retail English lines in ltn16 advances (credits and one 302 outlier left out)
_TAG_RE = re.compile(r"\{[^{}]*\}")
LANGUAGES = {"eue": "English (EU)", "euf": "French (FR)", "eug": "German (DE)", "eus": "Spanish (ES)",
             "eui": "Italian (IT)"}


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


class GameRules(BaseGameRules):
    """The Legend of Zelda: Majora's Mask 3D (3DS, European version, with or without the v1040 update)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[gmsg.Gmsg] = None
        self._original = b""
        self._located: Dict[int, Optional[Tuple[gmsg.Gmsg, List[int]]]] = {}

    def get_display_name(self) -> str:
        return "Zelda: Majora's Mask 3D"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".gmsg",), "bytes", "Majora's Mask 3D messages"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._original = data
        try:
            messages = gmsg.Gmsg(data)
            groups = split_blocks(messages.ids)
            blocks = [[gmsg.to_editor(messages.texts[i]) if messages.texts[i] else "" for i in group]
                      for group in groups]
            self._file = messages
            return blocks, {str(n): name for n, name in enumerate(group_names(messages.ids, groups))}
        except gmsg.FormatError as error:
            log_debug(f"zelda_mm3d: cannot read the file ({error})")
        self._file = None
        return [[]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        messages, changed = self._file, False
        groups = split_blocks(messages.ids)
        names = group_names(messages.ids, groups)
        for position, block in enumerate(data or []):
            # A project splits the file into one block per range (named like it) or keeps it whole.
            name = (block_names or {}).get(str(position))
            group = groups[names.index(name)] if name in names else groups[position]
            for index, text in zip(group, block or []):
                raw = messages.texts[index]
                # An untouched text keeps its exact bytes, whatever the editor form would encode to.
                if text is not None and text != (gmsg.to_editor(raw) if raw else ""):
                    messages.texts[index] = gmsg.from_editor(text)
                    changed = True
        return messages.build() if changed else self._original

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            raw = bytes(raw)
            try:
                self._file = gmsg.Gmsg(raw)
            except gmsg.FormatError as error:
                log_warning(f"zelda_mm3d: cannot read {context.relative_path}: {error}; trying the next version")
                continue
            self._original = raw
            return

    def reset_runtime_state(self) -> None:
        self._file = None
        self._original = b""
        self._located.clear()

    # -- where a string comes from -----------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[gmsg.Gmsg, List[int]]]:
        """``(parsed source eue.gmsg, message indices)`` of a data block; cached per load."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            project_idx = block_map.get(block_idx, block_idx)
            sub = sum(1 for d, p in block_map.items() if p == project_idx and d < block_idx)
            block = pm.project.blocks[project_idx]
            if str(block.source_file).lower().endswith(".gmsg"):
                messages = gmsg.Gmsg(Path(pm.get_absolute_path(block.source_file)).read_bytes())
                groups = split_blocks(messages.ids)
                if block.internal_key:
                    sub = group_names(messages.ids, groups).index(block.internal_key)
                found = (messages, groups[sub])
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"zelda_mm3d: no GMSG file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int) -> Optional[Tuple[gmsg.Gmsg, int]]:
        located = self._locate(block_idx)
        try:
            return (located[0], located[1][int(string_idx)]) if located else None
        except (IndexError, TypeError, ValueError):
            return None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._message(block_idx, string_idx)
        return found[0].attributes(found[1]) if found else None

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
        """The Russian build's ``eue.gmsg`` and the game's other languages are the references."""
        return True

    def get_reference_language_label(self) -> str:
        return "Russian (RU)"

    def load_reference_patch(self, patch_path: str, block_names=None) -> Dict[Tuple[int, int], str]:
        return self.load_multi_reference(patch_path, block_names).get(self.get_reference_language_label(), {})

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """Every ``eu?.gmsg`` at ``patch_path`` (a file, or a folder holding them directly, in
        ``message/eu`` or in ``romfs/message/eu``), matched by message id. An English file written in
        Cyrillic is the Russian translation."""
        where: Dict[int, Tuple[int, int]] = {}
        for key in (block_names or {}):
            located = self._locate(int(key))
            if located:
                for string_idx, index in enumerate(located[1]):
                    where[located[0].ids[index]] = (int(key), string_idx)
        result: Dict[str, Dict[Tuple[int, int], str]] = {}
        for path in _reference_files(Path(patch_path)):
            try:
                messages = gmsg.Gmsg(path.read_bytes())
            except (OSError, gmsg.FormatError) as error:
                log_warning(f"zelda_mm3d: reference {path}: {error}")
                continue
            decoded = {}
            for message_id, raw in zip(messages.ids, messages.texts):
                try:
                    decoded[message_id] = gmsg.to_editor(raw) if raw else ""
                except gmsg.FormatError:
                    continue
            cyrillic = any("Ѐ" <= ch <= "ӿ" for text in decoded.values() for ch in text)
            label = "Russian (RU)" if path.stem == "eue" and cyrillic else LANGUAGES.get(path.stem, "")
            if not label or label in result or label == "English (EU)" or not any(decoded.values()):
                continue
            result[label] = {where[i]: text for i, text in decoded.items() if i in where and text}
        return result

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        if not self._message(block_idx, string_idx):
            return None
        return {"warn_width": MAX_LINE_WIDTH, "max_width": MAX_LINE_WIDTH, "font_file": FONT_FILE}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 10) -> Optional[int]:
        """Widest line in font advances; tags take no room (plural forms count both)."""
        widest = 0
        for line in str(text).split("\n"):
            total = 0
            for ch in _TAG_RE.sub("", line):
                entry = (font_map or {}).get(ch)
                total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
            widest = max(widest, total)
        return widest

    def get_tag_tooltip(self, tag: str) -> str:
        return gmsg.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE


def _reference_files(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    for folder in (path, path / "message" / "eu", path / "romfs" / "message" / "eu"):
        found = sorted(folder.glob("eu?.gmsg")) if folder.is_dir() else []
        if found:
            return found
    return []
