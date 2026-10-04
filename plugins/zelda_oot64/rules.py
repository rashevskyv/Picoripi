"""Ocarina of Time (N64) plugin: opens the US 1.0 ROM itself and saves a translated ROM.

All 2,115 English messages form one block.  The shared ``Zelda64Rules`` rebuilds the
text file and the message table from the source ROM on every save and moves text
that outgrows its range.  Numbers come from zeldaret/oot (ntsc-1.0).
"""
import os
from typing import Dict, Optional

from plugins.common.z64_rules import RomLayout, Zelda64Rules
from plugins.common.z64_text import Message

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .msg_codec import FORMAT, SEGMENT
from .tag_manager import TagManager

# code = file 27, nes_message_data_static = file 22, sNesMessageEntryTable at 0xFD9EC in code.
# NTSC builds load the English text's address once (z_message.c); the font-order message
# 0xFFFC that Font_LoadOrderedFont addresses directly lives in the Japanese file there.
LAYOUTS = {(b"CZLE", 0): RomLayout(code_file=27, text_file=22, table_offset=0xFD9EC, text_references=1)}
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
