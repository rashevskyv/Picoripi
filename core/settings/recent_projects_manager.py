from pathlib import Path
from typing import Any, List
from utils.logging_utils import log_debug

class RecentProjectsManager:
    def __init__(self, main_window: Any):
        self.mw = main_window

    def add_recent_project(self, project_path: str, max_recent: int = 10) -> None:
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
        log_debug(f"Added '{project_path}' to recent projects")

    def remove_recent_project(self, project_path: str) -> None:
        """Remove a project from the recent projects list."""
        if not hasattr(self.mw, 'recent_projects'):
            return

        project_path = str(Path(project_path).resolve())
        if project_path in self.mw.recent_projects:
            self.mw.recent_projects.remove(project_path)
            log_debug(f"Removed '{project_path}' from recent projects")

    def clear_recent_projects(self) -> None:
        """Clear all recent projects."""
        self.mw.recent_projects = []
        log_debug("Cleared all recent projects")
