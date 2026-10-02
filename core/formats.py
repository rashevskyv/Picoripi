"""Which files a game plugin reads and writes, and how.

The host used to decide by extension in five places: ``.json`` was parsed,
``.txt`` read as text, ``.bmg`` read as bytes, anything else refused -- so a
game with its own table format could not be added without editing the host.
Now a plugin says what it handles (``BaseGameRules.get_file_formats``) and
every load and save goes through this module.

A format only says *in what shape* the file content travels between the disk
and the plugin: parsed JSON, text, or raw bytes. Parsing that content into
blocks of strings, and building it back, stays in the plugin's
``load_data_from_json_obj`` / ``save_data_to_json_obj``.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, List, Optional, Sequence, Set, Tuple, Union

from core.data_manager import load_json_file, load_text_file, save_json_file, save_text_file
from utils.logging_utils import log_debug, log_error

MODE_JSON = "json"
MODE_TEXT = "text"
MODE_BYTES = "bytes"
_MODES = (MODE_JSON, MODE_TEXT, MODE_BYTES)

# What to do with an extension no format claims.
UNKNOWN_IS_ERROR = "error"
UNKNOWN_IS_TEXT = "text"


@dataclass(frozen=True)
class FileFormat:
    """Files with these extensions travel to and from the plugin as ``mode``."""

    extensions: Tuple[str, ...]      # lowercase, with the dot: (".tbl",)
    mode: str                        # "json" (parsed), "text" (str) or "bytes"
    label: str = ""                  # for file dialogs: "Text tables"


@dataclass
class SaveContext:
    """What a plugin is told before it builds one file of a project (``prepare_save_context``)."""

    # The data blocks that go into this file, as indices into the loaded data.
    block_indices: Sequence[int] = ()
    # What ``export_runtime_state()`` returned before the save started.
    runtime_state: Any = None
    # Path of the file inside the project, as the project stores it.
    relative_path: str = ""
    # Call it to get the file as it exists now, newest first: the translation
    # copy, then the source. Each item is the raw bytes of one version.
    existing_versions: Callable[[], Iterator[bytes]] = field(default=lambda: iter(()))


DEFAULT_FORMATS: Tuple[FileFormat, ...] = (
    FileFormat((".json",), MODE_JSON, "JSON"),
    FileFormat((".txt",), MODE_TEXT, "Text files"),
)

PathLike = Union[str, Path]


def file_formats(rules: Any) -> Tuple[FileFormat, ...]:
    """The formats ``rules`` handles; the defaults when it does not say or says something unusable."""
    hook = getattr(rules, "get_file_formats", None)
    if not callable(hook):
        return DEFAULT_FORMATS
    try:
        declared = tuple(hook() or ())
    except Exception as error:  # noqa: BLE001 - a broken plugin must not block opening files
        log_error(f"formats: get_file_formats() failed, using the defaults: {error}")
        return DEFAULT_FORMATS
    usable = tuple(
        item for item in declared
        if isinstance(item, FileFormat) and item.mode in _MODES and item.extensions
    )
    return usable or DEFAULT_FORMATS


def resolve(rules: Any, path: PathLike) -> Optional[FileFormat]:
    """The format of ``path`` for this plugin, or None when no format claims its extension."""
    extension = Path(str(path)).suffix.lower()
    for item in file_formats(rules):
        if extension in item.extensions:
            return item
    return None


def supported_extensions(rules: Any) -> Set[str]:
    """Every extension the plugin's formats claim."""
    return {extension for item in file_formats(rules) for extension in item.extensions}


