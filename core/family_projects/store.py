"""The family engine: links between members, the shared store, seeding and fan-out. Plugin-agnostic.

Input: for each member the ordered list of (unit id, match key). The plugin supplies both (see model.py).
A member's unit links to a unit of one of its parents when the match keys are equal (align.py). A linked unit
has no text of its own: it reads the text of the parent unit. A text that differs from the parent's is kept as
that member's own override, with a warning. An unlinked unit keeps its text in the member.

File <family folder>\family_translations.json (written atomically, version 2)::

    {"version": 2, "base": "gc",
     "texts": {"gc": {"bmgres.arc/zel_00.bmg#12": {"source": "<sha256>", "text": "<translation>"}},
               "wii": {"bmgres.arc/zel_00.bmg#7": {"source": "<sha256>", "text": "<own or overriding text>"}}}}
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from utils.atomic_io import atomic_write_json

from .align import align, key_hash

VERSION = 2
STORE_FILE = "family_translations.json"


@dataclass(frozen=True)
class Family:
    """base: the base member key. parents: member -> its parents in link order (base: ()).
    units: member -> [(unit id, match key)] in order."""

    base: str
    parents: Mapping[str, Tuple[str, ...]]
    units: Mapping[str, Sequence[Tuple[str, str]]]

    def __post_init__(self) -> None:
        seen = set()
        for member in self.units:
            if member != self.base and not self.parents.get(member):
                raise ValueError(f"member {member!r} has no parent")
            for parent in self.parents.get(member, ()):
                if parent not in self.units:
                    raise ValueError(f"member {member!r} links to unknown parent {parent!r}")
                if parent not in seen:
                    raise ValueError(f"parents must be listed before their children: {member!r}")
            seen.add(member)


Link = Tuple[str, str]  # (parent member, parent unit id)


def links(family: Family) -> Dict[str, Dict[str, Link]]:
    """member -> unit id -> the parent unit it is linked to (first parent that has the same match key)."""
    result: Dict[str, Dict[str, Link]] = {family.base: {}}
    for member, units in family.units.items():
        if member == family.base:
            continue
        linked: Dict[str, Link] = {}
        keys = [key for _, key in units]
        for parent in family.parents[member]:
            parent_units = family.units[parent]
            for parent_pos, pos in align([key for _, key in parent_units], keys).pairs:
                uid = units[pos][0]
                if uid not in linked:
                    linked[uid] = (parent, parent_units[parent_pos][0])
        result[member] = linked
    return result


def load_store(path: Path, base: str) -> dict:
    """The store at path, or an empty store for base when there is no file yet."""
    if not path.is_file():
        return {"version": VERSION, "base": base, "texts": {}}
    store = json.loads(path.read_text(encoding="utf-8"))
    if store.get("version") != VERSION:
        raise ValueError(f"{path}: unknown family store version {store.get('version')!r}")
    return store


def save_store(path: Path, store: dict) -> None:
    atomic_write_json(path, store, ensure_ascii=False, indent=2)


def _resolve(family: Family, linked: Dict[str, Dict[str, Link]], texts: dict, member: str, uid: str,
             keys: Dict[str, Dict[str, str]]) -> str:
    """The text a unit has now: its own entry (when its source still matches), else its parent's."""
    entry = texts.get(member, {}).get(uid)
    if entry and entry["source"] == key_hash(keys[member][uid]):
        return entry["text"]
    link = linked.get(member, {}).get(uid)
    if link is None:
        return ""
    return _resolve(family, linked, texts, link[0], link[1], keys)


