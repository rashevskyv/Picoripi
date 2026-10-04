"""The Wind Waker (GameCube) plugin: zel_00.bmg in res/Msg/bmgres.arc.

Wind Waker and Twilight Princess share the JSystem BMG format, so this class reuses
the Twilight Princess rules for reading, saving, aliases, preview and checks, and
replaces only what is game data: the escape-tag catalogue, the color table, the
INF1 attributes and the per-window line width.  Sources: zeldaret/tww
(``include/f_op/f_op_msg_mng.h``, ``src/f_op/f_op_msg_mng.cpp``, ``src/d/d_msg.cpp``).
"""
import os
from typing import Any, Dict, Optional

from plugins.zelda_bmg.rules import GameRules as TwilightPrincessRules

from .tag_catalog import COLOR_NAMES, COLOR_TABLE, WW_CATALOG

plugin_dir = os.path.dirname(os.path.abspath(__file__))

# INF1 textbox type (byte 0x0C of the entry) -> what the player sees (d_msg.cpp, d_message.cpp).
TEXTBOX_TYPES = {
    0: "Talk", 1: "Item-style notice", 2: "Sign", 5: "Prologue caption",
    6: "Board or tablet", 7: "Letter", 8: "Talk (closes by itself)", 9: "Item get",
    10: "Talk (fixed position)", 11: "Item name", 12: "Hylian text",
    13: "Picto Box notice", 14: "Wind Waker conducting",
}

# Widths in font units (cell 24; the game draws the font at 23 px, so units = px x 24/23).
# The game wraps mid-word once a line reaches 503 px (419 px in an item-get box with its
# icon), so the longest allowed line is one pixel less.  The warning sits at the centring
# width, 486 / 402 px, which English text keeps to with few exceptions.
TALK_WIDTH = 523
TALK_WARN_WIDTH = 507
ITEM_GET_WIDTH = 436
ITEM_GET_WARN_WIDTH = 419
_ITEM_GET = 9


def decode_ww_attributes(info: bytes) -> Optional[Dict[str, int]]:
    """The 20 INF1 bytes after the DAT1 offset (JMSMesgEntry_c), or None if too short."""
    if len(info) < 20:
        return None
    return {
        "message_id": int.from_bytes(info[0:2], "big"),
        "item_price": int.from_bytes(info[2:4], "big", signed=True),
        "next_message_id": int.from_bytes(info[4:6], "big"),
        "textbox_type": info[8],
        "draw_type": info[9],
        "textbox_position": info[10],
        "item_image": info[11],
        "alignment": info[12],
        "initial_sound": info[13],
        "initial_camera": info[14],
        "initial_animation": info[15],
        "lines_per_page": info[18],
    }


class GameRules(TwilightPrincessRules):
    """Zelda: The Wind Waker (GameCube)."""

    escape_catalog = WW_CATALOG
    color_table = COLOR_TABLE
    color_names = {name: index for index, name in COLOR_NAMES.items()} | {"default": 0, "gray": 7}
    data_dir = plugin_dir

    # Kind sets the inherited speaker/glossary code reads, in Wind Waker textbox types.
    _NAME_CARD_KINDS = {11: "Items"}
    _ITEM_WINDOW_KIND = _ITEM_GET
    _NON_CONVERSATIONAL_KINDS = {1, 2, 5, 6, 7, 9, 11, 13, 14}
    _SYSTEM_VOICE_KINDS = {2, 6, 9, 11, 13, 14}
    _WINDOW_SPEAKERS: Dict[int, str] = {}

    def get_display_name(self) -> str:
        """Get the display name."""
        return "Zelda: The Wind Waker (GameCube BMG)"

    def get_capabilities(self):
        """Lore from the wiki and terms from item windows; no speakers or window chrome yet."""
        return {"glossary_seed", "external_lore", "external_reference"}

    def get_dynamic_name_tags(self) -> dict:
        """The player name is the only name the game inserts at runtime."""
        return {"{PLAYER}": "Link", "{escape:0:0000}": "Link"}

    def replace_runtime_names_for_ai(self, text: str) -> str:
        """Show the language model Link instead of the player-name escape."""
        result = str(text or "")
        for tag in ("{PLAYER}", "{F:Link}", "{f:Link}", "{escape:0:0000}"):
            result = result.replace(tag, "Link")
        return result

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, int]]:
        """Decoded INF1 attributes, with the textbox type also under the key the
        inherited kind-based code reads (``fuki_kind``)."""
        try:
            string_idx = int(string_idx)
        except (TypeError, ValueError):
            return None
        bmg, _, _ = self._get_bmg_for_block(block_idx)
        messages = getattr(bmg, "messages", None) or []
        if not (0 <= string_idx < len(messages)):
            return None
        attrs = decode_ww_attributes(getattr(messages[string_idx], "info", b""))
        if attrs is not None:
            attrs["fuki_kind"] = attrs["textbox_type"]
        return attrs

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """Tell the translator which kind of box the text sits in."""
        attrs = self.get_message_attributes(block_idx, string_idx)
        if not attrs:
            return {}
        kind = attrs["textbox_type"]
        return {"window_type": TEXTBOX_TYPES.get(kind, f"Textbox type {kind}")}

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Line width and lines per page from the message's own INF1 entry."""
        attrs = self.get_message_attributes(block_idx, string_idx)
        if not attrs:
            return None
        item_get = attrs["textbox_type"] == _ITEM_GET
        layout: Dict[str, Any] = {
            "max_width": ITEM_GET_WIDTH if item_get else TALK_WIDTH,
            "warn_width": ITEM_GET_WARN_WIDTH if item_get else TALK_WARN_WIDTH,
        }
        if attrs["lines_per_page"]:
            layout["lines_per_page"] = attrs["lines_per_page"]
        return layout

    def get_preview_window_style(self, block_idx: Optional[int] = None,
                                 string_idx: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Box name and lines per page only: no geometry, so the generic preview
        draws the text (Wind Waker window frames are not drawn yet)."""
        attrs = self.get_message_attributes(block_idx, string_idx) if block_idx is not None else None
        if not attrs:
            return None
        kind = attrs["textbox_type"]
        style: Dict[str, Any] = {"kind_name": TEXTBOX_TYPES.get(kind, f"Textbox type {kind}")}
        if attrs["lines_per_page"]:
            style["lines_per_page"] = attrs["lines_per_page"]
        return style
