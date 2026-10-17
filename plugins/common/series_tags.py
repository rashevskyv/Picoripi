"""Control tags across the games of a series: a neutral form of a text, and a carry-over of a translation.

A plugin declares its control tags with ``get_series_tag_map()`` on its rules. The declaration is a
``TagMap``: the syntax name, a regex that finds one tag of that syntax, and ``kind_of``, which gives a
tag its kind. Two games carry a translation across when they give the same kind to the tags of the
same text. The kind vocabulary is shared; a plugin uses a common kind only where its own codec means the
same thing. Otherwise it uses a kind that names the tag (``icon:E447``): then the tag never matches
another syntax, which is the safe answer.

Common kinds: ``line``, ``page``, ``scroll``, ``wait``, ``colour``, ``name`` (a name the game inserts),
``number`` (a number the game inserts), ``form`` (a word form chosen by gender or count), ``speed``.

The row of a translation memory keeps ``syntax`` (the ``TagMap.name``), ``tags`` (``[tag, kind]`` in
source order) and ``neutral`` (the text with every tag replaced by its kind). Equal ``neutral`` texts
carry the same kinds in the same order. ``carry`` converts a translation into the syntax of the target
text, or returns the reason it cannot.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple

from core.i18n import tr
from plugins.common.tag_logic import ANY_TAG_PATTERN, compare_tags

KIND_OPEN, KIND_CLOSE = "⟨", "⟩"


@dataclass(frozen=True)
class TagMap:
    """How one game's syntax shows its control tags. ``kind_of`` returns None for a tag with no kind (no match)."""

    name: str
    pattern: Pattern[str]
    kind_of: Callable[[str], Optional[str]]


def _fold(text: str) -> str:
    return " ".join(text.split()).casefold()


def body_kind(tag: str) -> str:
    """A kind that names the tag: its body without the brackets, spaces folded.

    ``{text_ram wStringBuffer}`` and ``[text_ram wStringBuffer]`` share one kind; a tag no codec names in common
    keeps its own kind, so it matches only a tag with the same body.
    """
    body = tag[1:-1] if len(tag) >= 2 else tag
    return "tag:" + " ".join(body.split())


def kind_by_name(tag: str, names: Dict[str, str]) -> str:
    """The common kind a codec names for a bare tag (``{cont}`` -> ``scroll``); any other tag gets ``body_kind``."""
    body = " ".join(tag[1:-1].split()) if len(tag) >= 2 else ""
    return names.get(body) or body_kind(tag)


def tags_of(text: str, tag_map: TagMap) -> Optional[List[Tuple[str, str]]]:
    """``[(tag, kind)]`` in order, or None when a tag has no kind."""
    found = []
    for match in tag_map.pattern.finditer(text):
        kind = tag_map.kind_of(match.group(0))
        if kind is None:
            return None
        found.append((match.group(0), kind))
    return found


def neutral_of(text: str, tag_map: TagMap) -> Optional[str]:
    """The text with every tag replaced by its kind, folded like a source text; None when a tag has no kind."""
    out: List[str] = []
    pos = 0
    for match in tag_map.pattern.finditer(text):
        kind = tag_map.kind_of(match.group(0))
        if kind is None:
            return None
        out.append(_fold(text[pos:match.start()]))
        out.append(f"{KIND_OPEN}{kind}{KIND_CLOSE}")
        pos = match.end()
    out.append(_fold(text[pos:]))
    return "".join(out)


def neutral_key(neutral: str) -> str:
    """The key of a neutral text in the series index."""
    return hashlib.sha1(neutral.encode("utf-8")).hexdigest()


def tag_fields(text: str, tag_map: Optional[TagMap]) -> Dict[str, Any]:
    """The fields a memory row keeps for ``text``: ``syntax``, ``tags``, ``neutral``; empty without a usable tag map."""
    if tag_map is None:
        return {}
    found = tags_of(text, tag_map)
    if found is None:
        return {}
    return {"syntax": tag_map.name, "tags": [[tag, kind] for tag, kind in found], "neutral": neutral_of(text, tag_map)}


def carry(translation: str, row: Dict[str, Any], target_source: str, target_map: TagMap) -> Tuple[Optional[str], str]:
    """``(text, "")``: the translation in the target's syntax, or ``(None, reason)`` when it cannot be carried.

    ``row`` is a memory row with ``source``, ``translation``, ``syntax`` and ``tags``. A row of the same syntax
    carries only with the same tags. Across syntaxes, each tag takes the target tag of the same kind. A kind
    that occurs with two different tags on either side is ambiguous and blocks the carry-over.
    """
    target_tags = tags_of(target_source, target_map)
    if target_tags is None:
        return None, tr("A tag of the current text has no kind in this game.")
    row_tags = [(str(tag), str(kind)) for tag, kind in row.get("tags") or []]
    if row.get("syntax") == target_map.name:
        if row_tags == target_tags:
            return translation, ""
        return None, tr("The tags of the other game's text are not the tags of this text.")
    if [kind for _, kind in row_tags] != [kind for _, kind in target_tags]:
        return None, tr("The tags of the two texts do not have the same kinds in the same order.")
    mapping: Dict[str, str] = {}
    source_by_kind: Dict[str, set] = {}
    target_by_kind: Dict[str, set] = {}
    for tag, kind in row_tags:
        source_by_kind.setdefault(kind, set()).add(tag)
    for tag, kind in target_tags:
        target_by_kind.setdefault(kind, set()).add(tag)
    for kind, sources in source_by_kind.items():
        targets = target_by_kind[kind]
        if len(sources) > 1 or len(targets) > 1:
            return None, tr("Two different tags of kind {kind} in one text: the pairing is not known.", kind=kind)
        mapping[next(iter(sources))] = next(iter(targets))
    if mapping:
        replacer = re.compile("|".join(re.escape(tag) for tag in sorted(mapping, key=len, reverse=True)))
        result = replacer.sub(lambda match: mapping[match.group(0)], translation)
    else:
        result = translation
    target_texts = Counter(tag for tag, _ in target_tags)
    in_result = Counter(match.group(0) for match in target_map.pattern.finditer(result))
    if in_result != target_texts:
        missing = target_texts - in_result
        if missing:
            return None, tr("The translation lacks a tag of the current text: {tag}", tag=next(iter(missing)))
        return None, tr("The translation has a tag that is not a tag of the current text.")
    for chunk in ANY_TAG_PATTERN.findall(result):
        if chunk not in target_texts:
            return None, tr("The translation has a tag that this game does not have: {tag}", tag=chunk)
    status, message = compare_tags(result, target_source)
    if status != "OK":
        return None, message
    return result, ""
