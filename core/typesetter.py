"""Typesetter: breaks the lines of a page with the game's font and the target language's rules.

One algorithm for AI translations, the width autofix and hand edits. The
model decides the words; this decides where the lines end: fill to the target
width, never leave a short function word (``і``, ``в``, ``на``) at the end of
a line, never leave one word alone on the last line, and go past the target
only up to the limit when those rules need it.
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional, Tuple

from core.tag_utils import ANY_TAG_PATTERN_STR

Measure = Callable[[str], int]

# A word is a run of tags and non-space characters, so "{color}word" stays whole and a tag with a space inside it too.
_WORD = re.compile(rf"(?:{ANY_TAG_PATTERN_STR}|\S)+")
_TAG = re.compile(ANY_TAG_PATTERN_STR)
_PAGE_BREAK = re.compile(r"\n[ \t]*\n")
_STRIP = "\"'«»“”„‘’(),.!?;:…—–-"

# Ukrainian one- and two-letter words that must not end a line (prepositions, conjunctions, particles).
HANGING_WORDS = frozenset(
    "а б в з і й о у ж є та то що як чи бо не ні ну ось от по на за до від під над при про без для із зі зо би".split()
)


def _bare(word: str) -> str:
    return _TAG.sub("", word).strip(_STRIP).casefold()


def _hangs(word: str) -> bool:
    return _bare(word) in HANGING_WORDS


def typeset_page(text: str, measure: Measure, target: int, limit: Optional[int] = None) -> List[str]:
    """The lines of one page: words of ``text`` filled up to ``target`` px, breaks moved by the rules above.

    ``limit`` (default ``target``) is how far a line may go when a rule asks for it. A single word wider than the
    limit stays on a line of its own.
    """
    limit = max(target, limit or target)
    words = _WORD.findall(text or "")
    if not words:
        return []
    lines: List[List[str]] = []
    current: List[str] = []
    for word in words:
        if current and not _bare(word) and not _TAG.fullmatch(word):
            current.append(word)  # punctuation on its own ("—", "...") stays with the word before it
            continue
        if current and measure(" ".join(current + [word])) > target:
            # Break here, but not after a hanging word: it goes down with the next word.
            carried: List[str] = []
            while len(current) > 1 and _hangs(current[-1]):
                carried.insert(0, current.pop())
            lines.append(current)
            current = carried + [word]
        else:
            current.append(word)
    lines.append(current)

    # No single word alone on the last line: pull one down from the line above (which keeps at least two words)
    # when the result stays within the limit.
    while len(lines) >= 2 and len(lines[-1]) == 1 and len(lines[-2]) >= 3:
        moved = lines[-2][-1]
        if not _bare(moved) or measure(" ".join([moved] + lines[-1])) > limit or (len(lines[-2]) > 2 and _hangs(lines[-2][-2])):
            break
        lines[-1].insert(0, lines[-2].pop())
    return [" ".join(line) for line in lines]


def typeset_text(
    text: str, measure: Measure, target: int, limit: Optional[int] = None, lines_per_page: Optional[int] = None
) -> Tuple[str, int]:
    """Every page of ``text`` (pages are separated by a blank line) typeset; the words of a page are reflowed.

    A page that needs more lines than ``lines_per_page`` is cut into more pages. Returns the text and how many
    pages were added that way (0 = everything fitted). A trailing newline is kept.
    """
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    trailing = "\n" if value.endswith("\n") else ""
    pages = _PAGE_BREAK.split(value.rstrip("\n"))
    out: List[str] = []
    added = 0
    for page in pages:
        lines = typeset_page(" ".join(page.split()), measure, target, limit)
        if lines_per_page and lines_per_page > 0 and len(lines) > lines_per_page:
            chunks = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
            added += len(chunks) - 1
            out.extend("\n".join(chunk) for chunk in chunks)
        else:
            out.append("\n".join(lines))
    return "\n\n".join(out) + trailing, added
