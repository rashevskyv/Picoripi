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


__all__ = [
    "Category",
    "Block",
    "Project",
    "VirtualFolder",
    "ProjectManager",
    "Path",
    "ContainerManager",
]
