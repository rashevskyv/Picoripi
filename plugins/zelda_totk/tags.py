"""TotK MSBT control tags: the catalogue, and the readable ``{tags}`` the editor shows.

Catalogue source: the public TotK game config of AeonSake's MSBT Editor (``configs/TotK.gcf``,
gitlab.com/AeonSake/msbt-editor) -- group/type numbers, argument types and value names.

Editor form:
  ``{name}`` / ``{name:arg:arg}``  a known tag whose bytes it reproduces exactly (``{color:2}``,
                                   ``{icon:AButton0}``, ``{ruby:4:かんじ}``, ``{playerName}``)
  ``{tag:G:T}`` / ``{tag:G:T:hex}``  any other tag, raw
  ``{/name}`` / ``{/tag:G:T}``     a closing tag
A tag is only shown by name when its readable form encodes back to the same bytes, so a file always
round-trips (the codec is ``plugins.common.lms_tags``).
"""
from __future__ import annotations

from typing import Dict, Tuple

from plugins.common.lms_tags import TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

_ICONS = (
    "LStickUp LStickDown LStickLeft LStickRight RStickUpDown RStickRightLeft DPadUp DPadDown DPadLeft "
    "DPadRight AButton0 AButton1 JumpButton0 YButton ZLTrigger0 ZLTrigger1 SprintButton0 SprintButton1 "
    "SprintButton2 SprintButton3 SprintButton4 RBumper0 LBumper PlusButton MinusButton RightArrow LeftArrow "
    "UpArrow DownArrow UpRightArrow UpLeftArrow DownLeftArrow DownRightArrow LStick RStick LStickLeftRight "
    "NintendoSwitch JumpButton1 XButton2 BButton XButton1 PristineWeaponSparkle RBumper1 DPadUpDown RoyalCrest"
).split()
_FONTS = {-1: "Default", 0: "Ancient", 1: "Thin", 2: "ThinOutlined", 3: "Unknown", 4: "Normal",
          5: "NormalOutlined", 6: "Bold", 7: "TitleDeco", 8: "Title"}
_EMOTIONS = ("Normal_Face Pleasure_Face Anger_Face Sorrow_Face Surprise_Face Thinking_Face Serious_Face "
             "Normal Pleasure Angry Sorrow Surprise Thinking Serious").split()

# Value names for an argument: (tag name, argument index) -> {value: name}
VALUE_NAMES: Dict[Tuple[str, int], Dict[int, str]] = {
    ("icon", 0): dict(enumerate(_ICONS)),
    ("font", 0): _FONTS,
    ("emotion", 0): dict(enumerate(_EMOTIONS)),
}

