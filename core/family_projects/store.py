"""The family translation store: shared units, per-console overrides, seeding and fan-out.

File: <family folder>\family_translations.json (written atomically, version 1)::

    {"version": 1, "base": "gc",
     "units":     {"zel_00.bmg#12": {"source": "<sha256>", "text": "<translation>"}},
     "overrides": {"hd": {"zel_00.bmg": {"9": {"source": "<sha256>", "text": "<translation>"}}}}}

A unit is one message of the base console. A console message with the same source text is linked to that
unit (see `align`). An override belongs to one console and wins for that console only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from utils.atomic_io import atomic_write_json

from .align import align, source_hash

VERSION = 1
STORE_FILE = "family_translations.json"


def unit_id(member: str, index: int) -> str:
    return f"{member}#{index}"


def empty_store(base: str) -> dict:
    return {"version": VERSION, "base": base, "units": {}, "overrides": {}}


def load_store(path: Path, base: str) -> dict:
    """The store at path, or an empty store for base when there is no file yet."""
    import json

    if not path.is_file():
        return empty_store(base)
    store = json.loads(path.read_text(encoding="utf-8"))
    if store.get("version") != VERSION:
        raise ValueError(f"{path}: unknown family store version {store.get('version')!r}")
    return store


def save_store(path: Path, store: dict) -> None:
    atomic_write_json(path, store, ensure_ascii=False, indent=2)


def seed(base: str, sources: Mapping[str, Mapping[str, Sequence[str]]],
         translations: Mapping[str, Mapping[str, Sequence[str]]]) -> Tuple[dict, List[str]]:
    """Build the store from every console's source and translation.

    sources[console][member] and translations[console][member] are lists per message; "" means untranslated.
    The base translation fills the units. A console translation of a linked message fills an empty unit; a
    different one is kept as that console's override, with a warning. A console-only message keeps its
    translation as an override.
    """
    store = empty_store(base)
    warnings: List[str] = []
    base_sources = sources[base]
    base_tr = translations.get(base, {})
    for member, texts in base_sources.items():
        tr = list(base_tr.get(member, [""] * len(texts)))
        for index, text in enumerate(texts):
            store["units"][unit_id(member, index)] = {"source": source_hash(text), "text": tr[index]}
    for console, members in sources.items():
        if console == base:
            continue
        console_tr = translations.get(console, {})
        overrides: Dict[str, Dict[str, dict]] = {}
        for member, texts in members.items():
            tr = list(console_tr.get(member, [""] * len(texts)))
            member_overrides: Dict[str, dict] = {}
            linked = {}
            if member in base_sources:
                for base_index, index in align(base_sources[member], texts).pairs:
                    linked[index] = unit_id(member, base_index)
            for index, text in enumerate(texts):
                own = tr[index]
                if not own:
                    continue
                uid = linked.get(index)
                if uid is None:
                    member_overrides[str(index)] = {"source": source_hash(text), "text": own}
                    continue
                unit = store["units"][uid]
                if not unit["text"]:
                    unit["text"] = own
                elif unit["text"] != own:
                    warnings.append(f"{console} {uid}: translation differs from the family unit; kept as override")
                    member_overrides[str(index)] = {"source": source_hash(text), "text": own}
            if member_overrides:
                overrides[member] = member_overrides
        if overrides:
            store["overrides"][console] = overrides
    return store, warnings


def fanout(store: dict, sources: Mapping[str, Mapping[str, Sequence[str]]],
           console: str) -> Tuple[Dict[str, List[Optional[str]]], List[str]]:
    """Translations to write into one console: per member a list, None where nothing changes.

    The override of this console wins over the shared unit. An override or unit whose source text no longer
    matches the console message is skipped with a warning.
    """
    warnings: List[str] = []
    base = store["base"]
    result: Dict[str, List[Optional[str]]] = {}
    for member, texts in sources[console].items():
        out: List[Optional[str]] = [None] * len(texts)
        if console == base:
            for index, text in enumerate(texts):
                unit = store["units"].get(unit_id(member, index))
                if unit and unit["text"] and unit["source"] == source_hash(text):
                    out[index] = unit["text"]
        elif member in sources.get(base, {}):
            for base_index, index in align(sources[base][member], texts).pairs:
                unit = store["units"].get(unit_id(member, base_index))
                if unit and unit["text"]:
                    out[index] = unit["text"]
        for key, override in store.get("overrides", {}).get(console, {}).get(member, {}).items():
            index = int(key)
            if index < len(texts) and override["source"] == source_hash(texts[index]):
                out[index] = override["text"]
            else:
                warnings.append(f"{console} {member}#{key}: override skipped, source text changed")
        result[member] = out
    return result, warnings
