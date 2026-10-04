"""Wind Waker HD MSBT control tags: the catalogue and the readable ``[tags]`` the editor shows.

Catalogue source: the game's own project file ``CKing.msbp`` (``permanent_2d_UsEnglish.pack``): tag groups
System, ControlTags, ReplaceTags, PictureFontTags, SoundTags, Camera and Action, with their parameter types.
The System tags use the standard LMS layout (the MSBP lists Color as r/g/b/a/name, but the messages store
a 16-bit index into the CLR1 palette).

Editor form (square brackets, as the plugin's Kruptar-era projects):
  ``[Red]`` ... ``[/C]``        a colour by palette index; ``[/C]`` is index 0xFFFF (back to the box colour)
  ``[Name]``                    the player's name (ReplaceTags.PlayerName)
  ``[Wait:10]`` ``[A]`` ...     a known tag by its MSBP name, with its arguments
  ``[SE:259]`` ``[Camera:Long]`` ``[Action:Laugh]``   sound, camera and animation tags
  ``[Tag:G:T]`` / ``[Tag:G:T:hex]``   any other tag, raw; ``[/Tag:G:T]`` a closing tag
A tag is shown by name only when its readable form encodes back to the same bytes, so a file always
round-trips. Arguments with an odd byte length are padded with 0xCD, as the game's files are.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Tuple

from plugins.zelda_totk.msbt import EndTag, Tag, Token

_PAD = 0xCD
COLOR_GROUP, COLOR_TYPE = 0, 3
COLOR_DEFAULT = 0xFFFF

# CLR1 of CKing.msbp; index 0 is drawn in the box's own text colour (white in a talk box).
COLORS = {0: "White", 1: "Red", 2: "Green", 3: "Blue", 4: "Yellow", 5: "Cyan", 6: "Purple", 7: "Silver",
          8: "Orange"}
COLOR_HEX = {0: "#ffffff", 1: "#ff1e00", 2: "#00ff64", 3: "#00c8ff", 4: "#f0c800", 5: "#00ffff",
             6: "#ff32ff", 7: "#808080", 8: "#ff8000"}
_COLOR_BY_NAME = {name: index for index, name in COLORS.items()}

_PICTURES = ("A B C L R X Y Z LS L-Arrow R-Arrow U-Arrow D-Arrow LS-Up LS-Down LS-Left LS-Right LS-UpDown "
             "LS-LeftRight A-Burst TargetIcon HeartIcon MusicalNote Plus Minus ZL ZR RS RS-Up RS-Down RS-Left "
             "RS-Right RS-UpDown RS-LeftRight Juuji JuujiUp JuujiDown JuujiLeft juujiRight PageTri sail1 "
             "sail2").split()
_CONTROL = ("InstanceDispStart InstanceDispEnd Return Close End Step Wait 2Choices 3Choices 2ChoicesSideL "
            "2ChoicesSideR Capital CreditPositon 2ChoicesSideLB 2ChoicesSideRB").split()
_REPLACE = ("PlayerName SeaBattleGameHighScoreShots VaseCompensationRupees AuctionGameName AuctionGameItemName "
            "AuctionGameBetRupees AuctionGameFirstBetRupees AuctionGameBidEntryRupees SwordGameBlows Password "
            "SortedLetters SortingPaymentRupees LettersArrived RemainingKoroks ForestWaterTimer "
            "BirdmanContestDistance BirdmanHighScore BeedleShopPoints CurrentJoyPendants JoyPendantsGiven "
            "TownPigGameTimer CoinGameTotalRupees Bombs Arrows BestSortingRecord MermanDirectHits "
            "MermanGamePrizeRupees BokobabaSeeds SkullNecklaces ChuJellies JoyPendants GoldenFeathers "
            "KnightsCrests BeedleTotalRupees BokobabaSeedEntry SkullNecklaceEntry ChuJellyEntry JoyPendantEntry "
            "GoldenFeatherEntry KnightsCrestEntry SetValue0 SetValue1 SetValue2 SetValue3 SetValue4").split()
_CAMERA = ("BasicConversationCamera Character1 Character2 Character3 Character4 Character5 Character6 "
           "Character7 Character8 Character9 Character10 LinkShot Long FirstPerson FirstPerson-Link "
           "FirstPerson-Speaker LinkZoom SpeakerZoom LinkSide SpeakerSide LinkFront SpeakerFront LinkBust "
           "SpeakerBust LinkAngleFront SpeakerAngleFront LinkAngleDown SpeakerAngleDown Side HugeFaceZoom "
           "SpeakertoLink2 LinktoSpeaker2").split()
_ACTION = "Laugh Anger Cry Surprise Troubled - Sniffle SisterNotices SisterSmirks SisterUneasy1".split()

_FRAMES = ("s16",)
_SET_VALUE = ("u8", "u8", "u8")
_SET_VALUE_NAMES = {1: {0: "No", 1: "Yes"}, 2: {0: "FullSize", 1: "HalfSize"}}

# (group, type) -> (editor name, argument types, description)
TAGS: Dict[Tuple[int, int], Tuple[str, Tuple[str, ...], str]] = {
    (0, 0): ("Ruby", ("u16", "str"), "Ruby text drawn above the next N bytes of text"),
    (0, 1): ("Font", ("str",), "Font face"),
    (0, 2): ("Size", ("u16",), "Text size in percent"),
    (0, 4): ("PageBreak", (), "Starts a new text box page"),
}
_DESCRIPTIONS = {
    "InstanceDispStart": "Show the following text at once (no typing)",
    "InstanceDispEnd": "Resume typing the text",
    "Return": "Close the box after a frame count",
    "Close": "Close the box by itself after a frame count",
    "End": "End the message after a frame count",
    "Step": "Typing speed step",
    "Wait": "Pause typing for a frame count",
    "2Choices": "Two choices: the last two lines are the options",
    "3Choices": "Three choices: the last three lines are the options",
    "Capital": "Upper-case the first letter of the next inserted word",
    "PlayerName": "The player's name (Link)",
}
for _index, _name in enumerate(_CONTROL):
    TAGS[(1, _index)] = (_name, _FRAMES if _name in ("Return", "Close", "End", "Step", "Wait") else (),
                         _DESCRIPTIONS.get(_name, "Message control"))
for _index, _name in enumerate(_REPLACE):
    TAGS[(2, _index)] = ("Name" if _name == "PlayerName" else _name,
                         _SET_VALUE if _name.startswith("SetValue") else (),
                         _DESCRIPTIONS.get(_name, "Inserted value: " + _name))
for _index, _name in enumerate(_PICTURES):
    TAGS[(3, _index)] = (_name, (), "Button or symbol icon")
for _index, _name in enumerate(_CAMERA):
    TAGS[(5, _index)] = ("Camera:" + _name, (), "Conversation camera")
for _index, _name in enumerate(_ACTION):
    TAGS[(6, _index)] = ("Action:" + _name, (), "Speaker animation")
_BY_NAME = {name: key for key, (name, _types, _description) in TAGS.items()}

TAG_RE = re.compile(r"\[/?[^\[\]\s]+\]")
_INT_FORMATS = {"u8": "B", "u16": "H", "s16": "h"}


def _decode_args(types: Tuple[str, ...], params: bytes) -> Optional[List]:
    values, position = [], 0
    try:
        for kind in types:
            if kind == "str":
                length = struct.unpack_from(">H", params, position)[0]
                chunk = params[position + 2:position + 2 + length]
                if len(chunk) != length:
                    return None
                values.append(chunk.decode("utf-16-be"))
                position += 2 + length
            else:
                fmt = ">" + _INT_FORMATS[kind]
                values.append(struct.unpack_from(fmt, params, position)[0])
                position += struct.calcsize(fmt)
    except (struct.error, UnicodeDecodeError):
        return None
    rest = params[position:]
    if rest and not (len(rest) == 1 and rest[0] == _PAD):
        return None
    return values


def _encode_args(types: Tuple[str, ...], values: List) -> bytes:
    out = bytearray()
    for kind, value in zip(types, values):
        if kind == "str":
            data = value.encode("utf-16-be")
            out += struct.pack(">H", len(data)) + data
        else:
            out += struct.pack(">" + _INT_FORMATS[kind], value)
    if len(out) % 2:
        out.append(_PAD)
    return bytes(out)


def _readable(tag: Tag) -> Optional[str]:
    if (tag.group, tag.type) == (COLOR_GROUP, COLOR_TYPE) and len(tag.params) == 2:
        index = struct.unpack(">H", tag.params)[0]
        text = "[/C]" if index == COLOR_DEFAULT else f"[{COLORS[index]}]" if index in COLORS else f"[Color:{index}]"
    else:
        known = TAGS.get((tag.group, tag.type))
        if known is None:
            if tag.group == 4 and not tag.params:
                return f"[SE:{tag.type}]"
            return None
        name, types, _description = known
        values = _decode_args(types, tag.params)
        if values is None:
            return None
        shown = [str(_SET_VALUE_NAMES.get(index, {}).get(value, value)) if name.startswith("SetValue") else str(value)
                 for index, value in enumerate(values)]
        text = "[" + ":".join([name, *shown]) + "]"
    try:
        return text if parse_tag(text) == tag else None
    except ValueError:
        return None


def render_tag(token) -> str:
    """The editor form of one ``Tag`` / ``EndTag``."""
    if isinstance(token, EndTag):
        return f"[/Tag:{token.group}:{token.type}]"
    readable = _readable(token)
    if readable:
        return readable
    return f"[Tag:{token.group}:{token.type}" + (f":{token.params.hex()}]" if token.params else "]")


def parse_tag(text: str):
    """The ``Tag`` / ``EndTag`` an editor tag stands for. ``ValueError`` when it is not one."""
    if not (text.startswith("[") and text.endswith("]")) or len(text) < 3:
        raise ValueError(f"Not a tag: {text}")
    body = text[1:-1]
    if body == "/C":
        return Tag(COLOR_GROUP, COLOR_TYPE, struct.pack(">H", COLOR_DEFAULT))
    if body in _COLOR_BY_NAME:
        return Tag(COLOR_GROUP, COLOR_TYPE, struct.pack(">H", _COLOR_BY_NAME[body]))
    closing = body.startswith("/")
    parts = body[1:].split(":") if closing else body.split(":")
    try:
        if parts[0] == "Tag":
            group, kind = int(parts[1]), int(parts[2])
            if closing:
                return EndTag(group, kind)
            return Tag(group, kind, bytes.fromhex(parts[3]) if len(parts) > 3 else b"")
        if closing:
            raise ValueError(f"Unknown closing tag {text}")
        if parts[0] == "Color" and len(parts) == 2:
            return Tag(COLOR_GROUP, COLOR_TYPE, struct.pack(">H", int(parts[1])))
        if parts[0] == "SE" and len(parts) == 2:
            return Tag(4, int(parts[1]), b"")
    except (IndexError, ValueError, struct.error) as error:
        raise ValueError(f"Bad tag {text}: {error}") from error
    for split in (2, 1):          # "Camera:Long" and "Action:Laugh" carry their group in the name
        name, args = ":".join(parts[:split]), parts[split:]
        key = _BY_NAME.get(name)
        if key is not None:
            break
    else:
        raise ValueError(f"Unknown tag {text}")
    types = TAGS[key][1]
    if len(args) != len(types):
        raise ValueError(f"{text}: {name} takes {len(types)} argument(s)")
    values = []
    for index, (kind, arg) in enumerate(zip(types, args)):
        if kind == "str":
            values.append(arg)
            continue
        names = {label: value for value, label in _SET_VALUE_NAMES.get(index, {}).items()} \
            if name.startswith("SetValue") else {}
        try:
            values.append(names[arg] if arg in names else int(arg))
        except ValueError as error:
            raise ValueError(f"{text}: argument {index + 1} must be a number") from error
    try:
        return Tag(key[0], key[1], _encode_args(types, values))
    except struct.error as error:
        raise ValueError(f"{text}: {error}") from error


def to_editor(tokens: List[Token]) -> str:
    """A message as editor text."""
    return "".join(token if isinstance(token, str) else render_tag(token) for token in tokens)


def from_editor(text: str) -> List[Token]:
    """Editor text back to tokens. ``[...]`` that is not a tag stays text."""
    tokens: List[Token] = []
    position = 0
    for match in TAG_RE.finditer(text):
        try:
            tag = parse_tag(match.group(0))
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
    try:
        tag = parse_tag(text or "")
    except ValueError:
        return ""
    if isinstance(tag, EndTag):
        return "Raw MSBT closing tag (group:type)"
    if (tag.group, tag.type) == (COLOR_GROUP, COLOR_TYPE):
        index = struct.unpack(">H", tag.params)[0]
        return "Back to the box's text colour" if index == COLOR_DEFAULT else f"Text colour {index} (CLR1 palette)"
    if tag.group == 4:
        return f"Sound effect {tag.type}"
    known = TAGS.get((tag.group, tag.type))
    if text.startswith("[Tag:") or known is None:
        return "Raw MSBT control tag (group:type:parameter bytes)"
    return f"{known[2]} (MSBT tag {tag.group}:{tag.type})"
