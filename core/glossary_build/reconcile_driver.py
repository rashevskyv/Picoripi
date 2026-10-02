"""Pass 4: bring related glossary entries back in line with each other.

Terms are translated one at a time, so a family can drift: "Clawshot" becomes
"Кігтемет" and "Clawshots" something else; "Postman" and "The Postman" end up as
two entries. This pass clusters entries that are the same term or share a word,
asks once per cluster that looks off, and turns the answer into a list of
changes. Applying them is the coordinator's job; nothing here touches the
glossary, so it is tested with canned replies.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Callable, Dict, Iterable, List, Sequence, Set

from core.glossary_manager import (
    STATUS_CONFIRMED,
    STATUS_TRANSLATED,
    GlossaryManager,
    possible_duplicate_pairs,
    render_notes,
)

from .decisions import families, term_stems

# ponytail: a bigger family is cut into consecutive batches that do not see each
# other; ask in overlapping windows if large families turn out to drift.
MAX_CLUSTER = 30
NOTE_LIMIT = 160

Ask = Callable[[List[Dict[str, str]]], Dict[str, Any]]


@dataclass(frozen=True)
class Change:
    """One change the reconcile pass wants to make."""

    kind: str          # "merge" or "align"
    term: str          # merge: the entry that goes away; align: the entry retranslated
    into: str = ""     # merge: the entry that stays
    old: str = ""      # align: translation before
    new: str = ""      # align: translation after
    reason: str = ""

    def describe(self) -> str:
        if self.kind == "merge":
            return f"merged '{self.term}' into '{self.into}'"
        return f"'{self.term}': {self.old} → {self.new}"


def _translation_stems(translation: str) -> Set[str]:
    """Three letters are what survives Ukrainian inflection: "Зора", "зорів", "зорянський"."""
    return {word[:3] for word in re.findall(r"\w+", (translation or "").casefold()) if len(word) >= 3}


def _worth_asking(members: Sequence[Any], pairs: Set[frozenset]) -> bool:
    """Two linked members are spelled as one term, or share a word and no root in translation."""
    for left, right in combinations(members, 2):
        same_term = (
            GlossaryManager.canonical_key(left.original) == GlossaryManager.canonical_key(right.original)
            or frozenset((left.original, right.original)) in pairs
        )
        if same_term:
            return True
        if term_stems(left.original) & term_stems(right.original) and not (
            _translation_stems(left.translation) & _translation_stems(right.translation)
        ):
            return True
    return False


def clusters(
    entries: Iterable[Any],
    duplicate_pairs: Callable[[List[Any]], Iterable[Sequence[str]]] = possible_duplicate_pairs,
) -> List[List[Any]]:
    """Groups of translated entries worth one reconcile request each, in a fixed order.

    Related means: the same canonical key, a shared distinctive word, or a
    likely-duplicate spelling. A group is skipped when a request could change
    nothing (every member confirmed) or nothing looks off.
    """
    translated = [entry for entry in entries if (entry.translation or "").strip()]
    pairs = {frozenset(pair) for pair in duplicate_pairs(translated)}
    result: List[List[Any]] = []
    for family in families(translated, extra_pairs=pairs):
        if len(family) < 2 or all(entry.status == STATUS_CONFIRMED for entry in family):
            continue
        if not _worth_asking(family, pairs):
            continue
        for start in range(0, len(family), MAX_CLUSTER):
            batch = family[start:start + MAX_CLUSTER]
            if len(batch) > 1:
                result.append(batch)
    return result


def _status_label(entry: Any) -> str:
    if entry.status == STATUS_CONFIRMED:
        return "confirmed"
    return "machine" if entry.status == STATUS_TRANSLATED else "existing"


def cluster_payload(members: Sequence[Any]) -> List[Dict[str, str]]:
    """What the model is shown for one cluster."""
    payload = []
    for entry in members:
        note = render_notes(entry.notes, translation=entry.translation, original=entry.original)
        payload.append({
            "term": entry.original,
            "translation": entry.translation,
            "section": entry.section or "",
            "status": _status_label(entry),
            "note": " ".join(note.split())[:NOTE_LIMIT],
        })
    return payload


def plan_changes(members: Sequence[Any], verdict: Dict[str, Any]) -> List[Change]:
    """The changes a reply asks for, with everything it may not ask for taken out.

    - Only members of this cluster can be merged or retranslated.
    - A confirmed entry is an anchor: it is never retranslated and never merged
      away; two confirmed entries are never merged with each other.
    - In a merge group the confirmed member survives, otherwise the first listed.
    - A translation equal to the current one is not a change, so running the
      pass again on its own result changes nothing.
    """
    if not isinstance(verdict, dict):
        return []
    by_name = {entry.original: entry for entry in members}
    reason = str(verdict.get("reason") or "").strip()
    changes: List[Change] = []
    used: Set[str] = set()
    absorbed: Set[str] = set()

    for group in verdict.get("merge") or []:
        if not isinstance(group, (list, tuple)):
            continue
        names = [name for name in dict.fromkeys(str(item) for item in group) if name in by_name and name not in used]
        confirmed = [name for name in names if by_name[name].status == STATUS_CONFIRMED]
        if len(names) < 2 or len(confirmed) > 1:
            continue
        survivor = confirmed[0] if confirmed else names[0]
        used.update(names)
        for name in names:
            if name != survivor:
                absorbed.add(name)
                changes.append(Change("merge", name, into=survivor, reason=reason))

    translations = verdict.get("canonical_translation_by_term")
    if isinstance(translations, dict):
        for entry in members:
            new = str(translations.get(entry.original) or "").strip()
            if not new or entry.original in absorbed or entry.status == STATUS_CONFIRMED:
                continue
            if new == (entry.translation or "").strip():
                continue
            changes.append(Change("align", entry.original, old=entry.translation, new=new, reason=reason))
    return changes


def reconcile_cluster(members: Sequence[Any], ask: Ask) -> List[Change]:
    """Ask about one cluster and return the changes to make."""
    return plan_changes(members, ask(cluster_payload(members)))
