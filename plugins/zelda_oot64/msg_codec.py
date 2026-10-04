"""Ocarina of Time (N64) messages: control codes and the extra font characters, on the shared Zelda 64 codec.

Source: zeldaret/oot ``include/message_data_fmt.h`` and ``assets/text/charmap.nes.txt``.
A message is ``body + 0x02`` with no header: the textbox type and position live
in the table entry (byte 2), messages start 4-byte aligned in
``nes_message_data_static``, the table points into segment 0x07.
"""
from plugins.common.z64_text import Control, TextFormat

NEWLINE = 0x01
END = 0x02
SEGMENT = 0x07

COLORS = {0x40: "default", 0x41: "red", 0x42: "adjustable", 0x43: "blue", 0x44: "light-blue",
          0x45: "purple", 0x46: "yellow", 0x47: "black"}
CONTROLS = {
    0x04: Control("box-break"),
    0x05: Control("color", 1, COLORS),
    0x06: Control("shift", 1),
    0x07: Control("textid", 2),
    0x08: Control("quicktext-on"),
    0x09: Control("quicktext-off"),
    0x0A: Control("persistent"),
    0x0B: Control("event"),
    0x0C: Control("box-break-delayed", 1),
    0x0D: Control("await-button-press"),
    0x0E: Control("fade", 1),
    0x0F: Control("name"),
    0x10: Control("ocarina"),
    0x11: Control("fade2", 2),
    0x12: Control("sfx", 2),
    0x13: Control("item-icon", 1),
    0x14: Control("text-speed", 1),
    0x15: Control("background", 3),
    0x16: Control("marathon-time"),
    0x17: Control("race-time"),
    0x18: Control("points"),
    0x19: Control("tokens"),
    0x1A: Control("unskippable"),
    0x1B: Control("two-choice"),
    0x1C: Control("three-choice"),
    0x1D: Control("fish-info"),
    0x1E: Control("highscore", 1),
    0x1F: Control("time"),
}
for _code, _label in {0x9F: "A", 0xA0: "B", 0xA1: "C", 0xA2: "L", 0xA3: "R", 0xA4: "Z", 0xA5: "C-up",
                      0xA6: "C-down", 0xA7: "C-left", 0xA8: "C-right", 0xA9: "target",
                      0xAA: "control-pad", 0xAB: "D-pad"}.items():
    CONTROLS[_code] = Control(f"btn:{_label}")

CHARMAP = dict(enumerate("ÀîÂÄÇÈÉÊËÏÔÖÙÛÜßàáâäçèéêëïôöùûü", start=0x80))

FORMAT = TextFormat(controls=CONTROLS, newline=NEWLINE, end=END, box_breaks=frozenset({0x04, 0x0C}),
                    charmap=CHARMAP)
