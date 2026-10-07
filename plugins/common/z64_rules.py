"""Shared rules of the N64 Zelda plugins: open a ROM, save a translated ROM, line widths.

A game plugin subclasses ``Zelda64Rules`` and fills in its text format, the
ROM layouts it supports, the font width table and the line limits.  Translated
letters are written into the font slots of ``translation_map.json`` (the
project's, else the plugin's): ``{"Б": "À"}`` saves Б as the byte of À.  Every
save is rebuilt from the SOURCE ROM, so repeated saves do not grow the file;
text that outgrows its range moves to free address space and the code that
loads it is retargeted.  Every other file the translation ROM changed (textures,
fonts written by the Textures window and the Font Editor) is carried into the
rebuilt ROM.  A layout may list more message tables (credits); a plugin may add
blocks of fixed-length strings outside the tables (``fixed_strings``); a table
may use its own text format (``table_format``).  Font width tables in ``code``
edited by the Font Editor are carried into the rebuilt ``code``.
"""
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common import z64_text
from plugins.common.n64_rom import N64Rom, retarget_constant
from plugins.common.z64_text import Message, TextFormat
from utils.constants import user_plugin_file_or_shipped
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

_TAG_RE = re.compile(r"\{[^{}]*\}")
# Actor overlay names (En_Go2) stand in for speakers the decomp gives no description.
_ACTOR_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]*_[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class RomLayout:
    code_file: int          # dmadata index of `code` (holds the message table)
    text_file: int          # dmadata index of the English message_data_static
    table_offset: int       # message table offset in decompressed `code`
    text_references: int    # lui/addiu pairs in `code` that load the text file's address
    # More message tables in `code`, one block each: (block name, text file, table offset, references).
    extra_tables: Tuple[Tuple[str, int, int, int], ...] = ()

    def tables(self) -> List[Tuple[str, int, int, int]]:
        """Every message table, the main one first (its block name comes from the game)."""
        return [("", self.text_file, self.table_offset, self.text_references), *self.extra_tables]


class Zelda64Rules(BaseGameRules):
    """Base of zelda_oot64 / zelda_mm64; the subclass sets the class attributes below."""

    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    game_name = ""
    text_format: TextFormat = None
    layouts: Dict[Tuple[bytes, int], RomLayout] = {}   # (game code at 0x3B, version byte at 0x3F)
    segment = 0x07
    font_widths: List[int] = []         # advance of characters from 0x20 up
    line_width = 0                      # widest retail line, in font units
    type_line_width: Dict[int, int] = {}
    message_buffer_size = 1280          # Font.msgBuf: one stored message, header included
    data_dir = ""                       # plugin folder holding context.json (plugins.common.zelda64_context)

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.source_rom: Optional[N64Rom] = None
        self.messages: List[Message] = []
        self.tables: List[List[Message]] = []     # every table's messages; tables[0] is self.messages
        self.edited_rom: Optional[N64Rom] = None  # the translation ROM a save keeps other edits from
        self._button_widths = {
            f"{{{control.name}}}": self._char_width(code)
            for code, control in self.text_format.controls.items() if not control.args and code >= 0x20
        }
        self._font_map_names = [source["font_map"] for source in self.get_font_sources() if source.get("font_map")]

    def get_display_name(self) -> str:
        return self.game_name

    def get_capabilities(self) -> Set[str]:
        """Speakers and glossary terms come from the decompilation (``context.json``)."""
        return {"glossary_seed", "speaker_attribution"} if self._context()["messages"] else set()

    # -- context mined from the decompilation ---------------------------------------------

    def _context(self) -> Dict[str, Any]:
        cached = getattr(self, "_context_cache", None)
        if cached is None:
            cached = {"messages": {}, "glossary": []}
            path = os.path.join(self.data_dir, "context.json")
            if self.data_dir and os.path.isfile(path):
                try:
                    with open(path, encoding="utf-8") as stream:
                        cached = json.load(stream)
                except (OSError, ValueError) as error:
                    log_warning(f"{self.game_name}: cannot read context.json: {error}")
            self._context_cache = cached
        return cached

    def _message_context(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        if block_idx != 0 or not 0 <= int(string_idx) < len(self.messages):
            return {}
        return self._context()["messages"].get(f"0x{self.messages[int(string_idx)].message_id:04X}", {})

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """The one actor whose code shows this message; None when several or none do."""
        speakers = self._message_context(block_idx, string_idx).get("speakers") or []
        return speakers[0] if len(speakers) == 1 else None

    def is_placeholder_speaker(self, name: str) -> bool:
        """Actor overlay names are ids; decomp descriptions ("Romani") are names."""
        return bool(_ACTOR_NAME_RE.match(str(name or "")))

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """Item-get and place-name messages carry their own role."""
        entry = self._message_context(block_idx, string_idx)
        if entry.get("place"):
            return {"content_role": "PlaceName", "has_speaker": False, "glossary_section": "Places",
                    "force_glossary": True,
                    "role_instruction": 'PLACE NAMES: "content_role": "PlaceName" is a location title, not '
                                        "dialogue. Translate it as a proper place name, consistently."}
        if entry.get("item"):
            return {"content_role": "ItemGet", "has_speaker": False, "glossary_section": "Items",
                    "role_instruction": 'ITEM MESSAGES: "content_role": "ItemGet" is the box shown when the '
                                        "player receives an item; the item name must match the glossary."}
        return {}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """Actors whose code shows the line and the scenes they stand in (any setup)."""
        entry = self._message_context(block_idx, string_idx)
        result: Dict[str, Any] = {}
        if entry.get("speakers") or entry.get("actors"):
            result["candidate_actors"] = list(entry.get("speakers") or entry.get("actors"))
        if entry.get("scenes"):
            result["location_candidates"] = list(entry["scenes"])
        return result

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Items, places, characters and highlighted terms named by the game and its decompilation."""
        return [{"term": item["term"], "section": item.get("section", "Terms"),
                 "description": item.get("note", ""), "blocks": [0],
                 "source_ref": "messages " + ", ".join(item.get("message_ids", [])[:8])}
                for item in self._context()["glossary"]]

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".z64", ".n64", ".v64"), "bytes", "N64 ROM")]

    # -- loading and saving -----------------------------------------------------------

    def layout_of(self, rom: N64Rom) -> RomLayout:
        key = (bytes(rom.data[0x3B:0x3F]), rom.data[0x3F])
        layout = self.layouts.get(key)
        if layout is None:
            supported = ", ".join(f"{code.decode()} v{version}" for code, version in self.layouts)
            raise ValueError(f"Unsupported ROM {key[0]!r} v{key[1]}: {self.game_name} supports {supported}")
        return layout

    def _read_rom(self, raw: bytes) -> Tuple[N64Rom, List[List[Message]]]:
        """The ROM and the messages of each of its tables."""
        rom = N64Rom(raw)
        layout = self.layout_of(rom)
        code = rom.read_file(layout.code_file)
        tables = [z64_text.read_messages(self.table_format(i), code, offset, rom.read_file(text_file))
                  for i, (_name, text_file, offset, _refs) in enumerate(layout.tables())]
        return rom, tables

    def _use_base(self, rom: N64Rom, tables: List[List[Message]]) -> None:
        self.source_rom, self.tables, self.messages = rom, tables, tables[0]

    def table_format(self, table: int) -> TextFormat:
        """The text format of message table ``table`` (0 = the main one). The game's format by default."""
        return self.text_format

    def fixed_strings(self, rom: N64Rom) -> List[Tuple[str, List[str]]]:
        """Blocks of text outside the message tables: ``[(block name, strings)]``. None by default."""
        return []

    def write_fixed_strings(self, rom: N64Rom, blocks: List[List[str]], changes: Dict[int, bytes]) -> None:
        """Encode the blocks of ``fixed_strings`` into ``changes`` (dmadata index -> new file; ``code`` is
        already there when the save changed it)."""

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        rom, tables = self._read_rom(bytes(json_obj))
        if self.source_rom is None:
            self._use_base(rom, tables)
        names = [f"{self.game_name} messages"] + [name for name, *_rest in self.layout_of(rom).extra_tables]
        blocks = [[self.decode_text(m.body, self.table_format(i)) for m in messages]
                  for i, messages in enumerate(tables)]
        for name, strings in self.fixed_strings(rom):
            names.append(name)
            blocks.append(strings)
        return blocks, {str(i): name for i, name in enumerate(names)}

    # -- translated letters ---------------------------------------------------------------

    def translation_map(self) -> Dict[str, str]:
        """``{letter: font character}`` from ``<project>/translation_map.json``, else the plugin's."""
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None)
        path = os.path.join(project_dir, "translation_map.json") if project_dir else ""
        if not path or not os.path.isfile(path):
            path = str(user_plugin_file_or_shipped(os.path.basename(self.data_dir), "translation_map.json"))
        try:
            stamp = (path, os.path.getmtime(path))
        except OSError:
            return {}
        if getattr(self, "_translation_map_stamp", None) != stamp:
            try:
                with open(path, encoding="utf-8") as stream:
                    raw = json.load(stream)
            except (OSError, ValueError) as error:
                log_warning(f"{self.game_name}: cannot read {path}: {error}")
                raw = {}
            self._translation_map_cache = {k: v for k, v in raw.items()
                                           if isinstance(v, str) and len(k) == 1 and len(v) == 1}
            self._translation_map_stamp = stamp
        return self._translation_map_cache

    def letter_slots(self) -> Dict[str, int]:
        """``{letter: font byte}``: the translation map with each font character as its byte."""
        slots = {}
        for letter, char in self.translation_map().items():
            code = self.text_format.by_char.get(char, ord(char))
            if code < 0x100:
                slots[letter] = code
        return slots

    def decode_text(self, body: bytes, fmt: Optional[TextFormat] = None) -> str:
        """Body bytes -> editor text, a slot read back as the letter drawn there.  Look-alike slots (a Latin
        letter or digit, the apostrophe) stay as they are: the English text shares them."""
        text = (fmt or self.text_format).decode(body)
        reverse = {char: letter for letter, char in self.translation_map().items()
                   if not (char.isascii() and (char.isalnum() or char == "'"))}
        return "".join(reverse.get(ch, ch) for ch in text) if reverse else text

    def prepare_save_context(self, context) -> None:
        """Build every save from the source ROM (the last version offered); keep the translation copy
        (the first one) for the files the text save does not rebuild: textures, fonts."""
        versions = list(context.existing_versions())
        self.edited_rom = None
        for raw in reversed(versions):
            try:
                self._use_base(*self._read_rom(raw))
                break
            except ValueError as error:
                log_warning(f"{self.game_name}: cannot use a ROM version as the save base: {error}")
        if len(versions) > 1:
            try:
                self.edited_rom = N64Rom(versions[0])
            except ValueError as error:
                log_warning(f"{self.game_name}: cannot read the translated ROM: {error}")

    def _edited_files(self, rebuilt: Set[int]) -> Dict[int, bytes]:
        """Files of the translation ROM that differ from the source, except the ones the save rebuilds."""
        rom, edited = self.source_rom, self.edited_rom
        if edited is None or len(edited.files) != len(rom.files):
            return {}
        changes = {}
        for index, (entry, old) in enumerate(zip(rom.files, edited.files)):
            if index in rebuilt or entry[2] == 0xFFFFFFFF:
                continue
            size = (entry[3] or entry[2] + entry[1] - entry[0]) - entry[2]
            old_size = (old[3] or old[2] + old[1] - old[0]) - old[2]
            if entry == old and rom.data[entry[2]:entry[2] + size] == edited.data[old[2]:old[2] + old_size]:
                continue
            content = edited.read_file(index)
            if content != rom.read_file(index):
                changes[index] = content
        return changes

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self.source_rom is None:
            raise ValueError(f"Open the {self.game_name} ROM before saving")
        rom = self.source_rom
        layout = self.layout_of(rom)
        tables = layout.tables()
        slots = self.letter_slots()
        code = original_code = rom.read_file(layout.code_file)
        changes = self._edited_files({layout.code_file} | {table[1] for table in tables})
        moved: Dict[int, int] = {}
        free = rom.free_vrom()
        if len(data) < len(tables):
            raise ValueError(f"Expected {len(tables)} message blocks, got {len(data)}")
        for number, ((_name, text_index, offset, references), messages, texts) in enumerate(
                zip(tables, self.tables, data)):
            if len(texts) != len(messages):
                raise ValueError(f"Expected {len(messages)} messages, got {len(texts)}")
            fmt = self.table_format(number)
            edited = [Message(m.message_id, m.header, fmt.encode(str(text), slots), m.info)
                      for m, text in zip(messages, texts)]
            for message in edited:
                size = len(message.header) + len(message.body) + 1
                if size > self.message_buffer_size:
                    raise ValueError(f"Message {message.message_id:#06x} is {size} bytes; the game reads at most "
                                     f"{self.message_buffer_size}")
            text_file, code = z64_text.build_messages(fmt, edited, code, offset, self.segment)
            text_file += b"\0" * (-len(text_file) % 16)
            if len(text_file) > rom.file_capacity(text_index):
                moved[text_index] = free
                free = (free + len(text_file) + 0xF) & ~0xF
                code = retarget_constant(code, rom.files[text_index][0], moved[text_index], references)
            if text_file != rom.read_file(text_index):
                changes[text_index] = text_file
        code = self._carry_font_widths(code, layout.code_file)
        if code != original_code:
            changes[layout.code_file] = code
        self.write_fixed_strings(rom, list(data[len(tables):]), changes)
        return rom.replace_files(changes, moved) if changes else bytes(rom.data)

    def _carry_font_widths(self, code: bytes, code_file: int) -> bytes:
        """``code`` with the font width tables (``font_sources.json``, ``widths_file`` = ``code``) of the
        translation ROM: the Font Editor writes widths there, and the text save rebuilds ``code``."""
        edited = self.edited_rom
        if edited is None or len(edited.files) != len(self.source_rom.files):
            return code
        regions = []
        for source in self.get_font_sources():
            params = source.get("params") or {}
            if source.get("format") == "n64" and "widths_file" in params and int(str(params["widths_file"]), 0) == code_file:
                regions.append((int(str(params["widths_offset"]), 0), 4 * int(str(params["widths_count"]), 0)))
        if not regions or edited.files[code_file] == self.source_rom.files[code_file]:
            return code
        edited_code = edited.read_file(code_file)
        out = bytearray(code)
        for start, size in regions:
            out[start:start + size] = edited_code[start:start + size]
        return bytes(out)

    # -- width and editing --------------------------------------------------------------

    def _char_width(self, code: int) -> int:
        index = code - 0x20
        return self.font_widths[index] if 0 <= index < len(self.font_widths) else 0

    def _editor_widths(self) -> Dict[str, Any]:
        """The Font Editor's width map for this game's font (``<project>/font_maps/<name>.json``), once saved."""
        maps = getattr(self.mw, "all_font_maps", None) or {}
        for name in self._font_map_names:
            if maps.get(name):
                return maps[name]
        return {}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        """Width in font units: the Font Editor's map, else the game's table, for characters; the table for
        buttons; other tags take none."""
        # ponytail: runtime values ({rupees-total}, timers) count as zero width; give them a sample if lines overflow.
        text = str(text)
        editor = self._editor_widths()
        slots = self.letter_slots()
        total = sum(self._button_widths.get(tag, 0) for tag in _TAG_RE.findall(text))
        for ch in _TAG_RE.sub("", text):
            entry = editor.get(ch)
            if isinstance(entry, dict) and "width" in entry:
                total += int(entry["width"])
                continue
            code = slots[ch] if ch in slots else self.text_format.by_char.get(ch, ord(ch))
            total += self._char_width(code) if 0x20 <= code < 0x20 + len(self.font_widths) else default_char_width
        return total

    def textbox_type(self, message: Message) -> int:
        """The message's textbox type; games keep it in different places."""
        return 0

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Line width by the message's textbox type."""
        if block_idx != 0 or not 0 <= int(string_idx) < len(self.messages):
            return None
        width = self.type_line_width.get(self.textbox_type(self.messages[int(string_idx)]), self.line_width)
        return {"max_width": width, "warn_width": width, "lines_per_page": 4}

    def analyze_subline(self, text: str, next_text: Optional[str], subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int, is_last_subline_in_data_string: bool,
                        editor_font_map: Optional[Dict] = None, editor_line_width_threshold: Optional[int] = None,
                        full_data_string_text_for_logical_check: Optional[str] = None,
                        is_target_for_debug: bool = False, logical_hard_limit: Optional[int] = None) -> Set[str]:
        threshold = editor_line_width_threshold or self.line_width
        full_text = text if full_data_string_text_for_logical_check is None else full_data_string_text_for_logical_check
        return super().analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor,
            is_last_subline_in_data_string, editor_font_map or {}, threshold, full_text,
            is_target_for_debug, logical_hard_limit=logical_hard_limit,
        )

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return 4
