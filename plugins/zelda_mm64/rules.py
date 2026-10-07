"""Majora's Mask (N64) plugin: opens the US ROM itself and saves a translated ROM.

Blocks: the 4,589 messages, the 45 credits messages (Ocarina of Time's codes), the strings the
code prints itself (owl-warp places, "Rupee(s)", time speed, mask-code colours) and the title
screen's "PRESS START".  The shared ``Zelda64Rules`` rebuilds the text files and the message
tables from the source ROM on every save and moves text that outgrows its range.  Numbers come
from zeldaret/mm (n64-us).
"""
import json
import os
import struct
from typing import Dict, List, Optional, Tuple

from plugins.common.n64_rom import N64Rom
from plugins.common.z64_rules import RomLayout, Zelda64Rules
from plugins.common.z64_text import Message, TextFormat
from utils.logging_utils import log_warning

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .msg_codec import CREDITS_FORMAT, FORMAT, SEGMENT
from .tag_manager import TagManager

# code = file 31, message_data_static = file 29, sMessageTableNES at 0x1210D8 in code;
# z_message.c loads the text file's address in four places.  The credits
# (staff_message_data_static = file 30) have their own table right after it, loaded once.
LAYOUTS = {(b"NZSE", 0): RomLayout(code_file=31, text_file=29, table_offset=0x1210D8, text_references=4,
                                    extra_tables=(("Credits", 30, 0x12A048, 1),))}
CODE_FILE = 31
# Strings z_message_nes.c prints itself, in `code`: (offset, bytes, length field offset, length field size).
# A length field of size 0: the code always prints all the bytes (blanks pad a shorter string).
CODE_STRINGS = (
    *((0x12AC54 + 16 * i, 16, 0x12AD04 + 2 * i, 2) for i in range(11)),   # sOwlWarpTextENG
    (0x12AC30, 8, 0x12AC50, 1),                                          # sRupeesTextLocalization[ENG]
    *((0x12AE18 + 4 * i, 4, 0, 0) for i in range(3)),                     # sTimeSpeedTextENG
    *((0x12AE28 + 6 * i, 6, 0x12AE40 + i, 1) for i in range(4)),          # sMaskCodeTextENG
)
# The title screen (ovl_En_Mag = file 169) draws "PRESS START" as ten cells of the ordered font
# (sPressStartFontIndices), with a gap after the fifth; sFontOrdering in `code` (ends with 0x8C) gives
# the message-font glyph of every cell.
TITLE_FILE, TITLE_OFFSET, TITLE_WORD = 169, 0x3654, 5
FONT_ORDER_OFFSET, FONT_ORDER_LAST = 0x118070, 0x8C
# sNESFontWidths (src/code/z_message_nes.c): advance of characters 0x20-0xBF.
FONT_WIDTHS = [
    8, 8, 6, 9, 9, 14, 12, 3, 7, 7, 7, 9, 4, 6, 4, 9, 10, 5, 9, 9, 10, 9, 9, 9, 9, 9, 6, 6, 9, 11, 9, 11,
    13, 12, 9, 11, 11, 8, 8, 12, 10, 4, 8, 10, 8, 13, 11, 13, 9, 13, 10, 10, 9, 10, 11, 15, 11, 10, 10, 7, 10, 7,
    10, 9, 5, 8, 9, 8, 9, 9, 6, 9, 8, 4, 6, 8, 4, 12, 9, 9, 9, 9, 7, 8, 7, 8, 9, 12, 8, 9, 8, 7, 5, 7, 10, 6,
    12, 12, 12, 12, 11, 8, 8, 8, 8, 6, 6, 6, 6, 10, 13, 13, 13, 13, 10, 10, 10, 10, 9, 8, 8, 8, 8, 8, 9, 9, 9, 9,
    4, 4, 4, 4, 8, 9, 9, 9, 9, 8, 8, 8, 8, 8, 11, 6, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
]
# The widest line of the retail English text in font units, per textbox type: the
# Bombers' Notebook (6) draws smaller and fits more.
MAX_LINE_WIDTH = 281
TYPE_LINE_WIDTH = {6: 312}
# The reference seed: Ukrainian carried over from Majora's Mask 3D, keyed by N64 message id.
SEED_NAME = "mm3d_seed.json"


