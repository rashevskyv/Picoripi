"""The owner's RomHacking workspace, for the tests that read real game files.

Set ``PICORIPI_ROMHACKING`` to the workspace root (the folder that holds the game folders). Unset, or a file
missing under it, the test skips with the reason. The repository keeps no personal paths.
"""
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import pytest

ENV = "PICORIPI_ROMHACKING"


def needs_scratch(gb: int) -> None:
    """Skip unless the temp folder has ``gb`` GB free: an unpack of a real game writes that much project data there."""
    free = shutil.disk_usage(tempfile.gettempdir()).free
    if free < gb * 2**30:
        pytest.skip(f"an unpack here needs {gb} GB free in the temp folder; {free // 2**30} GB is free")


def root() -> Optional[Path]:
    value = os.environ.get(ENV, "").strip()
    return Path(value) if value else None


def missing(*parts: str) -> Optional[str]:
    """Why ``parts`` under the root cannot be used, or None when the file is there."""
    base = root()
    if base is None:
        return f"{ENV} is not set: the real game files are not checked"
    if not base.joinpath(*parts).exists():
        return f"not on disk under {ENV}: {'/'.join(parts)}"
    return None


def path(*parts: str) -> Path:
    """The path under the root; call only after ``missing`` returned None."""
    return _base().joinpath(*parts)


def under(rel: str = "") -> Path:
    """The path under the root for a module-level constant; unset, it is a relative placeholder that does not exist."""
    return _base() / rel


def _base() -> Path:
    return root() or Path("RomHacking")


def needs(*files: tuple):
    """A skip marker for a test that reads each file under the root; ``files`` are tuples of path parts."""
    reason = next((r for r in (missing(*parts) for parts in files) if r), None)
    return pytest.mark.skipif(reason is not None, reason=reason or "")
