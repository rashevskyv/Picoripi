"""Shared rules of the N64 Zelda plugins: open a ROM, save a translated ROM, line widths.

A game plugin subclasses ``Zelda64Rules`` and fills in its text format, the
ROM layouts it supports, the font width table and the line limits.  Every
save is rebuilt from the SOURCE ROM, so repeated saves do not grow the file;
text that outgrows its range moves to free address space and the code that
loads it is retargeted.
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

    def _read_rom(self, raw: bytes) -> Tuple[N64Rom, List[Message]]:
        rom = N64Rom(raw)
        layout = self.layout_of(rom)
        messages = z64_text.read_messages(self.text_format, rom.read_file(layout.code_file),
                                          layout.table_offset, rom.read_file(layout.text_file))
        return rom, messages

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        rom, messages = self._read_rom(bytes(json_obj))
        if self.source_rom is None:
            self.source_rom, self.messages = rom, messages
        return [[self.text_format.decode(m.body) for m in messages]], {"0": f"{self.game_name} messages"}

    def prepare_save_context(self, context) -> None:
        """Build every save from the source ROM: it is the last version offered."""
        for raw in reversed(list(context.existing_versions())):
            try:
                self.source_rom, self.messages = self._read_rom(raw)
                return
            except ValueError as error:
                log_warning(f"{self.game_name}: cannot use a ROM version as the save base: {error}")

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self.source_rom is None:
            raise ValueError(f"Open the {self.game_name} ROM before saving")
        texts = data[0] if data else []
        if len(texts) != len(self.messages):
            raise ValueError(f"Expected {len(self.messages)} messages, got {len(texts)}")
        rom = self.source_rom
        layout = self.layout_of(rom)
        edited = [Message(m.message_id, m.header, self.text_format.encode(str(text)), m.info)
                  for m, text in zip(self.messages, texts)]
        for message in edited:
            size = len(message.header) + len(message.body) + 1
            if size > self.message_buffer_size:
                raise ValueError(f"Message {message.message_id:#06x} is {size} bytes; the game reads at most "
                                 f"{self.message_buffer_size}")
        code = rom.read_file(layout.code_file)
        text_file, code_file = z64_text.build_messages(self.text_format, edited, code, layout.table_offset,
                                                       self.segment)
        text_file += b"\0" * (-len(text_file) % 16)
        moved = {}
        if len(text_file) > rom.file_capacity(layout.text_file):
            moved[layout.text_file] = rom.free_vrom()
            code_file = retarget_constant(code_file, rom.files[layout.text_file][0], moved[layout.text_file],
                                          layout.text_references)
        changes = {}
        if text_file != rom.read_file(layout.text_file):
            changes[layout.text_file] = text_file
        if code_file != code:
            changes[layout.code_file] = code_file
        return rom.replace_files(changes, moved) if changes else bytes(rom.data)

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
        total = sum(self._button_widths.get(tag, 0) for tag in _TAG_RE.findall(text))
        for ch in _TAG_RE.sub("", text):
            entry = editor.get(ch)
            if isinstance(entry, dict) and "width" in entry:
                total += int(entry["width"])
                continue
            code = self.text_format.by_char.get(ch, ord(ch))
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
