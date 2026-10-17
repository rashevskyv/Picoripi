"""The project manager's own list: added projects, user folders and the view choices (``project_manager.json``)."""
from __future__ import annotations

import copy
import json
import os
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from utils.atomic_io import atomic_write_json
from utils.logging_utils import log_debug, log_warning

SCHEMA_VERSION = 1
REGISTRY_FILE_NAME = "project_manager.json"
DEFAULT_VIEW = {"group_by": "folder", "sort_by": "name", "descending": False}

# One lock for every read-modify-write: jobs run on worker threads, and two of them must not interleave.
_lock = threading.Lock()


def project_key(path: str | os.PathLike) -> str:
    """The identity of a project in the registry: its absolute, case-normalised path."""
    return os.path.normcase(os.path.abspath(str(path)))


def _empty_document() -> Dict[str, Any]:
    return {"version": SCHEMA_VERSION, "folders": [], "projects": [], "view": dict(DEFAULT_VIEW), "settings": {}}


# The settings the Project Manager keeps. Keys for AI services are not here: they live on the AI settings page only.
# ``emulator_command`` is the command of every platform before per-platform commands existed; a platform's own
# command is stored as ``emulator_command.<platform id>`` (see ``emulator_setting``).
EMULATOR_KEY = "emulator_command"
EMULATOR_PREFIX = EMULATOR_KEY + "."
SETTING_NAMES = (EMULATOR_KEY,)
_PLATFORM_ID = re.compile(r"[A-Za-z0-9_.-]{1,40}")


def emulator_setting(platform: str) -> str:
    """The settings name of one platform's emulator command. No platform (""): the shared command."""
    return EMULATOR_PREFIX + platform if platform else EMULATOR_KEY


def _known_setting(name: str) -> bool:
    if name in SETTING_NAMES:
        return True
    return name.startswith(EMULATOR_PREFIX) and bool(_PLATFORM_ID.fullmatch(name[len(EMULATOR_PREFIX):]))


def _set_aside(path: Path, reason: str) -> None:
    """Keep a file we cannot read under another name, so the next save does not replace the user's data."""
    aside = path.with_name(path.name + ".unreadable")
    try:
        os.replace(path, aside)
        log_warning(f"Project manager registry set aside as {aside.name}: {reason}")
    except OSError as exc:
        log_warning(f"Could not set aside project manager registry {path}: {exc}")


def _read_document(path: Path, set_aside: bool = True) -> Dict[str, Any]:
    """The stored document; an unreadable file is set aside unless ``set_aside`` is false (a dry run reads only)."""
    if not path.exists():
        return _empty_document()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        if set_aside:
            _set_aside(path, str(exc))
        return _empty_document()
    if not isinstance(raw, dict) or int(raw.get("version", 0) or 0) > SCHEMA_VERSION:
        if set_aside:
            _set_aside(path, "not a registry this version can read")
        return _empty_document()
    document = _empty_document()
    document.update(raw)  # unknown keys from a newer build stay in the file
    for key in ("folders", "projects"):
        if not isinstance(document.get(key), list):
            document[key] = []
    document["view"] = {**DEFAULT_VIEW, **(document.get("view") or {})}
    if not isinstance(document.get("settings"), dict):
        document["settings"] = {}
    return document


