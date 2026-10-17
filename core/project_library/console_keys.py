"""Where the key file of each console is: one path per console, kept in the data folder.

Picoripi stores the path only. It never copies a key file, never reads one here, and never logs or shows a key value
or the path. The path is not part of any project and is never sent to a Work Together room. ``path_for`` returns a
path only while the file still exists, so a moved or deleted key file makes the wizard ask again.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

from utils import constants

CONSOLES = ("3ds", "switch", "wii", "oodle")   # "oodle": the Oodle core library (a DLL path), not a key file
STORE_NAME = "console_keys.json"


def store_path() -> Path:
    """The store file. Read at call time, so a test that moves the data folder moves it too."""
    return constants.SETTINGS_DIR / STORE_NAME


def _read() -> Dict[str, str]:
    try:
        data = json.loads(store_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if key in CONSOLES and isinstance(value, str)}


def path_for(console: str) -> Optional[str]:
    """The key file path of ``console`` while that file exists, else None. Safe to call on any thread."""
    path = _read().get(console, "")
    return path if path and os.path.isfile(path) else None


def states() -> Dict[str, Tuple[str, bool]]:
    """``{console: (stored path, file exists)}`` for every console. It stats the files: call it on a worker."""
    data = _read()
    result: Dict[str, Tuple[str, bool]] = {}
    for console in CONSOLES:
        value = data.get(console, "")
        result[console] = (value, bool(value) and os.path.isfile(value))
    return result


def stored(console: str) -> str:
    """The stored path of ``console`` even when that file is gone; "" when none is stored. For the settings page."""
    return _read().get(console, "")


def set_path(console: str, path: str) -> None:
    """Remember ``path`` as the key file of ``console``. The store is written atomically (temporary file, then replace)."""
    _check(console)
    data = _read()
    data[console] = str(path)
    _write(data)


def clear_path(console: str) -> None:
    """Forget the key file of ``console``. The next unpack that needs it asks again."""
    _check(console)
    data = _read()
    data.pop(console, None)
    _write(data)


def _check(console: str) -> None:
    if console not in CONSOLES:
        raise ValueError(f"unknown console: {console}")


def _write(data: Dict[str, str]) -> None:
    folder = store_path().parent
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / f".{STORE_NAME}.{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temporary, store_path())
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
