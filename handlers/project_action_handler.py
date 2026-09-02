"""Compatibility shim: implementation lives in handlers.project_action.*."""
from __future__ import annotations

# Re-exported for callers/tests that patch symbols on this module path.
# QMessageBox / QFileDialog class-attribute patches apply to the shared class object.
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from core.project_manager import ProjectManager
from core.data_manager import load_json_file

from handlers.project_action import ProjectActionHandler, ProjectLoadWorker
from handlers.project_action import load_worker as _load_worker
from handlers.project_action import handler as _handler
from handlers.project_action import lifecycle_mixin as _lifecycle_mixin
from handlers.project_action import blocks_mixin as _blocks_mixin
from handlers.project_action import session_mixin as _session_mixin
from handlers.project_action import recent_mixin as _recent_mixin


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


# Tests patch these on handlers.project_action_handler; mixins use them as globals.
# Full QMessageBox replacements (not class-attribute patches) also need late-bind.
_load_worker.Path = _ShimName("Path")
_load_worker.load_json_file = _ShimName("load_json_file")
_handler.ProjectManager = _ShimName("ProjectManager")
_lifecycle_mixin.ProjectManager = _ShimName("ProjectManager")
_lifecycle_mixin.Path = _ShimName("Path")
_lifecycle_mixin.QMessageBox = _ShimName("QMessageBox")
_blocks_mixin.Path = _ShimName("Path")
_blocks_mixin.QMessageBox = _ShimName("QMessageBox")
_recent_mixin.ProjectManager = _ShimName("ProjectManager")
_recent_mixin.Path = _ShimName("Path")
_recent_mixin.QMessageBox = _ShimName("QMessageBox")
_session_mixin.ProjectLoadWorker = _ShimName("ProjectLoadWorker")
_session_mixin.QMessageBox = _ShimName("QMessageBox")

__all__ = [
    "ProjectActionHandler",
    "ProjectLoadWorker",
    "ProjectManager",
    "QMessageBox",
    "QFileDialog",
    "Path",
    "load_json_file",
]
