"""Choice of the user data folder: options, checks and a copy that never overwrites.

Pure logic, no Qt. The chooser dialog (dialogs/data_location_dialog.py) shows these
results; the copy runs in a worker thread there.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from utils.data_location import is_usable_dir, portable_dir

OPTION_PORTABLE = "portable"   # data folder next to the program (suggested)
OPTION_CUSTOM = "custom"       # a folder the user picks
OPTION_LEGACY = "legacy"       # the old per-user folder, used as it is

PROBLEM_NOT_WRITABLE = "not_writable"
PROBLEM_INSIDE_SOURCE = "inside_source"
PROBLEM_EMPTY = "empty"


@dataclass
class CopyResult:
    copied: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)   # already present at the destination
    stopped: bool = False


@dataclass(frozen=True)
class DataLocationChoice:
    """What the user confirmed: where data goes, what the pointer stores, and what to copy first."""
    option: str
    target: Path
    copy_from: Optional[Path]


def is_inside(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except ValueError:
        return False


def copy_missing(
    source: Path,
    destination: Path,
    should_stop: Callable[[], bool] = lambda: False,
    on_file: Callable[[str], None] = lambda name: None,
) -> CopyResult:
    """Copy every file that the destination lacks. Never overwrites, never deletes or moves the source.

    Idempotent: a second run copies nothing that the first one already placed. Each file is
    written to a temporary name and renamed, so a cancelled run leaves no half-written file.
    """
    if is_inside(destination, source):
        raise ValueError("The destination must not be inside the source folder.")
    result = CopyResult()
    for root, _dirs, files in os.walk(source):
        for name in files:
            if should_stop():
                result.stopped = True
                return result
            src_file = Path(root) / name
            relative = src_file.relative_to(source)
            dst_file = destination / relative
            if dst_file.exists():
                result.skipped.append(relative.as_posix())
                continue
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(dir=str(dst_file.parent), prefix=name + ".", suffix=".part")
            os.close(handle)
            try:
                shutil.copy2(src_file, temporary)
                os.replace(temporary, dst_file)
            except BaseException:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
            result.copied.append(relative.as_posix())
            on_file(relative.as_posix())
    return result


class DataLocationModel:
    """Options and checks for the data folder. ``legacy`` is the old ``~/.picoripi`` folder or None."""

    def __init__(self, root: Path, legacy: Optional[Path] = None):
        self.root = root
        self.legacy = legacy

    def options(self) -> List[str]:
        """Options in display order. The legacy option appears only when the old folder exists."""
        values = [OPTION_PORTABLE, OPTION_CUSTOM]
        if self.legacy is not None:
            values.append(OPTION_LEGACY)
        return values

    def path_for(self, option: str, custom: Optional[Path] = None) -> Optional[Path]:
        if option == OPTION_PORTABLE:
            return portable_dir(self.root)
        if option == OPTION_LEGACY:
            return self.legacy
        if option == OPTION_CUSTOM:
            return custom
        raise ValueError(f"Unknown option: {option}")

    def problems(self, path: Optional[Path], same_ok: bool = False) -> List[str]:
        """Reasons the folder cannot be the target. ``same_ok`` allows the legacy folder itself (the option that keeps it)."""
        if path is None or str(path).strip() == "":
            return [PROBLEM_EMPTY]
        found = []
        if not is_usable_dir(path):
            found.append(PROBLEM_NOT_WRITABLE)
        if self.legacy is not None and is_inside(path, self.legacy) and not (same_ok and self._same(path, self.legacy)):
            found.append(PROBLEM_INSIDE_SOURCE)
        return found

    @staticmethod
    def _same(first: Path, second: Path) -> bool:
        return first.resolve() == second.resolve()

    def free_bytes(self, path: Path) -> Optional[int]:
        probe = path
        while not probe.exists() and probe.parent != probe:
            probe = probe.parent
        try:
            return shutil.disk_usage(probe).free
        except OSError:
            return None

    def build_choice(self, option: str, custom: Optional[Path], copy_legacy: bool) -> DataLocationChoice:
        """Choice for the confirmed option. Copying is possible only into a folder that is not the legacy one."""
        target = self.path_for(option, custom)
        if target is None:
            raise ValueError("No folder chosen.")
        copy_from = None
        if copy_legacy and self.legacy is not None and option != OPTION_LEGACY:
            copy_from = self.legacy
        return DataLocationChoice(option=option, target=target, copy_from=copy_from)
