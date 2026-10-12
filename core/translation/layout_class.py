"""Layout class of a string: prose (Picoripi breaks the lines) or lines (one source line = one output line).

The plugin says it when it knows the window (``layout_class`` in
``get_translation_context_for_string``); otherwise the source text is read:
a few short lines without sentence punctuation are a list, a menu, a name.
"""
from __future__ import annotations

import re
from typing import Any, Optional

PROSE = "prose"
LINES = "lines"
CLASSES = (PROSE, LINES)

_SENTENCE_END = re.compile(r"[.!?…]['\")»]*\s*$")
_TAG = re.compile(r"\{[^{}]*\}|\[[^\[\]]*\]")
# A line with this many words or fewer may be a list entry rather than a sentence.
LIST_LINE_WORDS = 4


def guess_layout_class(text: Any) -> str:
    """``lines`` for short, unpunctuated lines (menus, names, choices); ``prose`` otherwise."""
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    rows = [_TAG.sub("", row).strip() for row in value.rstrip("\n").split("\n")]
    if not any(rows) or "" in rows:
        return PROSE  # empty, or pages separated by a blank line: dialogue windows, not a list
    if any(_SENTENCE_END.search(row) for row in rows):
        return PROSE
    if all(len(row.split()) <= LIST_LINE_WORDS for row in rows):
        return LINES
    return PROSE


def layout_class_for(mw: Any, block_idx: Optional[int], string_idx: Optional[int], text: Any) -> str:
    """The plugin's answer when it gives one, else a guess from ``text``."""
    rules = getattr(mw, "current_game_rules", None)
    hook = getattr(rules, "get_translation_context_for_string", None)
    if callable(hook) and block_idx is not None and string_idx is not None:
        try:
            context = hook(block_idx, string_idx)
        except Exception:
            context = None
        value = context.get("layout_class") if isinstance(context, dict) else None
        if value in CLASSES:
            return value
    return guess_layout_class(text)
