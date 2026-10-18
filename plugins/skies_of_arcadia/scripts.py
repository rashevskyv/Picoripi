"""Field scripts (``field/*.sct``) as editor strings: one string per text segment, saved back into the decoded body.

A segment is a page's text cut at each label inside it (``core.containers.skies_script.text_segments``). The field
scripts have no label inside a text, so a segment is a page.

Budget (one per script, the same on GameCube and Dreamcast): the script's text bytes may not grow in total. A changed
line takes its encoded length, padded with spaces so the next code word stays aligned: its length moves in steps of 4
bytes. ``budget_of`` computes this; the writer, the editor's problem and the build all use it. A script within its
budget keeps its length (``grow_regions`` net zero). A script over its budget is written with its typed text and a
longer body; the build refuses such a script, so the typed text is never lost and the game never reads it.
"""
from __future__ import annotations

import functools
from typing import List, NamedTuple, Sequence, Set, Tuple

from core.containers import skies_script

from . import text

BIG_ENDIAN = True   # GameCube
PAD = " "           # the editor's space; trailing spaces are padding (the writer adds and removes them)


class Budget(NamedTuple):
    """A script's budget and use, in bytes. ``changed`` has one flag per text segment (its string differs)."""
    budget: int
    used: int
    changed: Tuple[bool, ...]

    @property
    def free(self) -> int:
        return self.budget - self.used   # negative when the script is over its budget


def segments(body: bytes, big: bool = BIG_ENDIAN) -> List[Tuple[int, int]]:
    """(start, end) byte offsets of each text segment, in file order. ``big`` is the script's byte order."""
    return [(start, end) for _page, start, end in skies_script.text_segments(body, big)]


def read_strings(body: bytes, big: bool = BIG_ENDIAN) -> List[str]:
    return [text.decode(body[start:end]) for start, end in segments(body, big)]


def _trimmed(value: str) -> str:
    return value.rstrip(PAD)


@functools.lru_cache(maxsize=8192)
def _encoded_length(value: str) -> int:
    return len(text.encode(value)[0])


def budget_of(source: bytes, strings: Sequence[str], big: bool = BIG_ENDIAN) -> Budget:
    """The budget of the script whose source body is ``source``, and what ``strings`` (one per segment) use.

    A string equal to its source text (trailing spaces aside) is unchanged and uses its source length. A changed string
    uses its encoded length plus the spaces that keep the length in the source's residue mod 4.
    """
    spans = segments(source, big)
    if len(strings) != len(spans):
        raise ValueError(f"expected {len(spans)} strings, got {len(strings)}")
    budget = used = 0
    changed: List[bool] = []
    for (start, end), new_text in zip(spans, strings):
        old = end - start
        budget += old
        if _trimmed(new_text) == _trimmed(text.decode(source[start:end])):
            used += old
            changed.append(False)
            continue
        n = _encoded_length(_trimmed(new_text))
        used += n + (old - n) % 4
        changed.append(True)
    return Budget(budget, used, tuple(changed))


def write_strings(source: bytes, strings: Sequence[str], big: bool = BIG_ENDIAN) -> Tuple[bytes, Set[str]]:
    """The body with the edited strings written in. Returns (new body, missing characters).

    Every string is compared with the source text, so an unchanged string keeps its bytes. The source body is the only
    base: the offsets come from it, never from a previous save. An over-budget script is written too (see the module
    docstring): the build refuses it.
    """
    spans = segments(source, big)
    state = budget_of(source, strings, big)   # also checks the string count
    replacements = {}
    missing: Set[str] = set()
    for (start, end), new_text, is_changed in zip(spans, strings, state.changed):
        if not is_changed:
            continue
        new, lost = text.encode(_trimmed(new_text))
        missing |= lost
        replacements[(start, end)] = new
    if not replacements:
        return source, missing
    out, _delta = skies_script.grow_regions(source, replacements, big, net_zero=state.free >= 0)
    return out, missing
