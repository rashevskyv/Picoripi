"""Authoritative Twilight Princess BMG escape-tag catalogue.

The catalogue mirrors ``TAGS.md``.  It deliberately separates a tag's
semantic meaning from its preview representation: control tags are understood
but invisible, runtime values get readable placeholders, and outfont controls
produce vector icon specifications for the BFN preview.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


ICON_TAG_WIDTH = 24

# Real in-game icon textures, decoded from the retail BTI resources
# (res/Layout/main2D.arc and itemicon.arc) into PNGs.
ICON_TEXTURE_DIR = Path(__file__).resolve().parent / "icons"

_ESCAPE_RE = re.compile(r"\{escape:(\d+):([0-9a-fA-F]{4,})\}")

_COLOR_NAMES = {
    0: "white",
    1: "red",
    2: "green",
    3: "blue",
    4: "yellow",
    5: "light-blue",
    6: "purple",
    7: "white-2",
    8: "orange",
}


@dataclass(frozen=True)
class EscapeTagSpec:
    group: int
    code: int
    name: str
    meaning: str
    render: str = "control"  # control | text | dynamic | icon | color | scale | ruby
    preview_text: str = ""
    icon: dict[str, Any] | None = None


def _icon(kind: str, label: str, color: str, *, fg: str = "#ffffff",
          texture: str | None = None, tint: str | None = None,
          rot: int = 0, flip_y: bool = False, no_shadow: bool = False) -> dict[str, Any]:
    """Preview spec for a do_outfont icon.

    ``texture`` names a PNG in ``plugins/zelda_bmg/icons/`` decoded from the
    game's own BTI resources (main2D.arc / itemicon.arc); ``tint`` is the TEV
    white color the game applies in COutFont_c::createPane.  The kind/label/
    color triple stays as a vector fallback when the texture is unavailable.
    """
    spec: dict[str, Any] = {"kind": kind, "label": label, "color": color, "fg": fg,
                            "width": ICON_TAG_WIDTH}
    if texture:
        spec["texture"] = str(ICON_TEXTURE_DIR / texture)
        spec["tint"] = tint or "#ffffff"
        if rot:
            spec["rot"] = rot
        if flip_y:
            spec["flip_y"] = True
        if no_shadow:
            spec["no_shadow"] = True
    return spec


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
    (0x0A, "ABTN", "GameCube A button", "icon", "", _icon("circle", "A", "#62a32e", texture="font_00.png", tint="#62a32e")),
    (0x0B, "BBTN", "GameCube B button", "icon", "", _icon("circle", "B", "#c82727", texture="font_01.png", tint="#c82727")),
    (0x0C, "CSTICK", "GameCube C-stick", "icon", "", _icon("stick", "C", "#c8a032", texture="font_09.png", tint="#ffc832")),
    (0x0D, "LBTN", "GameCube L trigger", "icon", "", _icon("trigger", "L", GC_GRAY, texture="font_04.png", tint=GLYPH)),
    (0x0E, "RBTN", "GameCube R trigger", "icon", "", _icon("trigger", "R", GC_GRAY, texture="font_05.png", tint=GLYPH)),
    (0x0F, "XBTN", "GameCube X button", "icon", "", _icon("circle", "X", GC_GRAY, texture="font_02.png", tint=GLYPH)),
    (0x10, "YBTN", "GameCube Y button", "icon", "", _icon("circle", "Y", GC_GRAY, texture="font_03.png", tint=GLYPH)),
    (0x11, "ZBTN", "GameCube Z button", "icon", "", _icon("trigger", "Z", "#5046a5", texture="font_06.png", tint="#5046a5")),
    (0x12, "DPAD", "GameCube D-pad", "icon", "", _icon("dpad", "", GLYPH, texture="font_08.png", tint=GLYPH)),
    (0x13, "STICK_CROSS", "Analog stick", "icon", "", _icon("stick", "", GLYPH, texture="font_07_01.png", tint=GLYPH)),
    (0x14, "LEFT_ARROW", "Left arrow", "icon", "", _icon("char", "◄", GLYPH, texture="font_10.png", tint=GLYPH, rot=90)),
    (0x15, "RIGHT_ARROW", "Right arrow", "icon", "", _icon("char", "►", GLYPH, texture="font_10.png", tint=GLYPH, rot=270)),
    (0x16, "UP_ARROW", "Up arrow", "icon", "", _icon("char", "▲", GLYPH, texture="font_10.png", tint=GLYPH, flip_y=True)),
    (0x17, "DOWN_ARROW", "Down arrow", "icon", "", _icon("char", "▼", GLYPH, texture="font_10.png", tint=GLYPH)),
    (0x18, "STICK_UP", "Analog stick up", "icon", "", _icon("stick_direction", "↑", GLYPH, texture="font_07_01.png", tint=GLYPH)),
    (0x19, "STICK_DOWN", "Analog stick down", "icon", "", _icon("stick_direction", "↓", GLYPH, texture="font_07_01.png", tint=GLYPH)),
    (0x1A, "STICK_LEFT", "Analog stick left", "icon", "", _icon("stick_direction", "←", GLYPH, texture="font_07_01.png", tint=GLYPH)),
    (0x1B, "STICK_RIGHT", "Analog stick right", "icon", "", _icon("stick_direction", "→", GLYPH, texture="font_07_01.png", tint=GLYPH)),
    (0x1C, "STICK_VERTICAL", "Analog stick vertically", "icon", "", _icon("stick_direction", "↕", GLYPH, texture="font_07_01.png", tint=GLYPH)),
    (0x1D, "STICK_HORIZONTAL", "Analog stick horizontally", "icon", "", _icon("stick_direction", "↔", GLYPH, texture="font_07_01.png", tint=GLYPH)),
    # do_arrow2: the choice cursor is drawn (icon 29, font_10 tinted red,
    # mirrored+rotated to point right) and the cursor ALWAYS advances by
    # fontSize + charSpace, so these reserve icon width even though they keep
    # their control alias.
    (0x1E, "INLINE_2_NEXT", "Next entry in a two-way inline choice", "control", "",
     _icon("char", "►", "#ff5050", texture="font_10.png", tint="#ff5050", rot=270)),
    (0x1F, "INLINE_2_FIRST", "First entry in a two-way inline choice", "control", "",
     _icon("char", "►", "#ff5050", texture="font_10.png", tint="#ff5050", rot=270)),
    (0x20, "AWAIT_CHOICE", "Wait for a choice and insert its options", "control", "", None),
    (0x21, "UNK_33", "No visible operation", "control", "", None),
    (0x22, "HORSE_NAME", "Horse name", "dynamic", "Epona", None),
    (0x23, "RED_TARGET", "Red targeting reticle", "icon", "", _icon("reticle", "", "#dc3232", texture="font_15.png", tint="#dc3232")),
    (0x24, "YELLOW_TARGET", "Yellow targeting reticle", "icon", "", _icon("reticle", "", "#ffc832", texture="font_15.png", tint="#ffc832")),
    (0x25, "INPUT_VALUE", "Numeric input with a Rupee icon", "dynamic", "⟨input value⟩", None),
    (0x26, "ACKNOWLEDGE", "Acknowledge control; draws nothing", "control", "", None),
    (0x27, "ABTN_STAR", "GameCube A button with a star", "icon", "", _icon("button_star", "A", "#00ffb4", texture="font_12.png", tint="#00ffb4")),
    (0x28, "DEMOBOX", "Timed demo message window", "control", "", None),
    (0x29, "SCENT_NAME", "Current wolf-sense scent name", "dynamic", "⟨scent name⟩", None),
    (0x2A, "WHITE_TARGET", "White targeting reticle", "icon", "", _icon("reticle", "", "#ffffff", texture="font_15.png", tint="#ffffff")),
    (0x2B, "PORTAL_NAME", "Portal name", "dynamic", "⟨portal name⟩", None),
    (0x2C, "WARP_ICON", "Warp portal icon", "icon", "", _icon("diamond", "", "#aaffff", texture="im_map_icon_portal_4ia_40_05.png", tint="#aaffff")),
    (0x2D, "BOMB_NAME", "Selected bomb type name", "dynamic", "⟨bomb name⟩", None),
    (0x2E, "XYBTN", "X or Y item button", "icon", "", _icon("split_button", "X/Y", GC_GRAY, texture="font_02.png", tint=GLYPH)),
    (0x2F, "YXBTN", "Y or X item button", "icon", "", _icon("split_button", "Y/X", GC_GRAY, texture="font_03.png", tint=GLYPH)),
    (0x30, "BOMB_BAG_ICON", "Bomb bag icon", "icon", "", _icon("bag", "", "#464646", texture="st_bompoach_lv1.png")),
    (0x31, "BOMB_NUM", "Current bomb count", "dynamic", "⟨bomb count⟩", None),
    (0x32, "BOMB_PRICE", "Bomb price", "dynamic", "⟨bomb price⟩", None),
    (0x33, "INLINE_3_NEXT", "Next entry in a three-way inline choice", "control", "",
     _icon("char", "►", "#ff5050", texture="font_10.png", tint="#ff5050", rot=270)),
    (0x34, "INLINE_3_FIRST", "First entry in a three-way inline choice", "control", "",
     _icon("char", "►", "#ff5050", texture="font_10.png", tint="#ff5050", rot=270)),
    (0x35, "WORD", "Runtime word substitution", "dynamic", "⟨runtime word⟩", None),
    (0x36, "BOXATLEAST", "Minimum message-box constraint", "control", "", None),
    (0x37, "BOMB_MAX", "Maximum bomb capacity", "dynamic", "⟨max bombs⟩", None),
    (0x38, "ARROW_MAX", "Maximum arrow capacity", "dynamic", "⟨max arrows⟩", None),
    (0x39, "HEART", "Heart icon", "icon", "", _icon("char", "♥", "#ff3232", texture="font_13.png", tint="#ff3232")),
    (0x3A, "QUAVER", "Musical note icon", "icon", "", _icon("char", "♪", "#ffffff", texture="font_14.png", tint="#ffffff")),
    (0x3B, "INSECT_NAME", "Selected insect name", "dynamic", "⟨insect name⟩", None),
    (0x3C, "LETTER_NAME", "Selected letter name", "dynamic", "⟨letter name⟩", None),
    (0x3D, "LINE_DOWN", "Move the current line down by a pixel amount", "control", "", None),
    (0x3E, "CURRENT_LETTER_PAGE", "Current letter page", "dynamic", "⟨current page⟩", None),
    (0x3F, "MAX_LETTER_PAGE", "Total letter pages", "dynamic", "⟨total pages⟩", None),
]


_GROUP_3 = [
    (0x00, "WII_MSGID_OVERRIDE", "Override the Wii message ID", "control", "", None),
    (0x01, "WII_ABTN", "Wii Remote A button", "icon", "", _icon("wii_button", "A", WII_BODY, fg=WII_FG, texture="font_00.png", tint="#62a32e")),
    (0x02, "WII_BBTN", "Wii Remote B trigger", "icon", "", _icon("wii_trigger", "B", WII_BODY, fg=WII_FG, texture="font_24.png")),
    (0x03, "WII_HOMEBTN", "Wii Remote HOME button", "icon", "", _icon("wii_button", "⌂", WII_BODY, fg=WII_FG, texture="font_25.png")),
    (0x04, "WII_MINUSBTN", "Wii Remote minus button", "icon", "", _icon("wii_button", "−", WII_BODY, fg=WII_FG, texture="font_40.png")),
    (0x05, "WII_PLUSBTN", "Wii Remote plus button", "icon", "", _icon("wii_button", "+", WII_BODY, fg=WII_FG, texture="font_39.png")),
    (0x06, "WII_1BTN", "Wii Remote 1 button", "icon", "", _icon("wii_button", "1", WII_BODY, fg=WII_FG, texture="font_41.png")),
    (0x07, "WII_2BTN", "Wii Remote 2 button", "icon", "", _icon("wii_button", "2", WII_BODY, fg=WII_FG, texture="font_42.png")),
    (0x08, "WII_DPAD_ITEM", "Wii Remote D-pad item control", "icon", "", _icon("dpad", "", GLYPH, texture="font_23.png")),
    (0x09, "WII_DPAD_UP", "Wii Remote D-pad up", "icon", "", _icon("dpad_direction", "↑", GLYPH, texture="font_22.png")),
    (0x0A, "WII_DPAD_DOWN", "Wii Remote D-pad down", "icon", "", _icon("dpad_direction", "↓", GLYPH, texture="font_50.png")),
    (0x0B, "WII_DPAD_HORIZONTAL", "Wii Remote D-pad horizontally", "icon", "", _icon("dpad_direction", "↔", GLYPH, texture="font_49.png")),
    (0x0C, "WII_DPAD_RIGHT", "Wii Remote D-pad right", "icon", "", _icon("dpad_direction", "→", GLYPH, texture="font_51.png")),
    (0x0D, "WII_DPAD_LEFT", "Wii Remote D-pad left", "icon", "", _icon("dpad_direction", "←", GLYPH, texture="font_52.png")),
    (0x0E, "WII_WIIMOTE", "Wii Remote", "icon", "", _icon("wiimote", "", WII_BODY, fg=WII_FG, texture="font_35.png")),
    (0x0F, "WII_RETICULE", "Wii pointer reticle", "icon", "", _icon("reticle", "", "#78d2ff", texture="font_53.png")),
    (0x10, "WII_NUNCHUK", "Nunchuk controller", "icon", "", _icon("nunchuk", "", WII_BODY, fg=WII_FG, texture="font_36.png")),
    (0x11, "WII_WIIMOTE2", "Wii Remote variant 2", "icon", "", _icon("wiimote", "", WII_BODY, fg=WII_FG, texture="font_35.png")),
    (0x12, "WII_FAIRY", "Fairy pointer", "icon", "", _icon("char", "✦", "#ffffff", texture="font_33.png")),
    (0x13, "WII_CBTN", "Nunchuk C button", "icon", "", _icon("nunchuk_button", "C", WII_BODY, fg=WII_FG, texture="font_09.png", tint="#ffc832")),
    (0x14, "WII_ZBTN", "Nunchuk Z button", "icon", "", _icon("nunchuk_button", "Z", WII_BODY, fg=WII_FG, texture="font_06.png", tint="#5046a5")),
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
    # These eight are pushed through the BFN font (push_word), not do_outfont.
    # Their width therefore comes from the active font glyph, not a 24px icon.
    (0x02, "MALE_ICON", "Male symbol", "text", "♂", None),
    (0x03, "FEMALE_ICON", "Female symbol", "text", "♀", None),
    (0x04, "STAR_ICON", "Star symbol", "text", "★", None),
    (0x05, "REFMARK", "Reference mark", "text", "※", None),
    (0x06, "THIN_LEFT_ARROW", "Thin left arrow", "text", "←", None),
    (0x07, "THIN_RIGHT_ARROW", "Thin right arrow", "text", "→", None),
    (0x08, "THIN_UP_ARROW", "Thin up arrow", "text", "↑", None),
    (0x09, "THIN_DOWN_ARROW", "Thin down arrow", "text", "↓", None),
    # createPane 0x2a paints the bullet with TEV white (0,0,0): it renders as a
    # BLACK diamond in the game (used on light sign/kanban backgrounds).
    (0x0A, "BULLET", "List bullet", "icon", "", _icon("char", "▪", "#000000", texture="font_46.png", tint="#000000", no_shadow=True)),
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
# Group 1 is a generic message-sound command.  ID 0x14 is the only value used
# by the shipped North-American TP BMG resources (18 times, before Midna's
# laugh).  Group 2 is likewise generic camera metadata; see the fallback in
# get_escape_tag_spec() for arbitrary IDs.
ESCAPE_TAGS[(1, 0x14)] = EscapeTagSpec(
    1, 0x14, "MESSAGE_SOUND_20",
    "Play message sound effect ID 20 (used before Midna's laugh)", "control"
)
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
    group = int(group)
    spec = ESCAPE_TAGS.get((group, code))
    if spec is not None:
        return spec
    if group == 1:
        return EscapeTagSpec(group, code, f"MESSAGE_SOUND_{code}", f"Play message sound effect ID {code}")
    if group == 2:
        return EscapeTagSpec(group, code, f"CAMERA_TAG_{code}", f"Set message camera tag ID {code}")
    return None


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


def canonical_escape_alias(spec: EscapeTagSpec) -> str:
    """Return the stable, readable editor alias for a tag without arguments."""
    if spec.group == 1:
        return f"{{sound:{spec.code}}}"
    if spec.group == 2:
        return f"{{camera:{spec.code}}}"
    if spec.render == "icon" and spec.icon:
        label = str(spec.icon.get("label") or spec.name).strip()
        if spec.group == 0:
            controller_names = {
                "CSTICK": "C-stick", "DPAD": "D-pad", "STICK_CROSS": "stick",
                "STICK_UP": "stick ↑", "STICK_DOWN": "stick ↓",
                "STICK_LEFT": "stick ←", "STICK_RIGHT": "stick →",
                "STICK_VERTICAL": "stick ↕", "STICK_HORIZONTAL": "stick ↔",
                "XYBTN": "X/Y", "YXBTN": "Y/X", "ABTN_STAR": "A★",
            }
            if spec.name in controller_names or spec.name.endswith("BTN"):
                label = controller_names.get(spec.name, label)
                return f"{{GC:{label}}}"
        if spec.group == 3:
            wii_names = {
                "WII_HOMEBTN": "HOME", "WII_MINUSBTN": "−", "WII_PLUSBTN": "+",
                "WII_DPAD_ITEM": "D-pad", "WII_DPAD_UP": "D-pad ↑",
                "WII_DPAD_DOWN": "D-pad ↓", "WII_DPAD_HORIZONTAL": "D-pad ↔",
                "WII_DPAD_RIGHT": "D-pad →", "WII_DPAD_LEFT": "D-pad ←",
                "WII_WIIMOTE": "Remote", "WII_WIIMOTE2": "Remote 2",
                "WII_NUNCHUK": "Nunchuk", "WII_RETICULE": "pointer",
                "WII_FAIRY": "fairy pointer", "WII_CBTN": "Nunchuk C",
                "WII_ZBTN": "Nunchuk Z",
            }
            return f"{{W:{wii_names.get(spec.name, label)}}}"
        return f"{{icon:{spec.name.lower().replace('_', '-')}}}"
    if spec.name == "PLAYER_NAME":
        return "{F:Link}"
    if spec.name == "HORSE_NAME":
        return "{F:Epona}"
    if spec.name == "PLAYER_GENITIV":
        return "{F:Link's}"
    if spec.name == "HORSE_GENITIV":
        return "{F:Epona's}"
    if spec.render == "dynamic":
        return f"{{value:{spec.name.lower().replace('_', '-')}}}"
    if spec.render == "text":
        return f"{{glyph:{spec.name.lower().replace('_', '-')}}}"
    return f"{{ctrl:{spec.name.lower().replace('_', '-')}}}"


def build_static_escape_aliases() -> dict[str, str]:
    """Build aliases for complete, argument-free escape tags.

    Argument-bearing tags are formatted dynamically so a base-code replacement
    can never corrupt a longer raw tag such as ``PAUSE + frame count``.
    """
    argument_tags = {
        "TYPE", "AUTOBOX", "BOXATMOST", "PAUSE", "DEMOBOX", "LINE_DOWN",
        "BOXATLEAST", "WII_MSGID_OVERRIDE", "COLOR", "SCALE", "RUBY",
    }
    aliases: dict[str, str] = {}
    for (group, code), spec in ESCAPE_TAGS.items():
        if spec.name in argument_tags:
            continue
        aliases[canonical_escape_alias(spec)] = f"{{escape:{group}:{code:04x}}}"
    return aliases


def escape_tag_to_editor_alias(tag: str) -> str:
    """Convert one raw tag to a readable, lossless editor token."""
    match = _ESCAPE_RE.fullmatch(str(tag))
    if not match:
        return str(tag)
    group, data = int(match.group(1)), match.group(2).lower()
    spec = get_escape_tag_spec(group, data)
    if spec is None:
        return f"{{unknown:{group}:{data}}}"
    argument = data[4:]
    if spec.name == "PAUSE" and len(argument) >= 4:
        return f"{{pause:{int(argument[:4], 16)}f}}"
    if spec.name in {"TYPE", "AUTOBOX", "BOXATMOST", "BOXATLEAST", "LINE_DOWN"} and len(argument) >= 4:
        return f"{{{spec.name.lower().replace('_', '-')}:{int(argument[:4], 16)}}}"
    if spec.name == "DEMOBOX" and len(argument) >= 8:
        return f"{{demobox:{int(argument[:8], 16)}f}}"
    if spec.name == "WII_MSGID_OVERRIDE" and len(argument) >= 8:
        return f"{{wii-msgid:{int(argument[:8], 16)}}}"
    if spec.render == "color" and len(argument) >= 2:
        index = int(argument[:2], 16)
        return f"{{color:{_COLOR_NAMES.get(index, index)}}}"
    if spec.render == "scale" and len(argument) >= 4:
        return f"{{scale:{int(argument[:4], 16)}%}}"
    if spec.render == "ruby":
        return f"{{ruby:{argument}}}"
    alias = canonical_escape_alias(spec)
    if argument:
        # Preserve undocumented/unused payload bytes losslessly.  Several TP
        # value tags carry a one-byte selector even though their visible
        # meaning is defined by the tag code itself.
        return f"{alias[:-1]}:{argument}}}"
    return alias


def fixed_escape_widths() -> dict[str, dict[str, int]]:
    """Widths that are invariant across fonts, suitable for ``font_map.json``."""
    result: dict[str, dict[str, int]] = {}
    argument_tags = {
        "TYPE", "AUTOBOX", "BOXATMOST", "PAUSE", "DEMOBOX", "LINE_DOWN",
        "BOXATLEAST", "WII_MSGID_OVERRIDE", "COLOR", "SCALE", "RUBY",
    }
    for (group, code), spec in ESCAPE_TAGS.items():
        # A JSON key is an exact string, not a tag pattern.  Adding only the
        # four-byte prefix of an argument-bearing tag would make the width trie
        # consume part of e.g. PAUSE and then measure its hex argument as text.
        if spec.name in argument_tags:
            continue
        if spec.icon is not None:
            # Anything drawn through do_outfont/do_arrow2 advances the cursor
            # by the icon cell, including the inline-choice cursor arrows that
            # keep a control alias.
            width = int(spec.icon.get("width", ICON_TAG_WIDTH))
        elif spec.render in {"control", "color", "scale", "ruby"}:
            width = 0
        else:
            continue
        raw = f"{{escape:{group}:{code:04x}}}"
        result[raw] = {"width": width}
        result[canonical_escape_alias(spec)] = {"width": width}
    return result
