"""Authoritative Twilight Princess BMG escape-tag catalogue.

The catalogue mirrors ``TAGS.md``.  It deliberately separates a tag's
semantic meaning from its preview representation: control tags are understood
but invisible, runtime values get readable placeholders, and outfont controls
produce vector icon specifications for the BFN preview.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ICON_TAG_WIDTH = 24


@dataclass(frozen=True)
class EscapeTagSpec:
    group: int
    code: int
    name: str
    meaning: str
    render: str = "control"  # control | text | dynamic | icon | color | scale | ruby
    preview_text: str = ""
    icon: dict[str, Any] | None = None


def _icon(kind: str, label: str, color: str, *, fg: str = "#ffffff") -> dict[str, Any]:
    return {"kind": kind, "label": label, "color": color, "fg": fg, "width": ICON_TAG_WIDTH}


GC_GRAY = "#8c8c8c"
WII_BODY = "#e8e8e8"
WII_FG = "#222222"
GLYPH = "#c8c8c8"


_GROUP_0 = [
    (0x00, "PLAYER_NAME", "Player name", "dynamic", "Link", None),
    (0x01, "INSTANT", "Show following text instantly", "control", "", None),
    (0x02, "TYPE", "Message-window type", "control", "", None),
    (0x03, "UNK_3", "Autobox-compatible control", "control", "", None),
    (0x04, "AUTOBOX", "Automatically close the message window", "control", "", None),
    (0x05, "BOXATMOST", "Maximum message-box constraint", "control", "", None),
    (0x06, "UNK_6", "Ignored by the game renderer", "control", "", None),
    (0x07, "PAUSE", "Pause text printing for a frame count", "control", "", None),
    (0x08, "SELECT_2WAY", "Two-way choice", "control", "", None),
    (0x09, "SELECT_3WAY", "Three-way choice", "control", "", None),
    (0x0A, "ABTN", "GameCube A button", "icon", "", _icon("circle", "A", "#62a32e")),
    (0x0B, "BBTN", "GameCube B button", "icon", "", _icon("circle", "B", "#c82727")),
    (0x0C, "CSTICK", "GameCube C-stick", "icon", "", _icon("stick", "C", "#c8a032")),
    (0x0D, "LBTN", "GameCube L trigger", "icon", "", _icon("trigger", "L", GC_GRAY)),
    (0x0E, "RBTN", "GameCube R trigger", "icon", "", _icon("trigger", "R", GC_GRAY)),
    (0x0F, "XBTN", "GameCube X button", "icon", "", _icon("circle", "X", GC_GRAY)),
    (0x10, "YBTN", "GameCube Y button", "icon", "", _icon("circle", "Y", GC_GRAY)),
    (0x11, "ZBTN", "GameCube Z button", "icon", "", _icon("trigger", "Z", "#5046a5")),
    (0x12, "DPAD", "GameCube D-pad", "icon", "", _icon("dpad", "", GLYPH)),
    (0x13, "STICK_CROSS", "Analog stick", "icon", "", _icon("stick", "", GLYPH)),
    (0x14, "LEFT_ARROW", "Left arrow", "icon", "", _icon("char", "◄", GLYPH)),
    (0x15, "RIGHT_ARROW", "Right arrow", "icon", "", _icon("char", "►", GLYPH)),
    (0x16, "UP_ARROW", "Up arrow", "icon", "", _icon("char", "▲", GLYPH)),
    (0x17, "DOWN_ARROW", "Down arrow", "icon", "", _icon("char", "▼", GLYPH)),
    (0x18, "STICK_UP", "Analog stick up", "icon", "", _icon("stick_direction", "↑", GLYPH)),
    (0x19, "STICK_DOWN", "Analog stick down", "icon", "", _icon("stick_direction", "↓", GLYPH)),
    (0x1A, "STICK_LEFT", "Analog stick left", "icon", "", _icon("stick_direction", "←", GLYPH)),
    (0x1B, "STICK_RIGHT", "Analog stick right", "icon", "", _icon("stick_direction", "→", GLYPH)),
    (0x1C, "STICK_VERTICAL", "Analog stick vertically", "icon", "", _icon("stick_direction", "↕", GLYPH)),
    (0x1D, "STICK_HORIZONTAL", "Analog stick horizontally", "icon", "", _icon("stick_direction", "↔", GLYPH)),
    (0x1E, "INLINE_2_NEXT", "Next entry in a two-way inline choice", "control", "", None),
    (0x1F, "INLINE_2_FIRST", "First entry in a two-way inline choice", "control", "", None),
    (0x20, "AWAIT_CHOICE", "Wait for a choice and insert its options", "control", "", None),
    (0x21, "UNK_33", "No visible operation", "control", "", None),
    (0x22, "HORSE_NAME", "Horse name", "dynamic", "Epona", None),
    (0x23, "RED_TARGET", "Red targeting reticle", "icon", "", _icon("reticle", "", "#dc3232")),
    (0x24, "YELLOW_TARGET", "Yellow targeting reticle", "icon", "", _icon("reticle", "", "#ffc832")),
    (0x25, "INPUT_VALUE", "Numeric input with a Rupee icon", "dynamic", "⟨input value⟩", None),
    (0x26, "ACKNOWLEDGE", "Acknowledge control; draws nothing", "control", "", None),
    (0x27, "ABTN_STAR", "GameCube A button with a star", "icon", "", _icon("button_star", "A", "#62a32e")),
    (0x28, "DEMOBOX", "Timed demo message window", "control", "", None),
    (0x29, "SCENT_NAME", "Current wolf-sense scent name", "dynamic", "⟨scent name⟩", None),
    (0x2A, "WHITE_TARGET", "White targeting reticle", "icon", "", _icon("reticle", "", "#ffffff")),
    (0x2B, "PORTAL_NAME", "Portal name", "dynamic", "⟨portal name⟩", None),
    (0x2C, "WARP_ICON", "Warp portal icon", "icon", "", _icon("diamond", "", "#00ffb4")),
    (0x2D, "BOMB_NAME", "Selected bomb type name", "dynamic", "⟨bomb name⟩", None),
    (0x2E, "XYBTN", "X or Y item button", "icon", "", _icon("split_button", "X/Y", GC_GRAY)),
    (0x2F, "YXBTN", "Y or X item button", "icon", "", _icon("split_button", "Y/X", GC_GRAY)),
    (0x30, "BOMB_BAG_ICON", "Bomb bag icon", "icon", "", _icon("bag", "", "#464646")),
    (0x31, "BOMB_NUM", "Current bomb count", "dynamic", "⟨bomb count⟩", None),
    (0x32, "BOMB_PRICE", "Bomb price", "dynamic", "⟨bomb price⟩", None),
    (0x33, "INLINE_3_NEXT", "Next entry in a three-way inline choice", "control", "", None),
    (0x34, "INLINE_3_FIRST", "First entry in a three-way inline choice", "control", "", None),
    (0x35, "WORD", "Runtime word substitution", "dynamic", "⟨runtime word⟩", None),
    (0x36, "BOXATLEAST", "Minimum message-box constraint", "control", "", None),
    (0x37, "BOMB_MAX", "Maximum bomb capacity", "dynamic", "⟨max bombs⟩", None),
    (0x38, "ARROW_MAX", "Maximum arrow capacity", "dynamic", "⟨max arrows⟩", None),
    (0x39, "HEART", "Heart icon", "icon", "", _icon("char", "♥", "#ff3232")),
    (0x3A, "QUAVER", "Musical note icon", "icon", "", _icon("char", "♪", "#ffc832")),
    (0x3B, "INSECT_NAME", "Selected insect name", "dynamic", "⟨insect name⟩", None),
    (0x3C, "LETTER_NAME", "Selected letter name", "dynamic", "⟨letter name⟩", None),
    (0x3D, "LINE_DOWN", "Move the current line down by a pixel amount", "control", "", None),
    (0x3E, "CURRENT_LETTER_PAGE", "Current letter page", "dynamic", "⟨current page⟩", None),
    (0x3F, "MAX_LETTER_PAGE", "Total letter pages", "dynamic", "⟨total pages⟩", None),
]


_GROUP_3 = [
    (0x00, "WII_MSGID_OVERRIDE", "Override the Wii message ID", "control", "", None),
    (0x01, "WII_ABTN", "Wii Remote A button", "icon", "", _icon("wii_button", "A", WII_BODY, fg=WII_FG)),
    (0x02, "WII_BBTN", "Wii Remote B trigger", "icon", "", _icon("wii_trigger", "B", WII_BODY, fg=WII_FG)),
    (0x03, "WII_HOMEBTN", "Wii Remote HOME button", "icon", "", _icon("wii_button", "⌂", WII_BODY, fg=WII_FG)),
    (0x04, "WII_MINUSBTN", "Wii Remote minus button", "icon", "", _icon("wii_button", "−", WII_BODY, fg=WII_FG)),
    (0x05, "WII_PLUSBTN", "Wii Remote plus button", "icon", "", _icon("wii_button", "+", WII_BODY, fg=WII_FG)),
    (0x06, "WII_1BTN", "Wii Remote 1 button", "icon", "", _icon("wii_button", "1", WII_BODY, fg=WII_FG)),
    (0x07, "WII_2BTN", "Wii Remote 2 button", "icon", "", _icon("wii_button", "2", WII_BODY, fg=WII_FG)),
    (0x08, "WII_DPAD_ITEM", "Wii Remote D-pad item control", "icon", "", _icon("dpad", "", GLYPH)),
    (0x09, "WII_DPAD_UP", "Wii Remote D-pad up", "icon", "", _icon("dpad_direction", "↑", GLYPH)),
    (0x0A, "WII_DPAD_DOWN", "Wii Remote D-pad down", "icon", "", _icon("dpad_direction", "↓", GLYPH)),
    (0x0B, "WII_DPAD_HORIZONTAL", "Wii Remote D-pad horizontally", "icon", "", _icon("dpad_direction", "↔", GLYPH)),
    (0x0C, "WII_DPAD_RIGHT", "Wii Remote D-pad right", "icon", "", _icon("dpad_direction", "→", GLYPH)),
    (0x0D, "WII_DPAD_LEFT", "Wii Remote D-pad left", "icon", "", _icon("dpad_direction", "←", GLYPH)),
    (0x0E, "WII_WIIMOTE", "Wii Remote", "icon", "", _icon("wiimote", "", WII_BODY, fg=WII_FG)),
    (0x0F, "WII_RETICULE", "Wii pointer reticle", "icon", "", _icon("reticle", "", "#78d2ff")),
    (0x10, "WII_NUNCHUK", "Nunchuk controller", "icon", "", _icon("nunchuk", "", WII_BODY, fg=WII_FG)),
    (0x11, "WII_WIIMOTE2", "Wii Remote variant 2", "icon", "", _icon("wiimote", "", WII_BODY, fg=WII_FG)),
    (0x12, "WII_FAIRY", "Fairy pointer", "icon", "", _icon("char", "✦", "#ffffff")),
    (0x13, "WII_CBTN", "Nunchuk C button", "icon", "", _icon("nunchuk_button", "C", WII_BODY, fg=WII_FG)),
    (0x14, "WII_ZBTN", "Nunchuk Z button", "icon", "", _icon("nunchuk_button", "Z", WII_BODY, fg=WII_FG)),
]


_GROUP_4_TEXT = {
    0x00: ("DOLLAR", "Dollar sign", "$"),
    0x01: ("BACKSLASH", "Backslash", "\\"),
    0x02: ("AT", "At sign", "@"),
    0x03: ("SHARP", "Sharp/hash sign", "#"),
    0x04: ("FLAT", "Flat sign", "♭"),
    0x05: ("ROOT", "Square-root sign", "√"),
    0x06: ("PERCENT", "Percent sign", "%"),
    0x07: ("HECTARE", "Hectare unit", "ha"),
    0x08: ("ARE", "Are area unit", "a"),
    0x09: ("LITRE", "Litre unit", "ℓ"),
    0x0A: ("WATT", "Watt unit", "W"),
    0x0B: ("CALORIE", "Calorie unit", "cal"),
    0x0C: ("CURRENCY_DOLLAR", "Dollar currency symbol", "$"),
    0x0D: ("CENT", "Cent currency symbol", "¢"),
}


_GROUP_5 = {
    0x00: ("TIME_INFO", "Timer value", "⟨timer⟩"),
    0x03: ("INSECT_INFO", "Insect information", "⟨insect info⟩"),
    0x07: ("RIVER_POINTS", "River minigame points", "⟨river points⟩"),
    0x08: ("FISH_LENGTH", "Fish length in inches", "⟨fish length⟩"),
    0x09: ("FUNDRAISE_REMAIN", "Remaining fundraising Rupees", "⟨Rupees remaining⟩"),
    0x0A: ("NEW_LETTER_NUM", "Number of new letters", "⟨new letters⟩"),
    0x0B: ("POE_NUM", "Collected Poe souls", "⟨Poe souls⟩"),
    0x0C: ("BALLOON_SCORE", "Balloon minigame score", "⟨balloon score⟩"),
    0x0D: ("FISH_COUNT", "Fish count", "⟨fish count⟩"),
    0x0E: ("ROLLGOAL_LV", "Rollgoal level", "⟨Rollgoal level⟩"),
}


_GROUP_6 = [
    (0x00, "PLAYER_GENITIV", "Player name in the genitive form", "dynamic", "Link's", None),
    (0x01, "HORSE_GENITIV", "Horse name in the genitive form", "dynamic", "Epona's", None),
    (0x02, "MALE_ICON", "Male symbol", "icon", "", _icon("char", "♂", GLYPH)),
    (0x03, "FEMALE_ICON", "Female symbol", "icon", "", _icon("char", "♀", GLYPH)),
    (0x04, "STAR_ICON", "Star symbol", "icon", "", _icon("char", "★", "#ffc832")),
    (0x05, "REFMARK", "Reference mark", "icon", "", _icon("char", "※", GLYPH)),
    (0x06, "THIN_LEFT_ARROW", "Thin left arrow", "icon", "", _icon("char", "←", GLYPH)),
    (0x07, "THIN_RIGHT_ARROW", "Thin right arrow", "icon", "", _icon("char", "→", GLYPH)),
    (0x08, "THIN_UP_ARROW", "Thin up arrow", "icon", "", _icon("char", "↑", GLYPH)),
    (0x09, "THIN_DOWN_ARROW", "Thin down arrow", "icon", "", _icon("char", "↓", GLYPH)),
    (0x0A, "BULLET", "List bullet", "icon", "", _icon("char", "▪", "#ffffff")),
    (0x0B, "BULLET_SPACE", "Indent with the width of a list bullet", "icon", "", _icon("blank", "", "#000000")),
]


ESCAPE_TAGS: dict[tuple[int, int], EscapeTagSpec] = {}
for group, rows in ((0, _GROUP_0), (3, _GROUP_3), (6, _GROUP_6)):
    for code, name, meaning, render, preview_text, icon in rows:
        ESCAPE_TAGS[(group, code)] = EscapeTagSpec(
            group, code, name, meaning, render, preview_text, icon
        )
for code, (name, meaning, text) in _GROUP_4_TEXT.items():
    ESCAPE_TAGS[(4, code)] = EscapeTagSpec(4, code, name, meaning, "text", text)
for code, (name, meaning, text) in _GROUP_5.items():
    ESCAPE_TAGS[(5, code)] = EscapeTagSpec(5, code, name, meaning, "dynamic", text)
ESCAPE_TAGS[(255, 0)] = EscapeTagSpec(255, 0, "COLOR", "Change text color", "color")
ESCAPE_TAGS[(255, 1)] = EscapeTagSpec(255, 1, "SCALE", "Change text scale", "scale")
ESCAPE_TAGS[(255, 2)] = EscapeTagSpec(255, 2, "RUBY", "Ruby/furigana annotation", "ruby")


ESCAPE_ICON_SPECS = {
    key: dict(spec.icon)
    for key, spec in ESCAPE_TAGS.items()
    if spec.icon is not None
}


def get_escape_tag_spec(group: int, data: str) -> EscapeTagSpec | None:
    """Resolve a raw escape group/data pair to its documented semantic spec."""
    if len(data) < 4:
        return None
    try:
        code = int(data[:4], 16)
    except ValueError:
        return None
    return ESCAPE_TAGS.get((int(group), code))


def describe_escape_tag(group: int, data: str) -> str:
    """Return a readable description including meaningful encoded arguments."""
    spec = get_escape_tag_spec(group, data)
    if spec is None:
        return f"Unknown escape tag (group {group}, data {data})"
    suffix = ""
    argument = data[4:]
    if spec.name == "PAUSE" and len(argument) >= 4:
        suffix = f" — {int(argument[:4], 16)} frames"
    elif spec.name in {"TYPE", "AUTOBOX", "BOXATMOST", "BOXATLEAST", "LINE_DOWN"} and len(argument) >= 4:
        suffix = f" — value {int(argument[:4], 16)}"
    elif spec.render == "color" and len(argument) >= 2:
        suffix = f" — color index {int(argument[:2], 16)}"
    elif spec.render == "scale" and len(argument) >= 4:
        suffix = f" — {int(argument[:4], 16)}%"
    return f"{spec.name}: {spec.meaning}{suffix}"

