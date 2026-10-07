"""Majora's Mask (N64) messages: the 11-byte header and the control codes, on the shared Zelda 64 codec.

Source: zeldaret/mm ``include/message_data_fmt_nes.h`` and ``tools/text/msgdis.py``.
A message is ``header(11) + body + 0xBF``; messages start 4-byte aligned in
``message_data_static``, which the table entries (id, 0, 0, segment address 0x08xxxxxx)
point into.  The editor sees the body only: newline 0x11 is ``\n``, every other
control code is a ``{tag}``, and a text-box break is followed by a line break the
encoder drops; the header stays with the message untouched.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from plugins.common import z64_text
from plugins.common.z64_text import Control, Message, TextFormat
from plugins.zelda_oot64.msg_codec import CONTROLS as OOT_CONTROLS, END as OOT_END, NEWLINE as OOT_NEWLINE

END = 0xBF
NEWLINE = 0x11
HEADER_SIZE = 11
SEGMENT = 0x08

COLORS = ["default", "red", "green", "blue", "yellow", "light-blue", "pink", "silver", "orange"]
BUTTONS = {0xB0: "A", 0xB1: "B", 0xB2: "C", 0xB3: "L", 0xB4: "R", 0xB5: "Z", 0xB6: "C-up",
           0xB7: "C-down", 0xB8: "C-left", 0xB9: "C-right", 0xBA: "target", 0xBB: "control-pad"}
CONTROL: Dict[int, Tuple[str, int]] = {
    0x0A: ("text-speed", 0), 0x0B: ("hs-boat-archery", 0), 0x0C: ("stray-fairies", 0),
    0x0D: ("tokens", 0), 0x0E: ("points-tens", 0), 0x0F: ("points-thousands", 0),
    0x10: ("box-break", 0), 0x12: ("box-break2", 0), 0x13: ("carriage-return", 0),
    0x14: ("shift", 1), 0x15: ("continue", 0), 0x16: ("name", 0), 0x17: ("quicktext-on", 0),
    0x18: ("quicktext-off", 0), 0x19: ("event", 0), 0x1A: ("persistent", 0),
    0x1B: ("box-break-delayed", 2), 0x1C: ("fade", 2), 0x1D: ("fade-skippable", 2),
    0x1E: ("sfx", 2), 0x1F: ("delay", 2),
    0xC1: ("background", 0), 0xC2: ("two-choice", 0), 0xC3: ("three-choice", 0),
    0xC4: ("timer-postman", 0), 0xC5: ("timer-minigame-1", 0), 0xC6: ("timer-2", 0),
    0xC7: ("timer-moon-crash", 0), 0xC8: ("timer-minigame-2", 0), 0xC9: ("timer-env-hazard", 0),
    0xCA: ("time", 0), 0xCB: ("chest-flags", 0), 0xCC: ("input-bank", 0),
    0xCD: ("rupees-selected", 0), 0xCE: ("rupees-total", 0), 0xCF: ("time-until-moon-crash", 0),
    0xD0: ("input-doggy-racetrack-bet", 0), 0xD1: ("input-bomber-code", 0), 0xD2: ("pause-menu", 0),
    0xD3: ("time-speed", 0), 0xD4: ("owl-warp", 0), 0xD5: ("input-lottery-code", 0),
    0xD6: ("spider-house-mask-code", 0), 0xD7: ("stray-fairies-left-woodfall", 0),
    0xD8: ("stray-fairies-left-snowhead", 0), 0xD9: ("stray-fairies-left-great-bay", 0),
    0xDA: ("stray-fairies-left-stone-tower", 0), 0xDB: ("points-boat-archery", 0),
    0xDC: ("lottery-code", 0), 0xDD: ("lottery-code-guess", 0), 0xDE: ("held-item-price", 0),
    0xDF: ("bomber-code", 0), 0xE0: ("event2", 0), 0xE1: ("spider-house-mask-code-1", 0),
    0xE2: ("spider-house-mask-code-2", 0), 0xE3: ("spider-house-mask-code-3", 0),
    0xE4: ("spider-house-mask-code-4", 0), 0xE5: ("spider-house-mask-code-5", 0),
    0xE6: ("spider-house-mask-code-6", 0), 0xE7: ("hours-until-moon-crash", 0),
    0xE8: ("time-until-new-day", 0), 0xF0: ("hs-points-bank-rupees", 0), 0xF1: ("hs-points-unk-1", 0),
    0xF2: ("hs-points-fishing", 0), 0xF3: ("hs-time-boat-archery", 0),
    0xF4: ("hs-time-horse-back-balloon", 0), 0xF5: ("hs-time-lottery-guess", 0),
    0xF6: ("hs-town-shooting-gallery", 0), 0xF7: ("hs-unk-1", 0), 0xF8: ("hs-unk-3-lower", 0),
    0xF9: ("hs-horse-back-balloon", 0), 0xFA: ("hs-deku-playground-day-1", 0),
    0xFB: ("hs-deku-playground-day-2", 0), 0xFC: ("hs-deku-playground-day-3", 0),
    0xFD: ("deku-playground-name-day-1", 0), 0xFE: ("deku-playground-name-day-2", 0),
    0xFF: ("deku-playground-name-day-3", 0),
}
for _index, _color in enumerate(COLORS):
    CONTROL[_index] = (f"color:{_color}", 0)
for _code, _label in BUTTONS.items():
    CONTROL[_code] = (f"btn:{_label}", 0)

# The font's characters beyond ASCII (assets/text/charmap.nes.txt; the same as font_sources.json).
CHARMAP = {0x7F: "º", **dict(enumerate("ÀÁÂÄÇÈÉÊËÌÍÎÏÑÒÓÔÖÙÚÛÜßàáâäçèéêëìíîïñòóôöùúûü¡¿ª", start=0x80))}

FORMAT = TextFormat(
    controls={code: Control(name, args) for code, (name, args) in CONTROL.items()},
    newline=NEWLINE, end=END, box_breaks=frozenset({0x10, 0x12, 0x1B}), header_size=HEADER_SIZE,
    charmap=CHARMAP,
)


def decode_body(body: bytes) -> str:
    return FORMAT.decode(body)


def encode_body(text: str, extra_chars: Optional[Dict[str, int]] = None) -> bytes:
    return FORMAT.encode(text, extra_chars)


def read_messages(code: bytes, table_offset: int, data: bytes) -> List[Message]:
    return z64_text.read_messages(FORMAT, code, table_offset, data)


def build_messages(messages: List[Message], code: bytes, table_offset: int) -> Tuple[bytes, bytes]:
    return z64_text.build_messages(FORMAT, messages, code, table_offset, SEGMENT)


# The credits (staff_message_data_static) keep Ocarina of Time's codes: no header, newline 0x01, end 0x02
# (include/message_data_fmt_staff.h). They draw with this game's font, so its characters stay.
CREDITS_FORMAT = TextFormat(
    controls={code: control for code, control in OOT_CONTROLS.items() if code < 0x20},
    newline=OOT_NEWLINE, end=OOT_END, box_breaks=frozenset({0x04, 0x0C}), charmap=CHARMAP,
)
