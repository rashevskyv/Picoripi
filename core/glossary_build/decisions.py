"""What the glossary has already decided, selected for one build request.

Every build request used to be stateless: a chunk was swept, or a term
translated, without being told a single thing the glossary already holds. So
"Clawshots" was translated with no idea that "Clawshot" is "Кігтемет", and a
family of names drifted apart one member at a time. ``select_related`` picks the
decided entries that share words with the text at hand and renders them as
``term → translation`` lines short enough to ride along in the prompt.

Pure functions over plain entries: no Qt, no manager, no I/O.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Set, Tuple

from core.glossary_manager import (
    STATUS_FRAGMENTS,
    STATUS_SEEDED,
    STATUS_SYNTHESIZED,
    STATUS_TRANSLATED,
    GlossaryManager,
)

DEFAULT_LIMIT = 40
# A word shared by more entries than this relates none of them in particular
# ("key", "great", a numbered speaker's base name).
MAX_FAMILY_WORD_SPREAD = 12

# An entry in one of these states has no translation anyone settled on.
_UNDECIDED = frozenset({STATUS_SEEDED, STATUS_FRAGMENTS, STATUS_SYNTHESIZED})
# Words that relate nothing to anything.
_STOP = frozenset({"of", "the", "and", "a", "an", "to", "in", "on", "for", "with", "at", "from", "by", "or", "is"})

_HEADINGS = {
    "extract": (
        "Already in the glossary (settled):\n{lines}\n"
        "Do not list these again unless this text shows a new sense. Return every term exactly as the text "
        "spells it."
    ),
    # The one-shot builder: extracts and translates in the same request.
    "build": (
        "Already in the glossary (settled):\n{lines}\n"
        "Do not list these again. When a new term shares part of its name with them, reuse the same root and "
        "spelling for that part."
    ),
    "translate": (
        "Settled renderings of related terms:\n{lines}\n"
        "Reuse the same root and spelling for the part of the name this term shares with them."
    ),
}


def _stem(token: str) -> str:
    """Crude on purpose: enough to relate "Hylia" to "Hylian" and "Twili" to "Twilight"."""
    return token[:5] if len(token) > 5 else token


def _tokens(text: str) -> Set[str]:
    return {
        _stem(token)
        for token in GlossaryManager.canonical_key(text or "").split()
        if len(token) >= 3 and token not in _STOP
    }


def is_decided(entry: Any) -> bool:
    """Whether the entry carries a translation somebody (or an earlier pass) settled on."""
    return bool(getattr(entry, "translation", "")) and getattr(entry, "status", "") not in _UNDECIDED


def select_related(entries: Iterable[Any], text: str, limit: int = DEFAULT_LIMIT, *, exclude: str = "") -> str:
    """``term → translation`` lines for the decided entries related to ``text``.

    Related means sharing at least one meaningful word (by a short stem) with
    ``text``. Ranked: entries a person confirmed -- or that came without a
    status, i.e. were written by hand -- before machine-translated ones, then
    by how many words they share, then shorter terms first. ``exclude`` is the
    term being translated, whose own old rendering must not be offered back to
    it -- that exact term only: "Clawshots" kept as its own entry is still shown
    what "Clawshot" got. Returns ``""`` when nothing is related.
    """
    text_tokens = _tokens(text)
    if not text_tokens:
        return ""
    excluded = exclude.casefold()
    ranked: List[Tuple[int, int, int, str, str]] = []
    for entry in entries:
        if not is_decided(entry):
            continue
        original = entry.original
        if excluded and original.casefold() == excluded:
            continue
        overlap = len(_tokens(original) & text_tokens)
        if not overlap:
            continue
        machine = 1 if getattr(entry, "status", "") == STATUS_TRANSLATED else 0
        ranked.append((machine, -overlap, len(original), original, entry.translation))
    ranked.sort()
    return "\n".join(f"- {original} → {translation}" for _, _, _, original, translation in ranked[:limit])


def decided_from_reply(items: Iterable[Any]) -> List[Any]:
    """Terms an earlier request of the same run returned, as entries ``select_related`` can read."""
    return [
        SimpleNamespace(
            original=str(item.get("term") or "").strip(),
            translation=str(item.get("translation") or "").strip(),
            status=STATUS_TRANSLATED,
        )
        for item in items
        if isinstance(item, dict) and item.get("term") and item.get("translation")
    ]


def decided_block(related: str, purpose: str) -> str:
    """The prompt block for ``related`` lines, or ``""`` when there are none."""
    return _HEADINGS[purpose].format(lines=related) if related else ""


def _head_key(entry: Any) -> Tuple[int, str, str]:
    key = GlossaryManager.canonical_key(entry.original)
    return (len(key.split()), key, entry.original)


def families(entries: Iterable[Any]) -> List[List[Any]]:
    """Group entries that share a distinctive word; in each group the head term comes first.

    "Hylia", "Lake Hylia" and "Hylian Shield" are one family; so are "Clawshot"
    and "Clawshots". A word that many entries share is ignored (see
    ``MAX_FAMILY_WORD_SPREAD``). An entry related to nothing is a family of
    one. The result is deterministic: members by (number of words, canonical
    key), families by their head's canonical key.
    """
    entries = list(entries)
    stems = [_tokens(entry.original) for entry in entries]
    spread = Counter(stem for entry_stems in stems for stem in entry_stems)
    parent = list(range(len(entries)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    sharing: Dict[str, List[int]] = defaultdict(list)
    for index, entry_stems in enumerate(stems):
        for stem in entry_stems:
            if 2 <= spread[stem] <= MAX_FAMILY_WORD_SPREAD:
                sharing[stem].append(index)
    for members in sharing.values():
        for index in members[1:]:
            parent[find(index)] = find(members[0])

    groups: Dict[int, List[Any]] = defaultdict(list)
    for index, entry in enumerate(entries):
        groups[find(index)].append(entry)
    result = [sorted(group, key=_head_key) for group in groups.values()]
    result.sort(key=lambda group: _head_key(group[0])[1:])
    return result
