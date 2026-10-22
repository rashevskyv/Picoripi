"""The images a game plugin opens: the declarations in its ``config.json``, checked for the validator, the wizard and the wiki.

A declaration is ``{"kind", "id", "region", "note"}``. ``kind`` says what ``id`` is:

- ``disc``: a GameCube, Wii or Dreamcast game code (``GZLE01``, ``MK-51052``);
- ``title``: a 16-digit title ID of a 3DS, Switch or Wii U title (``0100ABF008968000``);
- ``code``: a four-letter product code of a DS, GBA or 3DS cartridge or title (``AYWE``);
- ``hash``: the SHA-1 of a ROM file the plugin's facts describe (``rom_facts``);
- ``serial``: a PlayStation or PlayStation 2 serial (``SLUS-00067``);
- ``name``: the internal name a cartridge ROM carries in its header (``CONKER BFD``);
- ``unchecked``: the game is known but the plugin reads no id; ``id`` is empty;
- ``any``: the plugin opens any file of its kind; ``id`` is empty.

``region`` is a region such as ``USA``, ``EUR`` or ``JPN``, ``All regions`` for a region-free id (Switch titles), or
``Not stated`` when the region is not known yet. Only ``any`` may leave it empty. ``note`` is free text: a version, a revision or a remark. Ids are written as the image holds them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ID_KINDS = ("disc", "title", "code", "serial", "name", "hash")
KINDS = ID_KINDS + ("unchecked", "any")
FIELDS = ("kind", "id", "region", "note")

Entry = Dict[str, str]


def normalise(entries: Any) -> List[Entry]:
    """The declarations as clean dicts with every field a string; anything else is dropped."""
    if not isinstance(entries, list):
        return []
    out: List[Entry] = []
    for item in entries:
        if isinstance(item, dict):
            out.append({field: str(item.get(field) or "").strip() for field in FIELDS})
    return out


def declared_in(folder: Path) -> List[Entry]:
    """The declarations of the plugin in ``folder`` (its config.json); an empty list when there are none or it is unreadable."""
    try:
        return normalise(json.loads((Path(folder) / "config.json").read_text(encoding="utf-8")).get("supported_images"))
    except (OSError, ValueError, AttributeError):
        return []


def problems(entries: Any) -> List[str]:
    """Why a ``supported_images`` value is wrong, one line each; an empty list when it is right."""
    if not isinstance(entries, list) or not entries:
        return ["supported_images must be a non-empty list"]
    found: List[str] = []
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            found.append(f"supported_images[{index}] must be an object")
            continue
        kind, ident, region = str(item.get("kind") or ""), str(item.get("id") or ""), str(item.get("region") or "")
        where = f"supported_images[{index}]"
        if kind not in KINDS:
            found.append(f"{where}: kind '{kind}' is not one of {', '.join(KINDS)}")
        elif kind in ID_KINDS and not ident:
            found.append(f"{where}: kind '{kind}' needs an id")
        elif kind in ("any", "unchecked") and ident:
            found.append(f"{where}: kind '{kind}' takes no id")
        if kind != "any" and not region:
            found.append(f"{where}: region is missing (write the region, or a note when several apply)")
        unknown = sorted(set(item) - set(FIELDS))
        if unknown:
            found.append(f"{where}: keys the host does not read: {', '.join(unknown)}")
    return found


def ids_of(entries: Iterable[Entry], kinds: Sequence[str] = ID_KINDS) -> Tuple[str, ...]:
    """The ids of the declarations of the given kinds, in order."""
    return tuple(item["id"] for item in entries if item.get("kind") in kinds and item.get("id"))


_NOT_ALNUM = re.compile(r"[^0-9A-Za-z]")


def appears_in(ident: str, text: str) -> bool:
    """True when a declared id occurs in source text. Punctuation is ignored: ``SLUS-00067`` matches ``SLUS_000.67``."""
    return _NOT_ALNUM.sub("", ident).upper() in _NOT_ALNUM.sub("", text).upper()