_REF = ("str", "s16")
_NUM = ("str", "s16", "bool")
# (group, type) -> (name, argument types, description)
TAGS: Dict[Tuple[int, int], Tuple[str, Tuple[str, ...], str]] = {
    (0, 0): ("ruby", ("u16", "str"), "Ruby text drawn above the next N bytes of text"),
    (0, 1): ("font", ("s16",), "Font face"),
    (0, 2): ("size", ("u16",), "Text size in percent"),
    (0, 3): ("color", ("s16",), "Text colour by id; -1 or 65535 = default"),
    (0, 4): ("pageBreak", (), "Starts a new dialogue page"),
    # Group 1 as the real 1.4.0 text uses it (the .gcf had u16 "delay"/"sound"; every real one is 4 bytes):
    (1, 0): ("pause", ("u32",), "Pause in frames before the rest of the text is typed"),
    (1, 1): ("textSpeed", ("f32",), "Typing speed from here on (1 = normal, 0.5 = half speed)"),
    (1, 3): ("autoAdvance", ("u32",), "The message closes by itself this many frames after it is shown"),
    (1, 4): ("icon", ("u8",), "Button or symbol icon"),
    (2, 1): ("string1", _REF, "Inserted string"),
    (2, 2): ("number2", _NUM, "Inserted number"),
    (2, 3): ("currentHorseName", (), "Name of the current horse"),
    (2, 4): ("selectedHorseName", (), "Name of the selected horse"),
    (2, 7): ("cookingAdjective", (), "Cooking adjective"),
    (2, 8): ("cookingEffectCaption", (), "Cooking effect caption"),
    (2, 9): ("number9", _NUM, "Inserted number"),
    (2, 11): ("string11", _REF, "Inserted string"),
    (2, 12): ("string12", _REF, "Inserted string"),
    (2, 14): ("number14", _NUM, "Inserted number"),
    (2, 15): ("number15", _NUM, "Inserted number"),
    (2, 16): ("number16", ("str", "s16", "bool", "bool"), "Inserted number (with delimiter flag)"),
    (2, 18): ("number18", _NUM, "Inserted number"),
    (2, 19): ("number19", _NUM, "Inserted number"),
    (2, 20): ("number20", _NUM, "Inserted number"),
    (2, 21): ("number21", _REF, "Inserted number"),
    (2, 22): ("number22", _REF, "Inserted number"),
    (2, 24): ("attachmentAdjective", (), "Fused material adjective"),
    (2, 25): ("equipmentBaseName", (), "Equipment base name"),
    (2, 26): ("essenceAdjective", (), "Essence adjective"),
    (2, 27): ("essenceBaseName", (), "Essence base name"),
    (2, 28): ("weaponName", (), "Weapon name"),
    (2, 29): ("playerName", (), "The player's name (Link)"),
    (2, 30): ("questItemName", (), "Quest item name"),
    (2, 31): ("string31", _REF, "Inserted string"),
    (2, 32): ("string32", _REF, "Inserted string"),
    (2, 33): ("string33", _REF, "Inserted string"),
    (2, 35): ("yonaName", (), "Yona's name, or ??? before meeting her"),
    (2, 36): ("string36", _REF, "Inserted string"),
    (2, 37): ("recipeName", (), "Cooking recipe name"),
    (3, 0): ("emotion", ("u8", "bool"), "Speaker's facial expression (second argument: no voice)"),
    (3, 1): ("italic", (), "Italic font"),
    (4, 0): ("voice", ("str",), "Voice clip"),
    (5, 0): ("delay8", (), "Pause of 8 frames"),
    (5, 1): ("delay15", (), "Pause of 15 frames"),
    (5, 2): ("delay30", (), "Pause of 30 frames"),
    (7, 0): ("tallLine", (), "Extra line height for accented capitals"),
    (15, 0): ("resetFont", (), "Back to the dialogue's default font style"),
    (201, 0): ("wordInfo", ("u8", "u8", "u8", "bool"),
               "Grammar of a word: gender, definite article, indefinite article, plural"),
    (201, 1): ("defArticle", (), "Definite article chosen by wordInfo"),
    (201, 2): ("indefArticle", (), "Indefinite article chosen by wordInfo"),
    (201, 3): ("capitalizeNext", (), "Upper-case the first letter of the next word"),
    (201, 4): ("lowercaseNext", (), "Lower-case the first letter of the next word"),
    (201, 5): ("gender", ("str", "str", "str"), "Masculine / feminine / neuter form, chosen by wordInfo"),
    (201, 6): ("plural", ("str", "str", "str"),
               "Plural forms by count (EUru: ends in 1 / ends in 2-4 / other)"),
    (201, 7): ("batchimObject", ("str", "str"), "Korean particle after consonant / vowel"),
    (201, 8): ("batchimDirection", ("str", "str"), "Korean particle after consonant / vowel"),
    (201, 9): ("nounCase", ("u8",), "Grammatical case of the next noun"),
    (201, 10): ("gender10", ("str",) * 12, "Twelve forms chosen by wordInfo"),
}
CODEC = TagCodec(TAGS, VALUE_NAMES)
render_tag = CODEC.render_tag
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
