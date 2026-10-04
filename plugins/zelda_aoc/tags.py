"""Age of Calamity text markup: the game's own ``[tags]``, shown as they are, plus one readable form.

The text is UTF-8 with square-bracket tags (counts from the English text of update 1.3.0):

  ``[cdb]``             before a line that continues the sentence (follows ``\\n`` in 4276 of 4278 uses)
  ``%s`` + ``[s0]``..   a value the game inserts; ``[sN]`` says which one
  ``[v]`` ``[t]`` ``[r]`` ``[b]`` ... ``[/]``   coloured text (names, values, red, blue) until ``[/]``
  ``[eg1]``..``[eg3]``  ``[cp]`` ``[eb]`` ``[ec2]``   grammar of the inserted name (article, plural, capital)
  ``[cs]`` ``[cm]`` ``[ce]``   the forms of a name: ``[cs]form 1[cm]form 2[ce]``
  ``[es]1_5_1______``   the grammar code of one form; shown as ``[es:1_5_1]``
  ``[$0003]``           a controller button icon
  ``^06``..``^07~ruby~`` Japanese furigana (Japanese only)

``%%`` is a literal percent sign, ``%d`` a number.
"""

from __future__ import annotations

import re

TAG_RE = re.compile(r"\[[^\[\]\n]*\]")
PLACEHOLDER_RE = re.compile(r"%(?:%|[0-9]*[sd])")
_ES_GAME = re.compile(r"\[es\]([0-9]+_[0-9]+_[0-9]+)______")
_ES_EDITOR = re.compile(r"\[es:([0-9]+_[0-9]+_[0-9]+)\]")
KNOWN_TAG_RE = re.compile(r"\[(?:cdb|/|v|t|r|b|cp|eb|cs|cm|ce|s[0-9]+|eg[0-9]+|ec[0-9]+|es|es:[0-9]+_[0-9]+_[0-9]+"
                          r"|\$[0-9A-Fa-f]{4})\]")

DESCRIPTIONS = {
    "cdb": "Before a line that continues the sentence of the line above",
    "/": "End of the coloured text",
    "v": "Colour of names and inserted values until [/]",
    "t": "Colour of numbers and targets until [/]",
    "r": "Red text until [/]",
    "b": "Blue text until [/]",
    "cp": "Inserted name in the plural / with a capital (grammar of the name)",
    "eb": "Grammar of the inserted name (sentence start)",
    "cs": "Start of the forms of a name",
    "cm": "Next form of the name",
    "ce": "End of the forms of a name",
    "es": "Grammar code of this form of the name",
    "s": "Which inserted value the %s before it shows",
    "eg": "Grammar of the inserted name (article)",
    "ec": "Grammar of the inserted name",
    "$": "Controller button icon",
}


def to_editor(text: str) -> str:
    """Game text -> editor text: only the ``[es]`` grammar code changes form."""
    return _ES_GAME.sub(r"[es:\1]", text)


def from_editor(text: str) -> str:
    return _ES_EDITOR.sub(r"[es]\1______", text)


def describe(tag: str) -> str:
    m = re.fullmatch(r"\[(\$|/|[a-z]+)[^\]]*\]", tag or "")
    return DESCRIPTIONS.get(m.group(1), "") if m else ""
