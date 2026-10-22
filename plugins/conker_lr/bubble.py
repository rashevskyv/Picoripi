"""Conker: Live & Reloaded dialogue size limits, from the game code (see docs/conker-text-limits-picoripi.md in the recomp repo).

A text is split on ``{PARAGRAPH}``: each paragraph is one speech bubble. The bubble wraps at 20 characters per
line, breaking at a space or ``{PMARKER}``; a word longer than the width stays whole. The bubble is at most 4 lines
tall; a longer paragraph scrolls. A ``{...}`` tag is one code (one unit), as in the game.
A displayed string holds up to 2047 units; a whole cutscene line (all its paragraphs) should stay under 511.
"""
from __future__ import annotations

import re
from typing import List

PARAGRAPH_TAG = "{PARAGRAPH}"
BREAK_TAG = "{PMARKER}"
WRAP_CHARS = 20
BUBBLE_LINES = 4
DISPLAY_STRING_LIMIT = 2047
CUTSCENE_LINE_LIMIT = 511

_TOKEN = re.compile(r"\{[^{}]*\}|.", re.DOTALL)


def _tokens(text: str) -> List[str]:
    """The units of a text: each ``{...}`` tag is one token, every other character is one token."""
    return _TOKEN.findall(text)


def paragraphs(text: str) -> List[str]:
    """The paragraphs of a line: the parts between ``{PARAGRAPH}`` tags (each one is its own bubble)."""
    return text.split(PARAGRAPH_TAG)


def units(text: str) -> int:
    """The length of a text in game units (a tag counts as one)."""
    return len(_tokens(text))


def bubble_lines(paragraph: str, width: int = WRAP_CHARS) -> int:
    """How many lines the game's word wrap gives one paragraph."""
    tokens = _tokens(paragraph)
    lines = 1
    start = 0
    for index in range(len(tokens)):
        if tokens[index] == " ":
            continue
        while index - start >= width:
            breaks = [k for k in range(start, index) if tokens[k] == " " or tokens[k] == BREAK_TAG]
            if not breaks:
                break  # a word longer than the width stays on one line
            start = breaks[-1] + 1
            lines += 1
    return lines


def problems(text: str) -> List[str]:
    """Problem ids of a line: ``LINE_LIMIT``, ``STRING_LIMIT`` or ``BUBBLE_LINES`` (informational, not blocking)."""
    found = []
    length = units(text)
    if length > DISPLAY_STRING_LIMIT:
        found.append("STRING_LIMIT")
    if length > CUTSCENE_LINE_LIMIT:
        found.append("LINE_LIMIT")
    if any(bubble_lines(part) > BUBBLE_LINES for part in paragraphs(text)):
        found.append("BUBBLE_LINES")
    return found
