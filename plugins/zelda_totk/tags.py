"""TotK MSBT control tags: the catalogue, and the readable ``{tags}`` the editor shows.

Catalogue source: the public TotK game config of AeonSake's MSBT Editor (``configs/TotK.gcf``,
gitlab.com/AeonSake/msbt-editor) -- group/type numbers, argument types and value names.

Editor form:
  ``{name}`` / ``{name:arg:arg}``  a known tag whose bytes it reproduces exactly (``{color:2}``,
                                   ``{icon:AButton0}``, ``{ruby:4:かんじ}``, ``{playerName}``)
  ``{tag:G:T}`` / ``{tag:G:T:hex}``  any other tag, raw
  ``{/name}`` / ``{/tag:G:T}``     a closing tag
A tag is only shown by name when its readable form encodes back to the same bytes, so a file always
round-trips. Arguments with an odd byte length are padded with 0xCD, as Nintendo's files are.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Tuple

from .msbt import EndTag, Tag, Token

_PAD = 0xCD

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
    (1, 0): ("delay", ("u16",), "Pause in frames"),
    (1, 3): ("sound", ("u16",), "Plays a sound"),
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
_BY_NAME = {name: key for key, (name, _types, _description) in TAGS.items()}

TAG_RE = re.compile(r"\{/?[A-Za-z][A-Za-z0-9_]*(?::[^{}:]*)*\}")
_TAG_PARTS_RE = re.compile(r"\{(/?)([A-Za-z][A-Za-z0-9_]*)((?::[^{}:]*)*)\}")
_INT_FORMATS = {"u8": "B", "bool": "B", "u16": "H", "s16": "h"}


def _decode_args(types: Tuple[str, ...], params: bytes, e: str) -> Optional[List]:
    values, position = [], 0
    try:
        for kind in types:
            if kind == "str":
                length = struct.unpack_from(e + "H", params, position)[0]
                position += 2
                chunk = params[position:position + length]
                if len(chunk) != length:
                    return None
                values.append(chunk.decode("utf-16-le" if e == "<" else "utf-16-be"))
                position += length
            else:
                fmt = _INT_FORMATS[kind]
                values.append(struct.unpack_from(e + fmt, params, position)[0])
                position += struct.calcsize(fmt)
    except (struct.error, UnicodeDecodeError):
        return None
    rest = params[position:]
    if rest and not (len(rest) == 1 and rest[0] == _PAD):
        return None
    return values


def _encode_args(types: Tuple[str, ...], values: List, e: str) -> bytes:
    out = bytearray()
    for kind, value in zip(types, values):
        if kind == "str":
            data = value.encode("utf-16-le" if e == "<" else "utf-16-be")
            out += struct.pack(e + "H", len(data)) + data
        else:
            out += struct.pack(e + _INT_FORMATS[kind], value)
    if len(out) % 2:
        out.append(_PAD)
    return bytes(out)


def _readable(tag: Tag, e: str) -> Optional[str]:
    known = TAGS.get((tag.group, tag.type))
    if known is None:
        return None
    name, types, _description = known
    values = _decode_args(types, tag.params, e)
    if values is None:
        return None
    shown = []
    for index, value in enumerate(values):
        names = VALUE_NAMES.get((name, index))
        shown.append(names.get(value, str(value)) if names and isinstance(value, int) else str(value))
    text = "{" + ":".join([name, *shown]) + "}"
    try:
        if parse_tag(text, e) != tag:
            return None
    except ValueError:
        return None
    return text


def render_tag(token, little: bool = True) -> str:
    """The editor form of one ``Tag`` / ``EndTag``."""
    e = "<" if little else ">"
    if isinstance(token, EndTag):
        known = TAGS.get((token.group, token.type))
        return f"{{/{known[0]}}}" if known else f"{{/tag:{token.group}:{token.type}}}"
    readable = _readable(token, e)
    if readable:
        return readable
    raw = f"{{tag:{token.group}:{token.type}"
    return raw + (f":{token.params.hex()}}}" if token.params else "}")


def parse_tag(text: str, e: str = "<"):
    """The ``Tag`` / ``EndTag`` an editor tag stands for. ``ValueError`` when it is not one."""
    match = _TAG_PARTS_RE.fullmatch(text)
    if not match:
        raise ValueError(f"Not a tag: {text}")
    closing, name, rest = match.group(1), match.group(2), match.group(3)
    args = rest.split(":")[1:] if rest else []
    try:
        if name == "tag":
            group, kind = int(args[0]), int(args[1])
            if closing:
                return EndTag(group, kind)
            return Tag(group, kind, bytes.fromhex(args[2]) if len(args) > 2 else b"")
    except (IndexError, ValueError) as error:
        raise ValueError(f"Bad raw tag {text}: {error}") from error
    key = _BY_NAME.get(name)
    if key is None:
        raise ValueError(f"Unknown tag {text}")
    if closing:
        return EndTag(*key)
    types = TAGS[key][1]
    if len(args) != len(types):
        raise ValueError(f"{text}: {name} takes {len(types)} argument(s)")
    values = []
    for index, (kind, arg) in enumerate(zip(types, args)):
        if kind == "str":
            values.append(arg)
            continue
        names = {label: value for value, label in VALUE_NAMES.get((name, index), {}).items()}
        try:
            values.append(names[arg] if arg in names else int(arg))
        except ValueError as error:
            raise ValueError(f"{text}: argument {index + 1} must be a number") from error
    try:
        return Tag(key[0], key[1], _encode_args(types, values, e))
    except struct.error as error:
        raise ValueError(f"{text}: {error}") from error


def to_editor(tokens: List[Token], little: bool = True) -> str:
    """A message as editor text."""
    return "".join(token if isinstance(token, str) else render_tag(token, little) for token in tokens)


def from_editor(text: str, little: bool = True) -> List[Token]:
    """Editor text back to tokens. ``{...}`` that is not a tag stays text."""
    e = "<" if little else ">"
    tokens: List[Token] = []
    position = 0
    for match in TAG_RE.finditer(text):
        try:
            tag = parse_tag(match.group(0), e)
        except ValueError:
            continue
        if match.start() > position:
            tokens.append(text[position:match.start()])
        tokens.append(tag)
        position = match.end()
    if position < len(text):
        tokens.append(text[position:])
    return tokens


def describe(text: str) -> str:
    """Tooltip for an editor tag."""
    match = _TAG_PARTS_RE.fullmatch(text or "")
    if not match:
        return ""
    if match.group(2) == "tag":
        return "Raw MSBT control tag (group:type:parameter bytes)"
    key = _BY_NAME.get(match.group(2))
    return f"{TAGS[key][2]} (MSBT tag {key[0]}:{key[1]})" if key else ""
