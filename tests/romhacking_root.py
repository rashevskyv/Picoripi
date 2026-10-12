"""The owner's RomHacking workspace, for the tests that read real game files.

Set ``PICORIPI_ROMHACKING`` to the workspace root (the folder that holds the game folders). Unset, or a file
missing under it, the test skips with the reason. The repository keeps no personal paths.
"""
import os
from pathlib import Path
from typing import Optional

import pytest

ENV = "PICORIPI_ROMHACKING"


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
    return root().joinpath(*parts)


def needs(*files: tuple):
    """A skip marker for a test that reads each file under the root; ``files`` are tuples of path parts."""
    reason = next((r for r in (missing(*parts) for parts in files) if r), None)
    return pytest.mark.skipif(reason is not None, reason=reason or "")
