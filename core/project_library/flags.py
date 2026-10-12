"""The user's own flags of a project ("built", "verified in game"), stored in the project file's metadata.

A flag is written only when the user sets it. Callers use this for a project that is not open; an open project keeps
its flags in memory and saves them with its own file (see the Project Manager window).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

from utils.atomic_io import atomic_write_json

FLAG_NAMES = ("built", "verified_in_game")


def set_flags(project_file: str | os.PathLike, updates: Dict[str, bool]) -> Dict[str, bool]:
    """Set the given flags in ``metadata.flags`` of the project file, atomically. Returns all flags stored.

    Unknown flag names are refused with ``ValueError``. Other metadata and other project data stay as they are.
    """
    unknown = set(updates) - set(FLAG_NAMES)
    if unknown:
        raise ValueError(f"Unknown project flags: {sorted(unknown)}")
    path = Path(project_file)
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("project file is not a JSON object")
    metadata = document.setdefault("metadata", {})
    flags = dict(metadata.get("flags") or {})
    flags.update({name: bool(value) for name, value in updates.items()})
    metadata["flags"] = {name: flags[name] for name in FLAG_NAMES if name in flags}
    atomic_write_json(path, document, indent=2, ensure_ascii=False)
    return dict(metadata["flags"])


def flags_of(metadata: Dict) -> Dict[str, bool]:
    """The stored flags of a project's metadata, with every known flag present."""
    stored = metadata.get("flags") or {}
    return {name: bool(stored.get(name, False)) for name in FLAG_NAMES}