class Registry:
    """An in-memory copy of ``project_manager.json``. Only the jobs in ``mutate`` and ``read`` create one."""

    def __init__(self, document: Dict[str, Any]):
        self.document = document

    # ----- projects -----
    def projects(self) -> List[Dict[str, Any]]:
        return [copy.deepcopy(entry) for entry in self.document["projects"]]

    def _find(self, path: str | os.PathLike) -> Optional[Dict[str, Any]]:
        key = project_key(path)
        for entry in self.document["projects"]:
            if project_key(entry["path"]) == key:
                return entry
        return None

    def add(self, path: str | os.PathLike, project_id: str = "", platform: str = "",
            folder_id: Optional[str] = None) -> bool:
        """Add a project. Returns False when it is already in the registry."""
        if self._find(path) is not None:
            return False
        self.document["projects"].append({
            "id": uuid.uuid4().hex,
            "path": os.path.abspath(str(path)),
            "project_id": project_id,
            "name": "",
            "folder_id": folder_id if self._folder(folder_id) else None,
            "platform": platform,
            "added": _now(),
            "last_opened": None,
        })
        return True

    def remove(self, path: str | os.PathLike) -> bool:
        entry = self._find(path)
        if entry is None:
            return False
        self.document["projects"].remove(entry)
        return True

    def touch_opened(self, path: str | os.PathLike, project_id: str = "") -> None:
        """Mark a project as opened now. Adds it when it is not in the registry yet."""
        self.add(path, project_id=project_id)
        entry = self._find(path)
        entry["last_opened"] = _now()
        if project_id and not entry.get("project_id"):
            entry["project_id"] = project_id

    def update_fields(self, path: str | os.PathLike, **fields: Any) -> bool:
        """Set ``name``, ``platform`` or ``folder_id`` of a project. Unknown fields are refused."""
        allowed = {"name", "platform", "folder_id"}
        entry = self._find(path)
        if entry is None or not set(fields) <= allowed:
            return False
        if "folder_id" in fields and fields["folder_id"] is not None and not self._folder(fields["folder_id"]):
            return False
        entry.update(fields)
        return True

    # ----- folders -----
    def folders(self) -> List[Dict[str, str]]:
        return [dict(folder) for folder in self.document["folders"]]

    def _folder(self, folder_id: Optional[str]) -> Optional[Dict[str, Any]]:
        for folder in self.document["folders"]:
            if folder["id"] == folder_id:
                return folder
        return None

    def create_folder(self, name: str) -> str:
        folder_id = uuid.uuid4().hex
        self.document["folders"].append({"id": folder_id, "name": name.strip()})
        return folder_id

    def rename_folder(self, folder_id: str, name: str) -> bool:
        folder = self._folder(folder_id)
        if folder is None:
            return False
        folder["name"] = name.strip()
        return True

    def delete_folder(self, folder_id: str) -> bool:
        """Remove a folder. Its projects move to the root; no project is removed."""
        folder = self._folder(folder_id)
        if folder is None:
            return False
        self.document["folders"].remove(folder)
        for entry in self.document["projects"]:
            if entry.get("folder_id") == folder_id:
                entry["folder_id"] = None
        return True

    # ----- view -----
    def view(self) -> Dict[str, Any]:
        return dict(self.document["view"])

    def set_view(self, **choices: Any) -> None:
        self.document["view"].update({k: v for k, v in choices.items() if k in DEFAULT_VIEW})

    # ----- settings -----
    def settings(self) -> Dict[str, Any]:
        stored = self.document["settings"]
        names = list(SETTING_NAMES) + sorted(name for name in stored if _known_setting(name) and name not in SETTING_NAMES)
        return {name: stored.get(name, "") for name in names}

    def set_setting(self, name: str, value: str) -> bool:
        """Store one Project Manager setting. Unknown names are refused."""
        if not _known_setting(name):
            return False
        self.document["settings"][name] = str(value)
        return True


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def registry_path(directory: str | os.PathLike) -> Path:
    return Path(directory) / REGISTRY_FILE_NAME


def read(directory: str | os.PathLike, set_aside: bool = True) -> Dict[str, Any]:
    """The registry document as stored (a job calls this on a worker thread).

    ``set_aside=False`` reads without moving or writing anything: an unreadable file reads as an empty registry.
    """
    with _lock:
        return _read_document(registry_path(directory), set_aside=set_aside)


def mutate(directory: str | os.PathLike, operation: Callable[[Registry], Any], *args: Any) -> Dict[str, Any]:
    """Load the registry, apply ``operation(registry, *args)``, write it atomically, return the new document.

    Runs on a worker thread. Failing writes raise ``OSError`` to the caller's job.
    """
    path = registry_path(directory)
    with _lock:
        registry = Registry(_read_document(path))
        operation(registry, *args)
        atomic_write_json(path, registry.document, indent=2, ensure_ascii=False)
        log_debug(f"Project manager registry saved ({len(registry.document['projects'])} projects).")
        return copy.deepcopy(registry.document)
