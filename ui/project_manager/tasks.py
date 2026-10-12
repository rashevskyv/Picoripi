"""Worker jobs of the Project Manager's new-project wizard and of its rows: plugin facts, unpacking, string counts,
and build, export or run. Each job runs its plugin code on its own thread and reports through signals only.

Every job takes ``load_rules`` (a plugin name -> ``GameRules``). The window passes the real loader; tests pass a fake.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal

from core.project_library import build, index, plugin_facts
from utils.constants import plugins_root
from utils.logging_utils import log_error, log_warning
from utils.thread_utils import WorkerThread

LoadRules = Callable[[str], Any]


def plugin_choices() -> List[Tuple[str, str]]:
    """``(display name, plugin folder)`` of every installed plugin, sorted by display name. Reads config files."""
    choices = []
    root = plugins_root()
    if not root.is_dir():
        return choices
    for folder in root.iterdir():
        config = folder / "config.json"
        if not folder.is_dir() or not config.is_file():
            continue
        try:
            display = json.loads(config.read_text(encoding="utf-8")).get("display_name") or folder.name
        except (OSError, ValueError) as exc:
            log_warning(f"Plugin config not read for {folder.name}: {exc}")
            display = folder.name
        choices.append((str(display), folder.name))
    return sorted(choices, key=lambda item: item[0].casefold())


class PluginListJob(WorkerThread):
    """The installed plugins, read on a worker so the wizard opens without disk work on the UI thread."""

    done = pyqtSignal(list)
    failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            choices = plugin_choices()
        except OSError as exc:
            self.failed.emit(str(exc))
            return
        self.done.emit(choices)


class FactsJob(WorkerThread):
    """Roles, platforms and the role and platform of each picked file, as the plugin reads them."""

    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, plugin_name: str, paths: List[str], load_rules: LoadRules):
        super().__init__()
        self._plugin = plugin_name
        self._paths = list(paths)
        self._load_rules = load_rules

    def run(self) -> None:
        try:
            rules = self._load_rules(self._plugin)
            result = {
                "roles": plugin_facts.roles_of(rules),
                "platforms": plugin_facts.platforms_of(rules),
                "identities": plugin_facts.identify_sources(rules, self._paths, self.isInterruptionRequested),
            }
        except Exception as exc:  # a plugin's failure is shown in the wizard; the user can still pick by hand
            log_error(f"Project wizard could not read plugin {self._plugin}: {exc}", exc_info=True)
            self.failed.emit(str(exc))
            return
        self.done.emit(result)


class UnpackJob(WorkerThread):
    """Unpacks the role files of a new project. Cancelling removes the job's own temporary folder only."""

    progress = pyqtSignal(int, str)
    done = pyqtSignal(object)  # the unpacked folder, or None when the files need no unpacking
    cancelled = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, plugin_name: str, sources: Dict[str, str], project_dir: str, load_rules: LoadRules):
        super().__init__()
        self._plugin = plugin_name
        self._sources = dict(sources)
        self._project_dir = project_dir
        self._load_rules = load_rules

    def run(self) -> None:
        try:
            rules = self._load_rules(self._plugin)
            folder = build.run_unpack(rules, self._sources, self._project_dir, self._report,
                                      self.isInterruptionRequested)
            Path(self._project_dir, "translation").mkdir(parents=True, exist_ok=True)
        except build.Cancel:
            self.cancelled.emit()
            return
        except Exception as exc:
            log_error(f"Unpacking {self._project_dir} failed: {exc}", exc_info=True)
            self.failed.emit(str(exc))
            return
        self.done.emit(folder)

    def _report(self, percent: int, text: str) -> None:
        self.progress.emit(int(percent), str(text))


def _project_paths(project_file: str) -> Tuple[str, str, str]:
    """``(plugin, source folder, translation folder)`` of a project file. Read on a worker."""
    path = Path(project_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("project file is not a JSON object")
    metadata = data.get("metadata") or {}
    source = str(metadata.get("source_path") or "")
    if source and not Path(source).is_absolute():
        source = str(path.parent / source)
    if source and Path(source).is_file():
        source = str(Path(source).parent)
    translation = str(metadata.get("translation_path") or "")
    if translation and not Path(translation).is_absolute():
        translation = str(path.parent / translation)
    if not translation:
        translation = str(path.parent / "translation")
    return str(data.get("plugin_name") or ""), source or str(path.parent), translation


class CountJob(WorkerThread):
    """Counts the lines of projects that have no counts yet, with each plugin's parser, one project at a time.

    Each result is emitted as soon as it is ready and stored in the index at the end. Cancelling keeps what was done.
    A project whose counting fails gets ``count_error`` instead, and is not retried until its file changes.
    """

    counted = pyqtSignal(str, dict)
    done = pyqtSignal(int)
    failed = pyqtSignal(str)

    def __init__(self, directory: str, targets: List[Tuple[str, str]], load_rules: LoadRules):
        super().__init__()
        self._directory = directory
        self._targets = list(targets)
        self._load_rules = load_rules

    def run(self) -> None:
        updates: Dict[str, Dict[str, Any]] = {}
        for key, project_file in self._targets:
            if self.isInterruptionRequested():
                break
            fields = self._count(project_file)
            if fields is None:
                break
            updates[key] = fields
            self.counted.emit(key, fields)
        try:
            index.merge(self._directory, updates)
        except OSError as exc:
            log_error(f"Could not save the counts to the project index: {exc}")
            self.failed.emit(str(exc))
            return
        self.done.emit(len(updates))

    def _count(self, project_file: str) -> Optional[Dict[str, Any]]:
        try:
            mtime = os.stat(project_file).st_mtime_ns
        except OSError as exc:
            return {"count_error": str(exc), "counted_mtime": 0, "counted_at": index.stamp()}
        try:
            result = plugin_facts.count_project(project_file, self._load_rules, self.isInterruptionRequested)
        except Exception as exc:  # one broken plugin or file must not stop the other projects
            log_warning(f"Could not count {project_file}: {exc}")
            return {"count_error": str(exc), "counted_mtime": mtime, "counted_at": index.stamp()}
        if result is None:
            return None
        return {"counts": result["counts"], "targets": result["targets"], "skipped": result["skipped"],
                "groups": result["groups"], "counted_mtime": mtime, "counted_at": index.stamp()}


class ActionJob(WorkerThread):
    """Builds one target of a project; with ``export_to`` it then copies the build to that folder.

    The plugin's build runs here, not on the UI thread. Cancel removes the temporary build folder only.
    """

    progress = pyqtSignal(int, str)
    done = pyqtSignal(str)
    cancelled = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, project_file: str, target_id: str, load_rules: LoadRules, export_to: str = ""):
        super().__init__()
        self._project_file = project_file
        self._target = target_id
        self._load_rules = load_rules
        self._export_to = export_to

    def run(self) -> None:
        try:
            plugin, source, translation = _project_paths(self._project_file)
            project_dir = str(Path(self._project_file).parent)
            rules = self._load_rules(plugin)
            result = build.run_build(rules, self._target, project_dir, source, translation, self._report,
                                     self.isInterruptionRequested)
            if self._export_to:
                result = build.export_build(result, self._export_to, self._report, self.isInterruptionRequested)
        except build.Cancel:
            self.cancelled.emit()
            return
        except Exception as exc:
            log_error(f"Build {self._target} of {self._project_file} failed: {exc}", exc_info=True)
            self.failed.emit(str(exc))
            return
        self.done.emit(result)

    def _report(self, percent: int, text: str) -> None:
        self.progress.emit(int(percent), str(text))
