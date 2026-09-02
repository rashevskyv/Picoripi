"""Compatibility barrel for project management helpers.

Implementation lives in ``core.project``; this module re-exports public names
with identity-preserving bindings so existing
``from core.project_manager import X`` imports keep working.
"""
from __future__ import annotations

from pathlib import Path

from core.containers import ContainerManager
from core.project_models import Category, Block, Project, VirtualFolder
from core.project.manager import ProjectManager
from core.project import persist_mixin as _persist_mixin
from core.project import blocks_mixin as _blocks_mixin
from core.project import folders_mixin as _folders_mixin


class _ShimName:
    """Late-bound name that always reads from this shim module."""

    __slots__ = ("_name",)

    def __init__(self, name: str):
        object.__setattr__(self, "_name", name)

    def _resolve(self):
        import sys
        return getattr(sys.modules[__name__], object.__getattribute__(self, "_name"))

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._resolve(), item)

    def __repr__(self):
        return repr(self._resolve())


# Tests patch Path / ContainerManager on core.project_manager; mixins use them as globals.
_persist_mixin.Path = _ShimName("Path")
_blocks_mixin.Path = _ShimName("Path")
_blocks_mixin.ContainerManager = _ShimName("ContainerManager")
_folders_mixin.Path = _ShimName("Path")

__all__ = [
    "Category",
    "Block",
    "Project",
    "VirtualFolder",
    "ProjectManager",
    "Path",
    "ContainerManager",
]
