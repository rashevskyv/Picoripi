"""The list of recently opened projects."""
from pathlib import Path
from typing import Any
from utils.logging_utils import log_debug

class RecentProjectsManager:
    """Manager class for recent projects."""
    def __init__(self, main_window: Any):
        """Initialize a new instance."""
        self.mw = main_window

    def _names(self) -> dict:
        """Project names by path, so the menu shows the game, not the folder (often 'picoripi')."""
        if not isinstance(getattr(self.mw, 'recent_projects_names', None), dict):
            self.mw.recent_projects_names = {}
        return self.mw.recent_projects_names

    def add_recent_project(self, project_path: str, max_recent: int = 10, name: str = "") -> None:
        """Add a project to the recent projects list."""
        if not hasattr(self.mw, 'recent_projects'):
            self.mw.recent_projects = []

        # Normalize path
        project_path = str(Path(project_path).resolve())

        # Remove if already in list
        if project_path in self.mw.recent_projects:
            self.mw.recent_projects.remove(project_path)

        # Add to beginning
        self.mw.recent_projects.insert(0, project_path)

        # Limit to max_recent
        self.mw.recent_projects = self.mw.recent_projects[:max_recent]
        names = self._names()
        if name:
            names[project_path] = name
        for path in [p for p in names if p not in self.mw.recent_projects]:
            del names[path]
        log_debug(f"Added '{project_path}' to recent projects")

    def remove_recent_project(self, project_path: str) -> None:
        """Remove a project from the recent projects list."""
        if not hasattr(self.mw, 'recent_projects'):
            return

        project_path = str(Path(project_path).resolve())
        self._names().pop(project_path, None)
        if project_path in self.mw.recent_projects:
            self.mw.recent_projects.remove(project_path)
            log_debug(f"Removed '{project_path}' from recent projects")

    def clear_recent_projects(self) -> None:
        """Clear all recent projects."""
        self.mw.recent_projects = []
        self.mw.recent_projects_names = {}
        log_debug("Cleared all recent projects")
