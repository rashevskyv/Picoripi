"""Majora's Mask (N64) plugin: opens the US ROM itself and saves a translated ROM.

All 4,589 messages form one block.  The shared ``Zelda64Rules`` rebuilds the text
file and the message table from the source ROM on every save and moves text
that outgrows its range.  Numbers come from zeldaret/mm (n64-us).
"""
import json
import os
import struct
from typing import Dict, Optional, Tuple

from plugins.common.z64_rules import RomLayout, Zelda64Rules
from plugins.common.z64_text import Message
from utils.logging_utils import log_warning

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .msg_codec import FORMAT, SEGMENT
from .tag_manager import TagManager

# code = file 31, message_data_static = file 29, sMessageTableNES at 0x1210D8 in code;
# z_message.c loads the text file's address in four places.
LAYOUTS = {(b"NZSE", 0): RomLayout(code_file=31, text_file=29, table_offset=0x1210D8, text_references=4)}
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
