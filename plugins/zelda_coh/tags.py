"""Cadence of Hyrule text markup <-> editor text.

The game's own tags are already readable and stay as they are (``localization.xml`` documents them):

  ``[n]``        line break -- shown in the editor as a real line break
  ``[p]``        next page of the dialogue box -- shown as ``[p]`` followed by a line break
  ``[c:X]``      text colour X until ``[/c]``: n normal, s selected (item names), r red, b blue (names,
                 places), g green
  ``[i:name]``   inline picture: a button (``button_a``), a character head (``link``, ``cadence``...) or
                 any item of ``necrodancer.xml``; ``[i:name,frame]`` one frame of it
  ``[s:N]``      N spaces of padding (the YES / NO choices)
  ``[z]`` ``[f]`` the current zone and floor number

A raw line break inside a string (one string ends in one) reads ``[cr]`` / ``[lf]`` so that it is
not mistaken for ``[n]``.
"""
from __future__ import annotations

import re

TAG_RE = re.compile(r"\[(?:/c|c:[nsrbg]|n|p|z|f|cr|lf|i:[A-Za-z0-9_]+(?:,\d+)?|s:\d+)\]")

_COLOURS = {"n": "normal (white)", "s": "selected (item names)", "r": "red", "b": "blue (names, places)",
            "g": "green"}


def to_editor(text: str) -> str:
    return (text.replace("\r", "[cr]").replace("\n", "[lf]")
            .replace("[n]", "\n").replace("[p]", "[p]\n"))


def from_editor(text: str) -> str:
    return (str(text).replace("\r\n", "\n").replace("[p]\n", "[p]").replace("\n", "[n]")
            .replace("[lf]", "\n").replace("[cr]", "\r"))


def describe(tag: str) -> str:
    """A tooltip for a tag, or "" for text that is not one."""
    if not TAG_RE.fullmatch(tag):
        return ""
    body = tag[1:-1]
    if body == "/c":
        return "Back to the normal text colour"
    if body.startswith("c:"):
        return f"Text colour: {_COLOURS[body[2:]]} until [/c]"
    if body.startswith("i:"):
        return f"Inline picture '{body[2:]}' (button, character head or item; text_images.xml / necrodancer.xml)"
    if body.startswith("s:"):
        return f"{body[2:]} spaces of padding"
    return {"n": "Line break", "p": "Next page of the dialogue box", "z": "Current zone number",
            "f": "Current floor number", "cr": "Raw carriage return in the file",
            "lf": "Raw line feed in the file"}[body]
