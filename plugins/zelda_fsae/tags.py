"""Four Swords Anniversary Edition control codes <-> readable editor tags.

``7F 00 01 00`` (line break) is a real line break in the editor; the end code is left out (saving adds it).
Every other code is a ``[...]`` tag with its numbers (meanings read from how the English text uses them):

  ``[wait:N]``    pause N frames inside the box          ``[next:N]``  after N frames the box moves on
  ``[close]``     close the box (end of a cutscene line)  ``[event:N]`` hand over to the scene (Great Fairies)
  ``[choice]``    a menu choice (the cursor stands here)  ``[center]``  centre this line
  ``[speaker:N]`` who speaks a cutscene line (1 Zelda, 2 the voice of the prologue, 3 Vaati)
  ``[icon:N]``    an item picture                         ``[button:N]`` a button picture
  ``[num:N]``     number N of the message (Rupees, time)  ``[player:N]`` player N's name
  ``[space:N]``   N pixels of space                       ``[color:N]`` text colour N (0 = normal)
  ``[code13:A,B,C]`` a code met once (Spanish)
"""
from __future__ import annotations

import re
from typing import List

from . import kmsg

NAMES = {2: "wait", 3: "next", 4: "close", 5: "event", 6: "choice", 7: "speaker", 8: "icon", 9: "num",
         10: "button", 11: "space", 12: "player", 13: "code13", 14: "center", 17: "color"}
CODES = {name: code for code, name in NAMES.items()}
TAG_RE = re.compile(r"\[(?:(?:wait|next|event|speaker|icon|num|button|space|player|color):\d+"
                    r"|close|choice|center|code13:\d+,\d+,\d+)\]")
SPEAKERS = {1: "Princess Zelda", 2: "npc:voice", 3: "Vaati"}
COLOURS = {0: "normal", 1: "highlight (places, keys, controls)", 3: "objects and places", 4: "credits heading",
           7: "credits name"}


def to_editor(raw: bytes) -> str:
    out: List[str] = []
    for part in kmsg.tokens(raw):
        if isinstance(part, str):
            out.append(part)
        elif part[0] == 1:
            out.append("\n")
        elif part[0]:
            name = NAMES[part[0]]
            out.append(f"[{name}:{','.join(map(str, part[1:]))}]" if len(part) > 1 else f"[{name}]")
    return "".join(out)


def from_editor(text: str) -> bytes:
    parts: list = []
    at = 0
    text = str(text).replace("\r\n", "\n")
    for match in TAG_RE.finditer(text):
        parts += _text(text[at:match.start()])
        name, _, numbers = match.group()[1:-1].partition(":")
        parts.append((CODES[name], *(int(n) & 0xFFFF for n in numbers.split(",") if n)))
        at = match.end()
    parts += _text(text[at:])
    return kmsg.encode(parts + [(0,)])


def _text(chunk: str) -> list:
    out: list = []
    for index, line in enumerate(chunk.split("\n")):
        if index:
            out.append((1,))
        if line:
            out.append(line)
    return out


def describe(tag: str) -> str:
    """A tooltip for a tag, or "" for text that is not one."""
    if not TAG_RE.fullmatch(tag):
        return ""
    name, _, numbers = tag[1:-1].partition(":")
    value = int(numbers.split(",")[0]) if numbers else 0
    if name == "speaker":
        who = SPEAKERS.get(value, "unknown").replace("npc:voice", "the voice of the prologue")
        return f"Speaker of the cutscene line: {who}"
    if name == "color":
        return f"Text colour {value}: {COLOURS.get(value, 'unknown')}"
    return {"wait": f"Pause {value} frames", "next": f"After {value} frames the box moves on",
            "close": "Close the box", "event": f"Hand over to the scene ({value})", "choice": "Menu choice",
            "center": "Centre this line", "icon": f"Item picture {value}", "button": f"Button picture {value}",
            "num": f"Number {value} of the message (Rupees, time, player)", "player": f"Name of player {value + 1}",
            "space": f"{value} pixels of space", "code13": "Control code 13 (meaning unknown)"}[name]
