"""Series glossary terms that fill a whole string (D45, item 1 of the series round).

A string whose whole normalised text equals a series term takes the term's translation. "Normalised" uses the
plugin's tag kinds (``get_series_tag_map``): a string with a control tag matches a term only when the term has the
same tags in the same order. A plugin without a tag map uses the generic normalisation of the translation memory.
Two entries that translate one term differently make a conflict: nothing is filled for it. A string that already
has a different translation is never overwritten: it is listed as a conflict.

Pure logic: no window, no file. The caller applies the planned fills.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from core.translation.run_memory import normalize_source
from plugins.common.series_tags import neutral_of

# Statuses of a planned fill.
FILL = "fill"                  # the string is untranslated: the term's translation is written
SAME = "same"                  # the string already has exactly the term's translation: nothing to do
CONFLICT = "conflict"          # a different translation exists: kept
GLOSSARY_CONFLICT = "glossary" # two series entries translate the term differently: nothing is written


@dataclass(frozen=True)
class TermTable:
    """What the series glossaries say: ``key -> (term, translation)`` and the keys with two translations."""

    by_key: Dict[str, Tuple[str, str]]
    conflicts: Dict[str, List[Tuple[str, str]]]


@dataclass(frozen=True)
class TermFill:
    """One planned fill: where, what, and what happens. ``translation`` is the text written (or the alternatives)."""

    block_idx: int
    string_idx: int
    source: str
    term: str
    translation: str
    current: str
    status: str


def term_key(text: str, tag_map: Any = None) -> Optional[str]:
    """The key a term and a string share, or None when the text has a tag without a kind (no match)."""
    if tag_map is None:
        key = normalize_source(text)
        return key or None
    neutral = neutral_of(text, tag_map)
    return neutral or None


def build_term_table(entries: Iterable[Tuple[str, str]], tag_map: Any = None) -> TermTable:
    """The table from ``(term, translation)`` pairs of the series glossaries (nearest first; untranslated pairs skipped)."""
    seen: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for term, translation in entries:
        term = (term or "").strip()
        translation = (translation or "").strip()
        if not term or not translation:
            continue
        key = term_key(term, tag_map)
        if key is None:
            continue
        if (term, translation) not in seen[key]:
            seen[key].append((term, translation))
    by_key: Dict[str, Tuple[str, str]] = {}
    conflicts: Dict[str, List[Tuple[str, str]]] = {}
    for key, pairs in seen.items():
        if len({translation for _, translation in pairs}) == 1:
            by_key[key] = pairs[0]
        else:
            conflicts[key] = pairs
    return TermTable(by_key, conflicts)


def plan_fills(table: TermTable, rows: Sequence[Tuple[int, int, str, Optional[str], bool]], tag_map: Any = None) -> List[TermFill]:
    """The fills for ``rows``: ``(block, string, source, current text or None, translated?)``.

    Only the rows whose source matches a term are returned. ``translated`` says whether the string already has a
    translation of its own; an untranslated row takes the term, a translated one keeps its text.
    """
    planned: List[TermFill] = []
    for block_idx, string_idx, source, current, translated in rows:
        key = term_key(source, tag_map)
        if key is None:
            continue
        if key in table.conflicts:
            alternatives = " | ".join(translation for _, translation in table.conflicts[key])
            planned.append(TermFill(block_idx, string_idx, source, table.conflicts[key][0][0], alternatives,
                                    current or "", GLOSSARY_CONFLICT))
            continue
        if key not in table.by_key:
            continue
        term, translation = table.by_key[key]
        if not translated:
            status = FILL
        elif (current or "").strip() == translation:
            status = SAME
        else:
            status = CONFLICT
        planned.append(TermFill(block_idx, string_idx, source, term, translation, current or "", status))
    return planned


def writable(fills: Iterable[TermFill]) -> List[TermFill]:
    """The fills that write something: untranslated strings with exactly one translation."""
    return [fill for fill in fills if fill.status == FILL]
