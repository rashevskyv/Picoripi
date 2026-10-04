"""Four Swords Anniversary Edition plugin: the English (EU) texts of ``eu.kmsg`` (DSiWare NitroFS), by id range.

A project's source folder holds ``eu.kmsg`` with the English text in its English (EU) slot (``1_unpack.bat``
of the workspace builds it from the game's ``all.kmsg``) and the font ``font_ltn.nftr``. The 220 messages are
shown one block per id range; saving writes the file with only the edited English texts encoded again (an
unedited file is written back byte for byte). Speakers come from the ``[speaker:N]`` code of cutscene lines
and the Great Fairy messages; widths from the NFTR font; the Russian build's ``eu.kmsg`` (and the game's other
languages) are the reference texts.
"""
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import kmsg
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager
from .tags import SPEAKERS, TAG_RE, describe, from_editor, to_editor

# (first id, block, role, spoken, widest line in pixels). The widths are the widest English, German and
# French lines of the range in font_ltn.nftr (pictures counted ICON_WIDTH wide).
BLOCKS = (
    (0, "Prologue", "Prologue cutscene line", True, 225),
    (100, "Chambers of Insight", "Hint in the Chambers of Insight (tutorial)", False, 225),
    (200, "Items", "Item get message", False, 225),
    (300, "Great Fairies", "Great Fairy dialogue", True, 225),
    (400, "Vaati and the ending", "Cutscene line", True, 225),
    (600, "Chambers of Insight (single player)", "Hint in the Chambers of Insight, single-player version", False, 225),
    (1000, "In-game messages", "Short message shown over the game", False, 168),
    (2000, "System and menus", "System message or menu text", False, 240),
    (3000, "Staff credits", "Staff credits", False, 240),
)
GREAT_FAIRIES = {301: "Great Fairy of Forest", 351: "Great Fairy of Forest", 302: "Great Fairy of Ice",
                 352: "Great Fairy of Ice", 303: "Great Fairy of Flame", 353: "Great Fairy of Flame"}
ICON_WIDTH = 12          # ponytail: item and button pictures guessed one cell wide; measure in a game screenshot
FONT_FILE = "fsae_ltn.json"
_SPEAKER_RE = re.compile(r"\[speaker:(\d+)\]")
_ITEM_RE = re.compile(r"^You got (?:the |a )?(.+?) ?(?:\[space:\d+\])?\[icon:\d+\]")
_PLACE_RE = re.compile(r"\[color:3\]\s*(.+?)\s*\[color:0\]")


def block_of(message_id: int) -> int:
    """Index in BLOCKS of a message id."""
    return max(index for index, block in enumerate(BLOCKS) if message_id >= block[0])


def split_blocks(ids: List[int]) -> List[List[int]]:
    """Message indices per block (file order); empty blocks are dropped."""
    groups: List[List[int]] = [[] for _ in BLOCKS]
    for index, message_id in enumerate(ids):
        groups[block_of(message_id)].append(index)
    return [group for group in groups if group]


def plain_text(text: str) -> str:
    return TAG_RE.sub("", text)


def line_width(line: str, font_map: dict, default_char_width: int = 10) -> int:
    """Pixels of one line: the font's advances, ``[space:N]`` N pixels, pictures ICON_WIDTH, other tags none."""
    total = 0
    for match in re.finditer(r"\[[^\]\n]*\]|.", line):
        piece = match.group()
        if TAG_RE.fullmatch(piece):
            if piece.startswith("[space:"):
                total += int(piece[7:-1])
            elif piece.startswith(("[icon:", "[button:")):
                total += ICON_WIDTH
            continue
        entry = font_map.get(piece)
        total += entry.get("width", default_char_width) if isinstance(entry, dict) else default_char_width
    return total