class GameRules(Zelda64Rules):
    """Zelda: Majora's Mask (N64)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager

    game_name = "Zelda: Majora's Mask (N64)"
    text_format = FORMAT
    layouts = LAYOUTS
    segment = SEGMENT
    font_widths = FONT_WIDTHS
    data_dir = os.path.dirname(os.path.abspath(__file__))
    line_width = MAX_LINE_WIDTH
    type_line_width = TYPE_LINE_WIDTH

    def textbox_type(self, message: Message) -> int:
        return message.header[0]

    def table_format(self, table: int) -> TextFormat:
        return CREDITS_FORMAT if table == 1 else FORMAT

    # -- strings outside the message tables ---------------------------------------------

    def _font_char(self, code: int) -> str:
        return FORMAT.charmap.get(code) or chr(code)

    def _title_cells(self, rom: N64Rom) -> List[int]:
        """The message-font character code of every ordered-font cell (glyph 0 is the blank)."""
        code = rom.read_file(CODE_FILE)
        order = code[FONT_ORDER_OFFSET:FONT_ORDER_OFFSET + code[FONT_ORDER_OFFSET:].index(FONT_ORDER_LAST) + 1]
        return [0x20 + glyph for glyph in order]

    def fixed_strings(self, rom: N64Rom) -> List[Tuple[str, List[str]]]:
        if len(rom.files) <= TITLE_FILE:
            return []
        code = rom.read_file(CODE_FILE)
        strings = []
        for offset, size, length_at, length_size in CODE_STRINGS:
            length = int.from_bytes(code[length_at:length_at + length_size], "big") if length_size else size
            strings.append(self.decode_text(code[offset:offset + min(length, size)]).rstrip("\0"))
        cells = self._title_cells(rom)
        indices = rom.read_file(TITLE_FILE)[TITLE_OFFSET:TITLE_OFFSET + 2 * TITLE_WORD]
        title = self.decode_text(bytes(cells[i] for i in indices))
        title = f"{title[:TITLE_WORD].strip()} {title[TITLE_WORD:].strip()}".strip()
        return [("Interface strings", strings), ("Title screen", [title])]

    def _encode_plain(self, text: str, what: str) -> bytes:
        """Font characters only: a tag or a character the font lacks is refused."""
        raw = FORMAT.encode(str(text), self.letter_slots())
        if any(byte < 0x20 or byte in FORMAT.controls for byte in raw):
            raise ValueError(f"{what} {text!r}: only letters the font has, no tags")
        return raw

    def write_fixed_strings(self, rom: N64Rom, blocks: List[List[str]], changes: Dict[int, bytes]) -> None:
        if len(blocks) < 2:
            return
        code = bytearray(changes.get(CODE_FILE) or rom.read_file(CODE_FILE))
        for (offset, size, length_at, length_size), text in zip(CODE_STRINGS, blocks[0]):
            raw = self._encode_plain(text, "Interface string")
            if len(raw) > size:
                raise ValueError(f"Interface string {text!r}: room for {size} characters")
            code[offset:offset + size] = raw.ljust(size, b"\0" if length_size else b" ")
            if length_size:
                code[length_at:length_at + length_size] = len(raw).to_bytes(length_size, "big")
        if bytes(code) != (changes.get(CODE_FILE) or rom.read_file(CODE_FILE)):
            changes[CODE_FILE] = bytes(code)

        index_of = {}
        for index, char_code in enumerate(self._title_cells(rom)):
            index_of.setdefault(char_code, index)
        first, _space, second = str(blocks[1][0] if blocks[1] else "").strip().partition(" ")
        if len(first) > TITLE_WORD or len(second.strip()) > TITLE_WORD:
            raise ValueError(f"Title screen text {blocks[1][0]!r}: its two words have room for {TITLE_WORD} "
                             f"characters each")
        raw = self._encode_plain(first.ljust(TITLE_WORD) + second.strip().ljust(TITLE_WORD), "Title screen text")
        missing = "".join(sorted({self._font_char(byte) for byte in raw if byte not in index_of}))
        if missing:
            raise ValueError(f"Title screen text {blocks[1][0]!r}: the title font has no {missing}")
        overlay = bytearray(rom.read_file(TITLE_FILE))
        overlay[TITLE_OFFSET:TITLE_OFFSET + 2 * TITLE_WORD] = bytes(index_of[byte] for byte in raw)
        if bytes(overlay) != rom.read_file(TITLE_FILE):
            changes[TITLE_FILE] = bytes(overlay)

    # -- reference: a Ukrainian draft carried over from Majora's Mask 3D --------------------

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return "Ukrainian (MM3D)"

    def load_reference_patch(self, patch_path: str, block_names=None) -> Dict[Tuple[int, int], str]:
        """(0, string) -> text from a seed JSON, ``{"messages": {"0x0004": {"uk": ..., "index": 2}}}``.

        ``patch_path`` is the file or the folder holding ``mm3d_seed.json``.  Messages are
        matched by id against the open ROM; with no ROM open, by the stored table index.
        """
        path = os.path.join(patch_path, SEED_NAME) if os.path.isdir(patch_path) else patch_path
        try:
            with open(path, encoding="utf-8") as stream:
                entries = json.load(stream).get("messages", {})
        except (OSError, ValueError, AttributeError) as error:
            log_warning(f"{self.game_name}: cannot read the reference seed {path}: {error}")
            return {}
        index_of = {m.message_id: i for i, m in enumerate(self.messages)}
        result = {}
        for message_id, entry in entries.items():
            index = index_of.get(int(message_id, 16)) if index_of else entry.get("index")
            if isinstance(index, int) and entry.get("uk"):
                result[(0, index)] = entry["uk"]
        return result

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, int]]:
        """The message id and its 11-byte header, decoded (zeldaret/mm HEADER macro)."""
        if block_idx != 0 or not 0 <= int(string_idx) < len(self.messages):
            return None
        message = self.messages[int(string_idx)]
        box, item, next_id, price1, price2, unknown = struct.unpack(">HBHHHH", message.header)
        return {"message_id": message.message_id, "textbox_type": box >> 8, "textbox_position": box & 0xFF,
                "item_icon": item, "next_message_id": next_id, "first_price": price1,
                "second_price": price2, "unknown": unknown}
