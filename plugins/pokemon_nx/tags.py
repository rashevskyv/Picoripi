"""Pokémon (Switch) text markup as the editor shows it (``gfmsg``): game commands and special characters.

``[VAR XXXX]`` / ``[VAR XXXX(AAAA,BBBB)]`` is a game command with its arguments (hex, as pkNX prints
them); ``[XXXX]`` is one character that is not plain text (a button icon, a literal bracket). Counts from
the English text of Sword/Shield 1.3.2 and Legends: Arceus 1.1.1:

  ``[VAR BE01]``    next text box (the text so far is cleared); ``[VAR BE00]`` scrolls one line up
  ``[VAR BE02(n)]`` waits n frames; ``[VAR BDFF(n)]`` stands for an empty line
  ``[VAR FF00(n)]`` text colour n until ``[VAR FF00(0000)]``
  ``[VAR 01xx(n)]`` a name the game inserts (player, Pokémon, move, item... from buffer n)
  ``[VAR 02xx(n)]`` a number the game inserts
  ``[VAR 1100(...)]`` / ``[VAR 1101(...)]`` a word form chosen by the gender / count of an inserted value
  ``[E300]``..      a button or symbol icon of the font
"""
from __future__ import annotations

import re

KNOWN_TAG_RE = re.compile(r"\[VAR [0-9A-F]{4}(?:\([0-9A-F]{4}(?:,[0-9A-F]{4})*\))?\]|\[[0-9A-F]{4}\]")

_DESCRIPTIONS = (
    (r"\[VAR BE01\]", "Next text box: the text so far is cleared"),
    (r"\[VAR BE00\]", "Scroll: the text moves up one line"),
    (r"\[VAR BE02\(.*", "Wait (frames)"),
    (r"\[VAR BE05\(.*", "Text speed / timing"),
    (r"\[VAR BDFF\(.*", "Empty line"),
    (r"\[VAR FF00\(0000\)\]", "End of the coloured text"),
    (r"\[VAR FF00\(.*", "Coloured text until [VAR FF00(0000)]"),
    (r"\[VAR 11..\(.*", "Word form chosen by the gender or count of an inserted value"),
    (r"\[VAR 01..\(.*", "A name the game inserts (player, Pokémon, move, item...)"),
    (r"\[VAR 02..\(.*", "A number the game inserts"),
    (r"\[E[0-9A-F]{3}\]", "Button or symbol icon of the font"),
    (r"\[005B\]", "Literal ["),
    (r"\[005D\]", "Literal ]"),
)


def describe(tag: str) -> str:
    return next((text for pattern, text in _DESCRIPTIONS if re.fullmatch(pattern, tag or "")),
                "Game command" if (tag or "").startswith("[VAR ") else "")
