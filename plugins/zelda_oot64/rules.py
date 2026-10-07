"""Ocarina of Time (N64) plugin: opens the US 1.0 ROM itself and saves a translated ROM.

Blocks: the 2,115 English messages, the 48 credits messages, the title screen's two strings.
The shared ``Zelda64Rules`` rebuilds the text files and the message tables from the source ROM
on every save and moves text that outgrows its range.  Numbers come from zeldaret/oot (ntsc-1.0).
"""
import os
from typing import Dict, List, Optional, Tuple

from plugins.common.n64_rom import N64Rom
from plugins.common.z64_rules import RomLayout, Zelda64Rules
from plugins.common.z64_text import Message

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .msg_codec import FORMAT, SEGMENT
from .tag_manager import TagManager

# code = file 27, nes_message_data_static = file 22, sNesMessageEntryTable at 0xFD9EC in code.
# NTSC builds load the English text's address once (z_message.c); the font-order message
# 0xFFFC that Font_LoadOrderedFont addresses directly lives in the Japanese file there.
# The credits (staff_message_data_static = file 23) have their own table right after the English one.
LAYOUTS = {(b"CZLE", 0): RomLayout(code_file=27, text_file=22, table_offset=0xFD9EC, text_references=1,
                                    extra_tables=(("Credits", 23, 0x101C0C, 1),))}
# The title screen (ovl_En_Mag = file 361) draws "PRESS START" and "NO CONTROLLER" from glyph numbers of
# the ordered font (Font_LoadOrderedFont): (offset, cells before the gap the code leaves, cells after it).
TITLE_FILE = 361
TITLE_STRINGS = ((0x2DA4, 5, 5), (0x2D98, 2, 10))
# NTSC file-name encoding (include/message.h FILENAME_*): the ordered-font characters a string may use.
FILENAME_CHARS = {**{str(digit): digit for digit in range(10)},
                  **{chr(ord("A") + i): 0xAB + i for i in range(26)},
                  **{chr(ord("a") + i): 0xC5 + i for i in range(26)},
                  " ": 0xDF, "?": 0xE1, "!": 0xE2, ":": 0xE3, "-": 0xE4, "(": 0xE5, ")": 0xE6,
                  ",": 0xE9, ".": 0xEA, "/": 0xEB}
FILENAME_BY_CODE = {code: char for char, code in FILENAME_CHARS.items()}
# sFontWidths (src/code/z_message.c, NTSC): advance of characters 0x20-0xAF.
FONT_WIDTHS = [
    8, 8, 6, 9, 9, 14, 12, 3, 7, 7, 7, 9, 4, 6, 4, 9, 10, 5, 9, 9, 10, 9, 9, 9,
    9, 9, 6, 6, 9, 11, 9, 11, 13, 12, 9, 11, 11, 8, 8, 12, 10, 4, 8, 10, 8, 13, 11, 13,
    9, 13, 10, 10, 9, 10, 11, 15, 11, 10, 10, 7, 10, 7, 10, 9, 5, 8, 9, 8, 9, 9, 6, 9,
    8, 4, 6, 8, 4, 12, 9, 9, 9, 9, 7, 8, 7, 8, 9, 12, 8, 9, 8, 7, 5, 7, 10, 10,
    12, 12, 12, 12, 11, 8, 8, 8, 6, 6, 13, 13, 10, 10, 10, 9, 8, 8, 8, 8, 8, 9, 9, 9,
    9, 6, 9, 9, 9, 9, 9, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
]
# The widest line of the retail English text in font units; no textbox type is wider.
MAX_LINE_WIDTH = 291


class GameRules(Zelda64Rules):
    """Zelda: Ocarina of Time (N64)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager

    game_name = "Zelda: Ocarina of Time (N64)"
    text_format = FORMAT
    layouts = LAYOUTS
    segment = SEGMENT
    font_widths = FONT_WIDTHS
    data_dir = os.path.dirname(os.path.abspath(__file__))
    line_width = MAX_LINE_WIDTH

    def textbox_type(self, message: Message) -> int:
        return message.info >> 4

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, int]]:
        """The message id and the textbox type and position from its table entry."""
        if block_idx != 0 or not 0 <= int(string_idx) < len(self.messages):
            return None
        message = self.messages[int(string_idx)]
        return {"message_id": message.message_id, "textbox_type": message.info >> 4,
                "textbox_position": message.info & 0x0F}

    # -- title screen strings -----------------------------------------------------------

    def fixed_strings(self, rom: N64Rom) -> List[Tuple[str, List[str]]]:
        """"PRESS START" and "NO CONTROLLER": two words each, split where the code leaves its gap."""
        if len(rom.files) <= TITLE_FILE:
            return []
        overlay = rom.read_file(TITLE_FILE)
        strings = []
        for offset, before, after in TITLE_STRINGS:
            cells = "".join(FILENAME_BY_CODE.get(code, "?") for code in overlay[offset:offset + before + after])
            strings.append(f"{cells[:before].rstrip()} {cells[before:].rstrip()}".strip())
        return [("Title screen", strings)]

    def write_fixed_strings(self, rom: N64Rom, blocks: List[List[str]], changes: Dict[int, bytes]) -> None:
        """Each word fills its cells, padded with blanks; a longer word or a character the title font
        lacks is refused."""
        if not blocks:
            return
        overlay = bytearray(changes.get(TITLE_FILE) or rom.read_file(TITLE_FILE))
        for (offset, before, after), text in zip(TITLE_STRINGS, blocks[0]):
            first, _space, second = str(text).strip().partition(" ")
            if len(first) > before or len(second) > after:
                raise ValueError(f"Title screen text {text!r}: its two words have room for {before} and "
                                 f"{after} characters")
            cells = first.ljust(before) + second.ljust(after)
            missing = "".join(sorted({char for char in cells if char not in FILENAME_CHARS}))
            if missing:
                raise ValueError(f"Title screen text {text!r}: the title font has no {missing}")
            overlay[offset:offset + before + after] = bytes(FILENAME_CHARS[char] for char in cells)
        if bytes(overlay) != rom.read_file(TITLE_FILE):
            changes[TITLE_FILE] = bytes(overlay)
