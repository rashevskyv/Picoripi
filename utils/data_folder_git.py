"""Keep the user data folder out of Git: a self-ignoring ``.gitignore`` and a check whether a repository ignores it.

Pure logic, no Qt. ``data_folder_git_state`` runs ``git check-ignore`` and blocks until git ends
(at most ``GIT_TIMEOUT_S``): callers on the UI thread must run it in a worker.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from utils.atomic_io import atomic_write_text

GIT_NO_REPO = "no_repo"          # no .git entry at or above the folder
GIT_IGNORED = "ignored"          # a repository ignores the folder, or the folder ignores itself
GIT_NOT_IGNORED = "not_ignored"  # inside a repository that does not ignore the folder
GIT_UNKNOWN = "unknown"          # git could not run, or failed

GITIGNORE_NAME = ".gitignore"
SELF_IGNORE_TEXT = "# Picoripi data folder: Git must not track it.\n*\n"
PROBE_NAME = ".picoripi_git_probe"   # a file name that is never created; git only matches it against the patterns
GIT_TIMEOUT_S = 5


@dataclass(frozen=True)
class GitState:
    state: str
    repo: Optional[Path] = None      # the work tree that holds the folder, when there is one


def _ceilings() -> set:
    """Folders that the search must not reach, from ``GIT_CEILING_DIRECTORIES`` (the same variable git reads)."""
    raw = os.environ.get("GIT_CEILING_DIRECTORIES", "")
    return {Path(part).expanduser().resolve() for part in raw.split(os.pathsep) if part.strip()}


def find_work_tree(path: Path) -> Optional[Path]:
    """The nearest folder at or above ``path`` that holds a ``.git`` entry (a folder, or a file in a linked worktree).

    The search stops before a folder named in ``GIT_CEILING_DIRECTORIES``, as git's own search does.
    """
    folder = Path(path).expanduser().resolve()
    ceilings = _ceilings()
    for candidate in (folder, *folder.parents):
        if candidate in ceilings:
            return None
        if (candidate / ".git").exists():
            return candidate
    return None


def has_self_ignore(folder: Path) -> bool:
    """True when the folder's own ``.gitignore`` holds a line ``*``, which makes Git skip everything in it."""
    try:
        text = (Path(folder) / GITIGNORE_NAME).read_text(encoding="utf-8")
    except OSError:
        return False
    return any(line.strip() == "*" for line in text.splitlines())


def ensure_self_ignore(folder: Path) -> bool:
    """Make the folder ignore itself. Appends to an existing ``.gitignore``, never removes lines. True when it wrote."""
    folder = Path(folder)
    if has_self_ignore(folder):
        return False
    target = folder / GITIGNORE_NAME
    try:
        existing = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    # newline="" keeps "\n" on Windows too: git reads a CR at the end of a pattern as part of it.
    atomic_write_text(target, existing + SELF_IGNORE_TEXT, newline="")
    return True


def data_folder_git_state(path: Path) -> GitState:
    """Whether Git would track files in the folder. Runs ``git check-ignore`` when a repository holds the folder."""
    folder = Path(path).expanduser().resolve()
    repo = find_work_tree(folder)
    if repo is None:
        return GitState(GIT_NO_REPO)
    if has_self_ignore(folder):
        return GitState(GIT_IGNORED, repo)
    probe = (folder.relative_to(repo) / PROBE_NAME).as_posix()
    command = ["git", "-C", str(repo), "check-ignore", "-q", "--", probe]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        done = subprocess.run(command, capture_output=True, timeout=GIT_TIMEOUT_S, creationflags=flags, check=False)
    except (OSError, subprocess.SubprocessError):
        return GitState(GIT_UNKNOWN, repo)
    if done.returncode == 0:
        return GitState(GIT_IGNORED, repo)
    if done.returncode == 1:
        return GitState(GIT_NOT_IGNORED, repo)
    return GitState(GIT_UNKNOWN, repo)