def seed(family: Family, translations: Mapping[str, Mapping[str, str]]) -> Tuple[dict, List[str]]:
    """Build the store from every member's translation: translations[member][unit id] ("" = untranslated).

    The base translation fills its own units. A linked unit with an empty parent takes the translation (it fills
    the parent unit). A linked unit with the same text adds nothing. A different text becomes an override of
    that member, with a warning.
    """
    linked = links(family)
    keys = {member: dict(units) for member, units in family.units.items()}
    texts: Dict[str, Dict[str, dict]] = {}
    warnings: List[str] = []

    def put(member: str, uid: str, text: str) -> None:
        texts.setdefault(member, {})[uid] = {"source": key_hash(keys[member][uid]), "text": text}

    for member in family.units:  # base first, then parents before children (checked in Family)
        given = translations.get(member, {})
        for uid, _key in family.units[member]:
            text = given.get(uid, "")
            if not text:
                continue
            link = linked[member].get(uid)
            if link is None:
                put(member, uid, text)
                continue
            parent_text = _resolve(family, linked, texts, link[0], link[1], keys)
            if not parent_text:
                put(link[0], link[1], text)
            elif parent_text != text:
                warnings.append(f"{member} {uid}: translation differs from {link[0]}; kept as override")
                put(member, uid, text)
    store = {"version": VERSION, "base": family.base, "texts": texts}
    return store, warnings


def fanout(family: Family, store: dict, member: str) -> Tuple[Dict[str, Optional[str]], List[str]]:
    """Translation for each unit of one member: text, or None where the member keeps its own text.

    A stored entry whose match key changed is skipped with a warning.
    """
    linked = links(family)
    keys = {m: dict(units) for m, units in family.units.items()}
    texts = store.get("texts", {})
    warnings: List[str] = []
    out: Dict[str, Optional[str]] = {}
    for uid, _key in family.units[member]:
        entry = texts.get(member, {}).get(uid)
        if entry and entry["source"] != key_hash(keys[member][uid]):
            warnings.append(f"{member} {uid}: stored text skipped, source text changed")
        text = _resolve(family, linked, texts, member, uid, keys)
        out[uid] = text or None
    return out, warnings


def trees(family: Family) -> List[Tuple[Tuple[str, str], Tuple[Tuple[str, str], ...]]]:
    """Every unit tree: (root, nodes). The root is the unit no parent link leads from; the nodes are the root and
    every unit linked below it, one per member. A tree with one node is unshared; with more, it is shared."""
    linked = links(family)
    parent = {(m, u): link for m in linked for u, link in linked[m].items()}

    def top(node: Tuple[str, str]) -> Tuple[str, str]:
        while node in parent:
            node = parent[node]
        return node

    grouped: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
    for member, units in family.units.items():
        for uid, _key in units:
            grouped.setdefault(top((member, uid)), []).append((member, uid))
    result = []
    for root, nodes in grouped.items():
        members = [m for m, _ in nodes]
        if len(set(members)) != len(members):
            raise ValueError(f"a unit tree holds two units of one member: {root}")
        result.append((root, tuple([root] + [n for n in nodes if n != root])))
    return result


def normalize(family: Family, store: dict) -> Tuple[dict, List[Tuple[str, str]]]:
    """The store with each tree's text on its root unit. Equal texts below the root are dropped (they resolve to the
    root). A text below the root that differs is kept, and listed: an override that a single shared unit cannot show.
    """
    keys = {(m, u): key for m, units in family.units.items() for u, key in units}
    texts = {m: dict(v) for m, v in store.get("texts", {}).items()}
    overrides: List[Tuple[str, str]] = []
    for root, nodes in trees(family):
        found = []
        for node in nodes:
            entry = texts.get(node[0], {}).get(node[1])
            if entry and entry["text"] and entry["source"] == key_hash(keys[node]):
                found.append((node, entry["text"]))
        if not found:
            continue
        text = found[0][1]
        for node, own in found:
            if own != text:
                overrides.append(node)
            elif node != root:
                del texts[node[0]][node[1]]
        texts.setdefault(root[0], {})[root[1]] = {"source": key_hash(keys[root]), "text": text}
    return {**store, "texts": texts}, overrides
