"""Where Picoripi keeps user data: only an explicit choice counts, never a silent default.

Explicit choices, in order: the environment variable ``PICORIPI_HOME``, then the pointer
file ``picoripi_home.json`` next to the program. Without either, ``needs_choice`` is True
and the first-start chooser must ask the user. Nothing here creates folders, and nothing
reads the user profile unless the caller passes ``legacy_dir`` (the chooser does, to offer
a copy).
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional

from utils.atomic_io import atomic_write_json

ENV_VAR = "PICORIPI_HOME"
POINTER_NAME = "picoripi_home.json"
PORTABLE_DIR_NAME = "data"
LEGACY_DIR_NAME = ".picoripi"
PROBLEM_SAVED_UNAVAILABLE = "saved_unavailable"   # the pointer names a folder that is missing or read-only


@dataclass(frozen=True)
class DataLocation:
    """Where user data is (or will be) kept, and whether the user still has to choose."""
    path: Path
    explicit: bool        # True when PICORIPI_HOME or the pointer file names the folder
    source: str           # "env", "pointer" or "none"
    problem: str = ""     # the pointer target is missing or read-only

    @property
    def needs_choice(self) -> bool:
        return (not self.explicit) or bool(self.problem)


def app_root() -> Path:
    """The folder of the program: the source tree, or the folder of the frozen executable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def portable_dir(root: Optional[Path] = None) -> Path:
    """The suggested folder: ``data`` next to the program."""
    return (root or app_root()) / PORTABLE_DIR_NAME


def pointer_file(root: Optional[Path] = None) -> Path:
    return (root or app_root()) / POINTER_NAME


def is_usable_dir(path: Path) -> bool:
    """True when the folder exists and accepts writes, or can be created under a writable folder."""
    existing = path
    while not existing.exists():
        if existing.parent == existing:
            return False
        existing = existing.parent
    return existing.is_dir() and os.access(existing, os.W_OK)


def resolve_target(raw: str, root: Path) -> Path:
    """A stored folder: absolute, or relative to the program folder."""
    candidate = Path(raw).expanduser()
    return candidate if candidate.is_absolute() else root / candidate


def read_pointer(root: Optional[Path] = None) -> Optional[str]:
    """The folder string stored in the pointer file, or None when there is no valid pointer."""
    try:
        data = json.loads(pointer_file(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("data_dir") if isinstance(data, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def write_pointer(target: Path, root: Optional[Path] = None) -> None:
    """Store the chosen folder. Inside the program folder it is stored relative, so the pair moves together."""
    base = (root or app_root()).resolve()
    resolved = Path(target).expanduser().resolve()
    try:
        stored = resolved.relative_to(base).as_posix() or "."
    except ValueError:
        stored = str(resolved)
    atomic_write_json(pointer_file(base), {"data_dir": stored}, indent=2)


def resolve_data_location(
    root: Optional[Path] = None,
    environ: Optional[Mapping[str, str]] = None,
    usable: Callable[[Path], bool] = is_usable_dir,
) -> DataLocation:
    """Decide the data folder from the environment and the pointer file only (no home lookup, no writes)."""
    base = root or app_root()
    env = os.environ if environ is None else environ
    raw_env = (env.get(ENV_VAR) or "").strip()
    if raw_env:
        return DataLocation(resolve_target(raw_env, base), explicit=True, source="env")
    raw_pointer = read_pointer(base)
    if raw_pointer:
        target = resolve_target(raw_pointer, base)
        problem = "" if usable(target) else PROBLEM_SAVED_UNAVAILABLE
        return DataLocation(target, explicit=True, source="pointer", problem=problem)
    return DataLocation(portable_dir(base), explicit=False, source="none")


def legacy_dir(home: Optional[Path] = None) -> Optional[Path]:
    """The old per-user folder (``~/.picoripi``) when it exists. Offered for copying, never used silently."""
    candidate = (home or Path.home()) / LEGACY_DIR_NAME
    return candidate if candidate.is_dir() else None
