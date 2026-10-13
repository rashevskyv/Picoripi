"""Checks of Wind Waker HD (MSBT) editor texts: tags that do not parse, unknown tags, unmatched closing tags,
[Size] values outside the game's range, colours the palette does not have, and icon characters the game never uses.

The limits come from the game files (the 68 HD message files): [Size] values 50..300 (304 uses), colour indices 0..8
and the default 0xFFFF, five icon characters (U+E000, U+E081, U+E082, U+E0A0, U+E0A1), and no closing tags. A check
returns issues; it never changes a text. The GameCube plugin applies it to MSBT blocks only (see zelda_tww).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from plugins.common.msbt import EndTag

from .tags import COLOR_DEFAULT, COLORS, TAGS, from_editor, parse_tag

SIZE_GROUP, SIZE_TYPE = 0, 2
COLOUR_GROUP, COLOUR_TYPE = 0, 3
SIZE_MIN, SIZE_MAX = 50, 300
ICON_CHARS = frozenset("\ue000\ue081\ue082\ue0a0\ue0a1")
_UNPARSED = re.compile(r"\[/?[A-Za-z][^\[\]\n]*\]")


@dataclass(frozen=True)
class Issue:
    """kind: "unparsed", "unknown", "closing", "size", "colour", "icon". text: the offending editor text."""

    kind: str
    text: str
    detail: str


def check_text(text: str) -> List[Issue]:
    """Every issue of one editor text, in text order."""
    issues: List[Issue] = []
    for match in _UNPARSED.finditer(text):
        try:
            parse_tag(match.group(0))
        except ValueError:
            issues.append(Issue("unparsed", match.group(0), "not a tag this game uses"))
    open_tags = set()
    for token in from_editor(text):
        if isinstance(token, str):
            for char in token:
                if 0xE000 <= ord(char) <= 0xF8FF and char not in ICON_CHARS:
                    issues.append(Issue("icon", char, "icon character the game does not use"))
            continue
        if isinstance(token, EndTag):
            key = (token.group, token.type)
            if key not in open_tags:
                issues.append(Issue("closing", f"[/Tag:{token.group}:{token.type}]", "closes a tag that is not open"))
            open_tags.discard(key)
            continue
        key = (token.group, token.type)
        open_tags.add(key)
        if key == (COLOUR_GROUP, COLOUR_TYPE):
            index = int.from_bytes(token.params, "big") if len(token.params) == 2 else -1
            if index not in (*COLORS, COLOR_DEFAULT):
                issues.append(Issue("colour", f"[Color:{index}]", "colour not in the game's palette"))
            continue
        if key == (SIZE_GROUP, SIZE_TYPE):
            value = int.from_bytes(token.params, "big") if len(token.params) == 2 else -1
            if not SIZE_MIN <= value <= SIZE_MAX:
                issues.append(Issue("size", f"[Size:{value}]", f"size outside {SIZE_MIN}..{SIZE_MAX}"))
            continue
        if token.group == 4 or key in TAGS:      # SE:<any id> is in the game's catalogue as a group
            continue
        issues.append(Issue("unknown", f"[Tag:{token.group}:{token.type}]", "tag the game's catalogue does not name"))
    return issues
