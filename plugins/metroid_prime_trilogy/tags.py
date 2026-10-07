"""Metroid Prime text tags: the games write formatting as ``&name;`` / ``&name=value;`` inside the strings; the
editor shows them as ``{name}`` / ``{name=value}``. The English text of all three games and the menu has no
``{`` or ``}`` and no ``&`` outside a tag, so the two forms convert both ways without loss.

Common tags: ``push`` / ``pop`` (save / restore the style), ``main-color=#RRGGBB[AA]``, ``just=left|center|right``,
``font=<id>``, ``image=<kind>,<args>,<texture id>``, ``lookup=<name>`` and ``if=`` / ``else`` / ``endif``
(text the game fills in or chooses), ``link=`` / ``endlink`` and ``rollover=`` (menu buttons), ``space``.
"""
from __future__ import annotations

import re

GAME_TAG = re.compile(r"&([a-z][a-z0-9-]*(?:=[^;]*)?);")
EDITOR_TAG = re.compile(r"\{([a-z][a-z0-9-]*(?:=[^{}]*)?)\}")

DESCRIPTIONS = {
    "push": "Saves the current text style", "pop": "Restores the saved text style",
    "main-color": "Text colour (#RRGGBB or #RRGGBBAA)", "just": "Line alignment (left, center, right)",
    "font": "Switches to another font (its resource id)", "image": "Draws an image (button icon) in the text",
    "lookup": "Text the game fills in", "if": "Shows the text up to else / endif only if the condition is true",
    "else": "Otherwise branch of if", "endif": "End of an if", "link": "Start of a menu button",
    "endlink": "End of a menu button", "rollover": "What changes when the button is selected",
    "space": "A space", "line-spacing": "Line spacing", "typewrite": "Typewriter speed",
}


def to_editor(text: str) -> str:
    return GAME_TAG.sub(r"{\1}", text)


def from_editor(text: str) -> str:
    return EDITOR_TAG.sub(r"&\1;", text)


def describe(tag: str) -> str:
    match = EDITOR_TAG.fullmatch(tag.strip())
    if not match:
        return ""
    name = match.group(1).split("=", 1)[0]
    return DESCRIPTIONS.get(name, "Game text tag")