def dialog_filter(rules: Any, extra: Iterable[Tuple[str, Sequence[str]]] = ()) -> str:
    """A Qt file-dialog filter: all supported files first, then one entry per format, then "All".

    ``extra`` adds entries the host knows about itself (archives): ``("Archives", (".arc", ".rarc"))``.
    """
    entries: List[Tuple[str, Sequence[str]]] = [
        (item.label or item.extensions[0].lstrip(".").upper(), item.extensions) for item in file_formats(rules)
    ]
    entries += list(extra)
    everything = " ".join(f"*{extension}" for _label, extensions in entries for extension in extensions)
    parts = [f"Supported Files ({everything})"]
    parts += [f"{label} ({' '.join('*' + extension for extension in extensions)})" for label, extensions in entries]
    parts.append("All (*)")
    return ";;".join(parts)


def read_file(rules: Any, path: PathLike, unknown: str = UNKNOWN_IS_ERROR) -> Tuple[Any, Optional[str]]:
    """``(content, error)`` of a file on disk, in the shape its format asks for."""
    target = Path(str(path))
    found = resolve(rules, target)
    mode = found.mode if found else (MODE_TEXT if unknown == UNKNOWN_IS_TEXT else None)
    if mode is None:
        return None, f"Unsupported file type: {target.suffix.lower()}"
    # The path goes on as the caller gave it (str or Path).
    if mode == MODE_JSON:
        return load_json_file(path)
    if mode == MODE_TEXT:
        return load_text_file(path)
    try:
        return target.read_bytes(), None
    except OSError as error:
        return None, f"Failed to read binary file: {error}"


def decode(rules: Any, path: PathLike, raw: bytes) -> Any:
    """Bytes read from inside an archive, in the shape the format of ``path`` asks for.

    A member no format claims stays bytes, which is what archive members have
    always been handed to the plugin as.
    """
    found = resolve(rules, path)
    if found is None or found.mode == MODE_BYTES or not isinstance(raw, (bytes, bytearray)):
        return raw
    text = bytes(raw).decode("utf-8-sig")
    return json.loads(text) if found.mode == MODE_JSON else text


def write_file(rules: Any, path: PathLike, content: Any, unknown: str = UNKNOWN_IS_ERROR) -> Tuple[bool, Optional[str]]:
    """Write what the plugin built for ``path``. ``(ok, error)``."""
    target = Path(str(path))
    found = resolve(rules, target)
    mode = found.mode if found else (MODE_TEXT if unknown == UNKNOWN_IS_TEXT else None)
    if mode is None:
        return False, f"Unsupported file type: {target.suffix.lower()}"
    if mode == MODE_JSON:
        return (True, None) if save_json_file(path, content) else (False, "Failed to write file to disk.")
    if mode == MODE_TEXT:
        if found is None:
            content = str(content)          # the old fallback for an extension nobody claims
        if not isinstance(content, str):
            return False, f"Plugin did not return a string for {target.suffix.lower()} file."
        return (True, None) if save_text_file(path, content) else (False, "Failed to write file to disk.")
    if not isinstance(content, (bytes, bytearray)):
        return False, f"Plugin did not return bytes for {target.suffix.lower()} file."
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # In one step: a crash mid-write must not leave half a game file.
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_bytes(bytes(content))
        os.replace(temporary, target)
        return True, None
    except OSError as error:
        log_debug(f"formats: failed to write {target}: {error}", category="file_ops")
        return False, f"Failed to save {target.name}: {error}"


# -- the plugin's loading state, as the host handles it --------------------------------
# The host never reads a plugin's attributes; it asks through these. A rules object
# without the hook (an old plugin, a test double) simply has no state.

def export_state(rules: Any) -> Any:
    hook = getattr(rules, "export_runtime_state", None)
    return hook() if callable(hook) else None


def restore_state(rules: Any, state: Any) -> None:
    hook = getattr(rules, "restore_runtime_state", None)
    if callable(hook) and state is not None:
        hook(state)


def reset_state(rules: Any) -> None:
    hook = getattr(rules, "reset_runtime_state", None)
    if callable(hook):
        hook()


def prepare_save(rules: Any, context: SaveContext) -> None:
    hook = getattr(rules, "prepare_save_context", None)
    if callable(hook):
        hook(context)
