"""Yo-kai Watch text markup <-> editor text.

The game writes its control codes in angle brackets and a line break as the two characters ``\\n``.
The editor shows a real line break and the codes in curly brackets (the engine's tag syntax), unchanged
inside: ``<PNAME01>`` -> ``{PNAME01}``. No English string has a ``{`` or ``}`` of its own. Inline pictures
are already ``[g_coin]``-style and stay as they are.

  ``{PAGE}``            next page of the message window (2 lines per page)
  ``{CR}`` ``{CG}`` ``{CN}`` ``{CY}`` ``{C14}`` ``{C"48943C"}`` ... ``{/C}``   text colour until ``{/C}``
  ``{PNAME01}`` ``{PNAME}``  the player's name; ``{CHARA_NAME}``, ``{ITEM_NAME}``, ``{VAL#...}``... values
  ``{SEL2/1/3}``        the answer choice that follows the line
  ``{A01/02}`` ``{O34}`` ``{ML#...}``  the speaker's animation / window options (zero width)
"""
from __future__ import annotations

import re

TAG_RE = re.compile(r"\{[^{}\n]+\}|\[[a-z_0-9]+\]")
GAME_TAG_RE = re.compile(r"<([^<>\n]+)>")
NEWLINE = "\\n"

_DESCRIPTIONS = [
    (r"PAGE", "Next page of the message window"),
    (r"/C|/CR", "Back to the normal text colour"),
    (r"C[RGNYB]", "Text colour: R red (warnings, keywords), G green (items, places), N name colour, Y yellow, "
                  "until {/C}"),
    (r"C\d+|C\".*\"", "Text colour by number or RGB value, until {/C}"),
    (r"PNAME[MF]?\d*\??", "The player's name (Nate / Katie / Hailey, or what the player typed)"),
    (r"SEL.*", "Answer choice shown after this line (choice list id / default / cancel)"),
    (r"A\d+/\d+", "Speaker animation (zero width)"),
    (r"O\d+", "Message window option (zero width)"),
    (r"ML#.*", "Speaker motion (zero width)"),
    (r"J\".*\"", "Sound / jingle cue (zero width)"),
    (r"PV#.*|V#.*", "Voice clip of the speaker (zero width; the model name tells who speaks)"),
    (r"X[\d.]+f?", "Horizontal position of the following text"),
    (r"VAL#.*|VALUE\d*|NUM\d*|STR\d*|QVAL#.*|QPARAM#.*", "A number or word the game fills in"),
]


def to_editor(text: str) -> str:
    """Game string -> editor text."""
    return GAME_TAG_RE.sub(r"{\1}", str(text)).replace(NEWLINE, "\n")


def from_editor(text: str) -> str:
    """Editor text -> game string (``{x}`` back to ``<x>``, line breaks back to ``\\n``)."""
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\{([^{}\n]+)\}", r"<\1>", text).replace("\n", NEWLINE)


def describe(tag: str) -> str:
    """A tooltip for a tag, or "" for text that is not one."""
    if not TAG_RE.fullmatch(str(tag)):
        return ""
    if tag.startswith("["):
        return f"Inline picture '{tag[1:-1]}'"
    body = tag[1:-1]
    for pattern, text in _DESCRIPTIONS:
        if re.fullmatch(pattern, body):
            return text
    return "A name or value the game fills in" if body.replace("_", "").isalnum() else "Game control code"
