"""Unpack, build, export and emulator launch for the Project Manager. Every function here runs on a worker thread.

A result folder is written beside its final name and renamed into place only when it is complete, so a cancel or a
crash leaves no half-written folder behind. Only folders this module made are removed.
"""
from __future__ import annotations

import os
import shlex
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from utils.logging_utils import log_info

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]

UNPACKED_NAME = "unpacked"
BUILD_DIR_NAME = "build"
PLACEHOLDER = "{path}"


class Cancel(Exception):
    """Raised when the user cancels a job that has no partial result to keep."""


def _unique_sibling(parent: Path, name: str) -> Path:
    """``parent/name``, or ``parent/name-2``, ``name-3`` ... when that name is taken."""
    candidate = parent / name
    number = 2
    while candidate.exists():
        candidate = parent / f"{name}-{number}"
        number += 1
    return candidate


def _remove_own(folder: Path) -> None:
    """Remove a folder this module made (a temporary one). Never called on a folder the user chose."""
    shutil.rmtree(folder, ignore_errors=True)


def run_unpack(rules: Any, sources: Dict[str, str], project_dir: str | os.PathLike,
               progress: Progress, is_cancelled: Cancelled) -> Optional[str]:
    """Unpack the role files of a new project into ``project_dir/unpacked``.

    Returns the final folder, or None when the plugin needs no unpacking. Raises ``Cancel`` when the user cancelled;
    the temporary folder is then removed and nothing else is touched.
    """
    project = Path(project_dir)
    temporary = project / f".unpack-{uuid.uuid4().hex}"
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        result = rules.unpack_sources(sources, str(temporary), progress, is_cancelled)
        if is_cancelled():
            raise Cancel()
        if result is None:
            _remove_own(temporary)
            return None
        final = _unique_sibling(project, UNPACKED_NAME)
        os.replace(temporary, final)
        log_info(f"Unpacked {len(sources)} source files into {final}.")
        return str(final)
    except BaseException:
        _remove_own(temporary)
        raise


def run_build(rules: Any, target_id: str, project_dir: str | os.PathLike, source_dir: str, translation_dir: str,
              progress: Progress, is_cancelled: Cancelled) -> str:
    """Build ``target_id`` into ``project_dir/build/<target id>`` and return the result path.

    The build is written to a temporary folder first. An existing result of the same target is replaced.
    Raises ``Cancel`` on cancel. Raises ``ValueError`` when the plugin declares no such target.
    """
    build_root = Path(project_dir) / BUILD_DIR_NAME
    build_root.mkdir(parents=True, exist_ok=True)
    temporary = build_root / f".{target_id}-{uuid.uuid4().hex}"
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        result = rules.build_target(target_id, source_dir, translation_dir, str(temporary), progress, is_cancelled)
        if is_cancelled():
            raise Cancel()
        final = build_root / target_id
        previous = None
        if final.exists():
            previous = build_root / f".{target_id}-old-{uuid.uuid4().hex}"
            os.replace(final, previous)
        os.replace(temporary, final)
        if previous is not None:
            _remove_own(previous)
    except BaseException:
        _remove_own(temporary)
        raise
    return _rebase(result, temporary, final)


def _rebase(result: str, temporary: Path, final: Path) -> str:
    """The build may return a path inside its temporary folder; that path moves with the folder."""
    try:
        return str(final / Path(result).relative_to(temporary))
    except ValueError:
        return result


def export_build(build_path: str | os.PathLike, destination: str | os.PathLike, progress: Progress,
                 is_cancelled: Cancelled) -> str:
    """Copy a build folder to ``destination``, a folder that does not exist yet or is empty.

    The copy goes to a temporary sibling first and is renamed into place. A single-file build is copied as a file.
    Raises ``ValueError`` when the destination already holds files.
    """
    source = Path(build_path)
    target = Path(destination)
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"The folder is not empty: {target}")
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = parent / f".export-{uuid.uuid4().hex}"
    try:
        if source.is_dir():
            files = [path for path in source.rglob("*") if path.is_file()]
            temporary.mkdir()
            for position, path in enumerate(files, start=1):
                if is_cancelled():
                    raise Cancel()
                relative = path.relative_to(source)
                (temporary / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, temporary / relative)
                progress(100 * position // max(1, len(files)), relative.as_posix())
        else:
            temporary.mkdir()
            shutil.copy2(source, temporary / source.name)
        if target.exists():
            target.rmdir()
        os.replace(temporary, target)
    except BaseException:
        _remove_own(temporary)
        raise
    return str(target if source.is_dir() else target / source.name)


def emulator_argv(template: str, path: str, posix: Optional[bool] = None) -> List[str]:
    """The program and its arguments for a user's emulator command template.

    The template is split into words first, then ``{path}`` is replaced inside each word, so a path with spaces stays
    one argument. ``posix`` follows the platform by default (Windows keeps the quotes, so they are removed).
    Returns an empty list for an empty template.
    """
    if posix is None:
        posix = os.name != "nt"
    words = shlex.split(template, posix=posix)
    if not posix:
        words = [word[1:-1] if len(word) >= 2 and word[0] == word[-1] == '"' else word for word in words]
    if not words:
        return []
    argv = [word.replace(PLACEHOLDER, path) for word in words]
    if not any(PLACEHOLDER in word for word in words):
        argv.append(path)
    return argv


def list_relative(folder: str | os.PathLike) -> Sequence[str]:
    """Relative file paths under ``folder``, sorted; empty when the folder is missing."""
    root = Path(folder)
    if not root.is_dir():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