class GameRules(BaseGameRules):
    """The Legend of Zelda: Four Swords Anniversary Edition (DSiWare, European version)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[kmsg.Kmsg] = None
        self._original = b""
        self._located: Dict[int, Optional[Tuple[kmsg.Kmsg, List[int]]]] = {}

    def get_display_name(self) -> str:
        return "Zelda: Four Swords Anniversary Edition"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".kmsg",), "bytes", "Four Swords Anniversary Edition KMSG"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        try:
            messages = kmsg.Kmsg(bytes(json_obj))
            groups = split_blocks(messages.ids)
            blocks = [[to_editor(messages.texts[i][kmsg.EN_EU] or b"") for i in group] for group in groups]
        except kmsg.FormatError as error:
            log_debug(f"zelda_fsae: not a KMSG file ({error})")
            self._file = None
            return [[]], {}
        self._file, self._original = messages, bytes(json_obj)
        names = {str(n): BLOCKS[block_of(messages.ids[group[0]])][1] for n, group in enumerate(groups)}
        return blocks, names

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        messages, changed = self._file, False
        for group, block in zip(split_blocks(messages.ids), data or []):
            for index, text in zip(group, block or []):
                raw = messages.texts[index][kmsg.EN_EU] or b""
                # An untouched text keeps its exact bytes, whatever the editor form would encode to.
                if text is not None and text != to_editor(raw):
                    messages.texts[index][kmsg.EN_EU] = from_editor(text)
                    changed = True
        return messages.build() if changed else self._original

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                self._file, self._original = kmsg.Kmsg(raw), bytes(raw)
                return
            except kmsg.FormatError as error:
                log_warning(f"zelda_fsae: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._file = None
        self._original = b""
        self._located.clear()

    # -- where a string comes from -----------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[kmsg.Kmsg, List[int]]]:
        """``(parsed source file, message indices)`` of a data block; cached per load."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            project_idx = block_map.get(block_idx, block_idx)
            sub = sum(1 for d, p in block_map.items() if p == project_idx and d < block_idx)
            block = pm.project.blocks[project_idx]
            messages = kmsg.Kmsg(Path(pm.get_absolute_path(block.source_file)).read_bytes())
            found = (messages, split_blocks(messages.ids)[sub])
        except (AttributeError, IndexError, KeyError, OSError, TypeError, kmsg.FormatError) as error:
            log_debug(f"zelda_fsae: no KMSG file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int) -> Optional[Tuple[int, str, tuple]]:
        """``(message id, English editor text, BLOCKS entry)``."""
        located = self._locate(block_idx)
        try:
            index = located[1][int(string_idx)] if located else None
        except (IndexError, TypeError, ValueError):
            return None
        if index is None:
            return None
        messages = located[0]
        message_id = messages.ids[index]
        return message_id, to_editor(messages.texts[index][kmsg.EN_EU] or b""), BLOCKS[block_of(message_id)]

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._message(block_idx, string_idx)
        return {"id": found[0], "block": found[2][1]} if found else None

    # -- AI and story context --------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        context: Dict[str, Any] = {"content_role": found[2][2]}
        if not found[2][3]:
            context["has_speaker"] = False
        return context

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        if not found or not found[2][3]:
            return None
        match = _SPEAKER_RE.search(found[1])
        if match:
            return SPEAKERS.get(int(match.group(1)))
        if found[2][0] == 300:
            return GREAT_FAIRIES.get(found[0], "Great Fairy")
        return None

    def is_placeholder_speaker(self, name: str) -> bool:
        return str(name).startswith("npc:")

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        result: Dict[str, Any] = {"resource": "eu.kmsg", "label": str(found[0]), "msg_group": found[2][1]}
        speaker = self.get_speaker_for_string(block_idx, string_idx)
        if speaker:
            result["candidate_actors"] = [speaker]
        return result

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        speaker = self.get_speaker_for_string(block_idx, string_idx)
        where = f"{found[2][1]}, message {found[0]}"
        return f"{where}, spoken by {speaker}" if speaker and not self.is_placeholder_speaker(speaker) else where

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """The cutscene lines of one range (prologue, Great Fairies, Vaati and the ending) are one story."""
        found = self._message(block_idx, string_idx)
        return f"fsae:{found[2][0]}" if found and found[2][3] else None

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Items from the item get messages, places from the place-coloured words, the speakers."""
        messages = self._project_file()
        if messages is None:
            return []
        seen, entries = set(), []

        def add(term: str, section: str, description: str, ref: str) -> None:
            term = " ".join(term.split())
            if term and term not in seen:
                seen.add(term)
                entries.append({"term": term, "section": section, "description": description, "source_ref": ref})

        for message_id, texts in zip(messages.ids, messages.texts):
            text = to_editor(texts[kmsg.EN_EU] or b"")
            ref = f"eu.kmsg message {message_id}"
            item = _ITEM_RE.match(text)
            if item:
                add(item.group(1), "Items", "Item (Four Swords Anniversary Edition)", ref)
            for place in _PLACE_RE.findall(text):
                if place[:1].isupper():
                    add(place, "Places", "Place or object name (Four Swords Anniversary Edition)", ref)
        for name in [*SPEAKERS.values(), *GREAT_FAIRIES.values()]:
            if not self.is_placeholder_speaker(name):
                add(name, "Characters", "Character (Four Swords Anniversary Edition)", "eu.kmsg speakers")
        return entries

    def _project_file(self) -> Optional[kmsg.Kmsg]:
        try:
            pm = self.mw.project_manager
            for block in pm.project.blocks:
                if str(block.source_file).lower().endswith(".kmsg"):
                    return kmsg.Kmsg(Path(pm.get_absolute_path(block.source_file)).read_bytes())
        except (AttributeError, OSError, TypeError, kmsg.FormatError) as error:
            log_debug(f"zelda_fsae: no KMSG file in the project: {error}")
        return None

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution", "glossary_seed", "external_reference"}

    def get_external_reference_url(self, term: str) -> Optional[str]:
        if not term or not term.strip():
            return None
        return f"https://zeldawiki.wiki/wiki/Special:Search?search={urllib.parse.quote(term.strip())}"

    # -- reference languages -------------------------------------------------------

    def supports_reference_patch(self) -> bool:
        """The Russian build's ``eu.kmsg`` and the game's other languages (``all.kmsg``) are the references."""
        return True

    def get_reference_language_label(self) -> str:
        return "Russian (RU)"

    def load_reference_patch(self, patch_path: str, block_names=None) -> Dict[Tuple[int, int], str]:
        return self.load_multi_reference(patch_path, block_names).get(self.get_reference_language_label(), {})

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """Every language of the KMSG files at ``patch_path`` (a file, or a folder with ``eu.kmsg`` /
        ``all.kmsg``, also in ``nitrofs``), matched by message id. An English (EU) slot written in Cyrillic
        is the Russian translation."""
        where: Dict[int, Tuple[int, int]] = {}
        for key in (block_names or {}):
            located = self._locate(int(key))
            if located:
                for string_idx, index in enumerate(located[1]):
                    where[located[0].ids[index]] = (int(key), string_idx)
        result: Dict[str, Dict[Tuple[int, int], str]] = {}
        for path in _reference_files(Path(patch_path)):
            try:
                messages = kmsg.Kmsg(path.read_bytes())
            except (OSError, kmsg.FormatError) as error:
                log_warning(f"zelda_fsae: reference {path}: {error}")
                continue
            for slot in range(1, kmsg.SLOTS):
                texts = kmsg.slot_texts(messages, slot)
                if not texts:
                    continue
                decoded = {}
                for message_id, raw in texts.items():
                    try:
                        decoded[message_id] = to_editor(raw)
                    except kmsg.FormatError:
                        continue
                cyrillic = any("Ѐ" <= ch <= "ӿ" for text in decoded.values() for ch in text)
                label = "Russian (RU)" if slot == kmsg.EN_EU and cyrillic else kmsg.LANGUAGES[slot]
                if not label or label in result:
                    continue
                result[label] = {where[i]: text for i, text in decoded.items() if i in where}
        return result

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The widest line the game's own languages have in that range (the lines are broken by hand)."""
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        width = found[2][4]
        return {"warn_width": width, "max_width": width, "font_file": FONT_FILE}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 10) -> Optional[int]:
        return max(line_width(line, font_map or {}, default_char_width) for line in str(text).split("\n"))

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE


def _reference_files(path: Path) -> List[Path]:
    if path.is_file():
        return [path]
    found = []
    for folder in (path, path / "nitrofs", path / "source"):
        found += [folder / name for name in ("eu.kmsg", "all.kmsg") if (folder / name).is_file()]
    return found
