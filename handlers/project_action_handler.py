"""Compatibility shim: implementation lives in handlers.project_action.*."""
from __future__ import annotations

# Re-exported for callers/tests that patch symbols on this module path.
# QMessageBox / QFileDialog class-attribute patches apply to the shared class object.
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from core.project_manager import ProjectManager
from core.data_manager import load_json_file

from handlers.project_action import ProjectActionHandler, ProjectLoadWorker


__all__ = [
    "ProjectActionHandler",
    "ProjectLoadWorker",
    "ProjectManager",
    "QMessageBox",
    "QFileDialog",
    "Path",
    "load_json_file",
]
