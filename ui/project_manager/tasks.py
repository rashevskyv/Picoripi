"""Worker jobs of the Project Manager's new-project wizard and of its rows: plugin facts, unpacking, string counts,
and build, export or run. Each job runs its plugin code on its own thread and reports through signals only.

Every job takes ``load_rules`` (a plugin name -> ``GameRules``). The window passes the real loader; tests pass a fake.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal

from core.project_library import build, console_keys, plugin_facts, resources
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

    def __init__(self, plugin_name: str, sources: Dict[str, str], project_dir: str, load_rules: LoadRules,
                 key_paths: Optional[Dict[str, str]] = None, existing_translation: str = ""):
        super().__init__()
        self._plugin = plugin_name
        self._sources = dict(sources)
        self._project_dir = project_dir
        self._load_rules = load_rules
        self._key_paths = dict(key_paths or {})   # console id -> key file path the user chose in the wizard
        self._existing_translation = existing_translation  # a folder the user chose: no folder is made here

    def run(self) -> None:
        try:
            for console, path in self._key_paths.items():
                console_keys.set_path(console, path)
            rules = self._load_rules(self._plugin)
            folder = build.run_unpack(rules, self._sources, self._project_dir, self._report,
                                      self.isInterruptionRequested, key_provider=console_keys.path_for)
            if not self._existing_translation:
                # Made only when the project keeps its own folder, so a refused create leaves no empty folder.
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


def _resource_project(project_file: str) -> Tuple[str, str]:
    """``(plugin, source)`` of a project file: the source the project names, as it is (a folder, or one file, not its
    folder). An empty source means the project's folder."""
    path = Path(project_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("project file is not a JSON object")
    source = str((data.get("metadata") or {}).get("source_path") or "")
    if source and not Path(source).is_absolute():
        source = str(path.parent / source)
    return str(data.get("plugin_name") or ""), source or str(path.parent)


class ResourceJob(WorkerThread):
    """Counts the texts, fonts, textures and other files of one project's source folder. The walk stops on cancel.

    The game's ``classify_resource`` hook names a file's kind first when the plugin has one; a plugin that fails or
    is not installed leaves the extension rule in place.
    """

    done = pyqtSignal(dict)  # {kind: {"files", "bytes"}}; not emitted when cancelled
    failed = pyqtSignal(str)

    def __init__(self, project_file: str, load_rules: LoadRules):
        super().__init__()
        self._project_file = project_file
        self._load_rules = load_rules

    def run(self) -> None:
        try:
            plugin, source = _resource_project(self._project_file)
            counts = resources.count_resources(source, self.isInterruptionRequested, self._classifier(plugin))
        except Exception as exc:  # a project that cannot be read shows a line in its row, not an error box
            log_warning(f"Resources of {self._project_file} not counted: {exc}")
            self.failed.emit(str(exc))
            return
        if counts is not None:
            self.done.emit(counts)

    def _classifier(self, plugin: str) -> Optional[Callable[[str], Optional[str]]]:
        """The plugin's ``classify_resource`` as a function of a path, or None when the plugin cannot give one."""
        if not plugin:
            return None
        try:
            rules = self._load_rules(plugin)
        except Exception as exc:  # a missing or broken plugin: the extension rule counts its files
            log_warning(f"Plugin {plugin} not loaded for its file kinds: {exc}")
            return None
        hook = getattr(rules, "classify_resource", None)
        if hook is None:
            return None

        def classify(path: str) -> Optional[str]:
            try:
                return hook(path)
            except Exception as exc:  # a plugin's bug falls back to the extension for that file
                log_warning(f"classify_resource failed for {path}: {exc}")
                return None
        return classify
