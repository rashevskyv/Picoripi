"""Project actions: the Project Manager window, and the registry and string counts it reads."""
from functools import partial
from typing import Optional

from core.project_library import index, registry
from ui.project_manager.jobs import BackgroundJob
from ui.project_manager.window import ProjectManagerDialog
from utils import constants
from utils.logging_utils import log_debug


def _touch(reg: registry.Registry, path: str, project_id: str) -> None:
    reg.touch_opened(path, project_id=project_id)


def _library_dir() -> str:
    # Read at call time: tests point SETTINGS_DIR at a temporary folder.
    return str(constants.SETTINGS_DIR)


class LibraryMixin:
    def open_project_manager_action(self) -> None:
        """Show the Project Manager. One window is kept; it reloads its list each time it is shown."""
        dialog: Optional[ProjectManagerDialog] = getattr(self.mw, "project_manager_dialog", None)
        if dialog is None:
            dialog = ProjectManagerDialog(self.mw, _library_dir(), self._open_from_manager,
                                          self.create_new_project_action)
            self.mw.project_manager_dialog = dialog
        else:
            dialog.reload()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def open_project_manager_if_none(self) -> None:
        """At start-up: show the Project Manager when no project is open."""
        project_manager = getattr(self.mw, "project_manager", None)
        if project_manager is not None and project_manager.project is not None:
            return
        self.open_project_manager_action()

    def _open_from_manager(self, project_file: str) -> None:
        self._open_recent_project(project_file)

    def note_project_opened(self, project_file: str) -> None:
        """Record in the registry that a project was opened now. Adds the project when it is new."""
        project_manager = getattr(self.mw, "project_manager", None)
        project = getattr(project_manager, "project", None)
        project_id = getattr(project, "id", "") or ""
        job = BackgroundJob(registry.mutate, _library_dir(), partial(_touch, path=project_file, project_id=project_id))
        job.start()

    def record_project_counts(self) -> None:
        """Store the line and translation counts of the open project, counted on a worker thread.

        The lists are copied here (cheap pointer copies) so the worker never reads a list the UI is changing.
        """
        project_manager = getattr(self.mw, "project_manager", None)
        store = getattr(self.mw, "data_store", None)
        if project_manager is None or project_manager.project_file_path is None or store is None or not store.data:
            return
        key = registry.project_key(project_manager.project_file_path)
        original = [list(block) if isinstance(block, list) else block for block in store.data]
        translated = [list(block) if isinstance(block, list) else block for block in store.edited_file_data or []]
        edited = dict(store.edited_data or {})
        log_debug(f"Counting strings of project {key} on a worker thread.")
        BackgroundJob(index.record_counts, _library_dir(), key, original, translated, edited).start()
