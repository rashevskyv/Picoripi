"""Write a file so that it is either the old version or the new one, never half of either.

``open(path, "w")`` empties the file first. A crash, a full disk or a killed
process between that and the last byte leaves a truncated file -- and the files
written this way here are a user's translation, glossary, project and settings.

Every function below writes the whole content to a temporary file in the same
folder, flushes it to the disk, and renames it over the target in one step.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Union

PathLike = Union[str, "os.PathLike[str]"]

# On Windows the rename fails while another process (an indexer, an antivirus,
# a sync client) holds the target open for a moment. It is worth a few tries.
_REPLACE_ATTEMPTS = 3
_REPLACE_DELAY = 0.05


def _write(path: PathLike, content: Any, mode: str, **open_arguments: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=str(target.parent), prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, mode, **open_arguments) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        _replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def atomic_write_bytes(path: PathLike, data: bytes) -> None:
    """Replace ``path`` with ``data``. Creates the parent folder. Raises ``OSError`` on failure."""
    _write(path, bytes(data), "wb")


def atomic_write_text(path: PathLike, text: str, encoding: str = "utf-8", newline: Any = None) -> None:
    """Replace ``path`` with ``text``.

    ``newline`` means what it means for ``open()``: the default writes the
    platform's line ending for every line feed -- what ``open(path, "w")``
    did at the places this replaced, so files keep the endings they always
    had. Pass ``""`` to write the text exactly as given.
    """
    _write(path, text, "w", encoding=encoding, newline=newline)


def atomic_write_json(path: PathLike, data: Any, **dumps_arguments: Any) -> None:
    """Replace ``path`` with ``data`` as JSON.

    ``dumps_arguments`` go to ``json.dumps`` (``indent``, ``ensure_ascii``, ...).
    The data is serialised before the file is touched, so an object that cannot
    be serialised leaves the old file as it was.
    """
    atomic_write_text(path, json.dumps(data, **dumps_arguments))


def _replace(temporary: str, target: Path) -> None:
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(temporary, target)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_DELAY)
