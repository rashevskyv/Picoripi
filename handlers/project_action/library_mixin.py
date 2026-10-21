"""Project actions: the Project Manager window, its wizard, and the registry, counts and flags it reads and writes."""
from functools import partial
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtWidgets import QDialog

from core.project_library import flags, index, registry
from core.project_library.icons import save_user_icon
from core.project_library.scan import ICON_FILE_NAME
from core.project_library.plugin_facts import default_load_rules
from ui.project_manager.jobs import BackgroundJob
from ui.project_manager.window import ProjectManagerDialog
from ui.project_manager.wizard import ProjectWizard
from utils import constants
from utils.logging_utils import log_debug


def _touch(reg: registry.Registry, path: str, project_id: str, platform: str = "") -> None:
    reg.touch_opened(path, project_id=project_id)
    if platform:
        reg.update_fields(path, platform=platform)


def _library_dir() -> str:
    # Read at call time: tests point SETTINGS_DIR at a temporary folder.
    return str(constants.SETTINGS_DIR)


def _same_file(first: str, second: str) -> bool:
    return registry.project_key(first) == registry.project_key(second)


class LibraryMixin:
    def open_project_manager_action(self) -> None:
        """Show the Project Manager. One window is kept; it reloads its list each time it is shown."""
        dialog: Optional[ProjectManagerDialog] = getattr(self.mw, "project_manager_dialog", None)
        if dialog is None:
            dialog = ProjectManagerDialog(self.mw, _library_dir(), self._open_from_manager,
                                          self.open_new_project_wizard, self.save_project_flags,
                                          self.save_project_manager_setting, on_closed=self._project_manager_closed)
            self.mw.project_manager_dialog = dialog
        else:
            dialog.reload()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _project_manager_closed(self) -> None:
        """The user closed the Project Manager. With no project open, nothing is left to show: quit as File > Exit does."""
        project_manager = getattr(self.mw, "project_manager", None)
        if project_manager is not None and project_manager.project is not None:
            return
        self.mw.close()

    def open_project_manager_if_none(self) -> None:
        """At start-up: show the Project Manager when no project is open."""
        project_manager = getattr(self.mw, "project_manager", None)
        if project_manager is not None and project_manager.project is not None:
            return
        self.open_project_manager_action()

    def open_new_project_wizard(self) -> bool:
        """The Project Manager's new-project wizard. It creates the project through the shared creation path.

        True when the wizard made a project (it is opening in the main window)."""
        wizard = ProjectWizard(self.mw, default_load_rules, self.finish_new_project)
        return wizard.exec() == QDialog.DialogCode.Accepted.value

    def _open_from_manager(self, project_file: str) -> None:
        self._open_recent_project(project_file)

    def note_project_opened(self, project_file: str, platform: str = "") -> None:
        """Record in the registry that a project was opened now. Adds the project when it is new."""
        project_manager = getattr(self.mw, "project_manager", None)
        project = getattr(project_manager, "project", None)
        project_id = getattr(project, "id", "") or ""
        job = BackgroundJob(registry.mutate, _library_dir(),
                            partial(_touch, path=project_file, project_id=project_id, platform=platform))
        job.start()

    def save_project_flags(self, project_file: str, updates: Dict[str, bool]) -> None:
        """Store the user's flags of a project. An open project saves them with its own file; others on a worker."""
        project_manager = getattr(self.mw, "project_manager", None)
        project = getattr(project_manager, "project", None)
        open_file = getattr(project_manager, "project_file_path", None)
        if project is not None and open_file and _same_file(open_file, project_file):
            stored = dict(project.metadata.get("flags") or {})
            stored.update(updates)
            project.metadata["flags"] = {name: bool(value) for name, value in stored.items()
                                         if name in flags.FLAG_NAMES}
            project_manager.save()
            return
        BackgroundJob(flags.set_flags, project_file, updates).start()

    def copy_project_icon(self, directory: str, source: str) -> None:
        """Copy a picture the user chose in the wizard to the new project's icon.png, scaled, on a worker."""
        BackgroundJob(save_user_icon, Path(source), Path(directory) / ICON_FILE_NAME).start()

    def save_project_manager_setting(self, name: str, value: str) -> None:
        """Store one Project Manager setting (for example the emulator command) on a worker."""
        BackgroundJob(registry.mutate, _library_dir(), partial(_set_setting, name=name, value=value)).start()

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
        BackgroundJob(index.record_counts, _library_dir(), key, original, translated, edited,
                      project_manager.project_file_path).start()


def _set_setting(reg: registry.Registry, name: str, value: str) -> None:
    reg.set_setting(name, value)
