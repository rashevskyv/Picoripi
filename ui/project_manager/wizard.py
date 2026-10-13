"""The new-project wizard of the Project Manager: game, files with roles and platform, location, then unpack and create.

The plugin reads the files on a worker. Unpacking runs on a worker with progress and cancel; only a finished
project reaches ``on_create``, which creates it through the shared project-creation path.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.i18n import tr
from ui.project_manager.tasks import FactsJob, PluginListJob, UnpackJob
from utils.logging_utils import log_info
from utils.thread_utils import safe_shutdown_thread

PROJECT_FILE_NAME = "project.uiproj"
TRANSLATION_FOLDER = "translation"
ROLE_COLUMN, PLATFORM_COLUMN = 1, 2
NOT_SET = ""


class ProjectWizard(QDialog):
    """Four steps in one dialog: Game, Files, Location, and the summary with the unpack progress."""

    def __init__(self, parent, load_rules: Callable[[str], Any], on_create: Callable[[Dict[str, Any]], None]):
        super().__init__(parent)
        self.setWindowTitle(tr("New project"))
        self.resize(820, 520)
        self._load_rules = load_rules
        self._on_create = on_create
        self._jobs: List[Any] = []
        self._roles: List[Dict[str, str]] = []
        self._platforms: List[Dict[str, str]] = []
        self._unpack_job: Optional[UnpackJob] = None
        self._build_ui()
        self._run(PluginListJob(), self._on_plugins)
        self._show_page(0)

    # ----- layout -----
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._pages = QStackedWidget()
        self._pages.addWidget(self._game_page())
        self._pages.addWidget(self._files_page())
        self._pages.addWidget(self._location_page())
        layout.addWidget(self._pages, 1)

        buttons = QHBoxLayout()
        self._back = QPushButton(tr("Back"))
        self._back.clicked.connect(lambda: self._show_page(self._pages.currentIndex() - 1))
        self._next = QPushButton(tr("Next"))
        self._next.clicked.connect(self._next_clicked)
        self._create = QPushButton(tr("Create project"))
        self._create.clicked.connect(self._create_clicked)
        self._cancel = QPushButton(tr("Cancel"))
        self._cancel.clicked.connect(self.reject)
        buttons.addWidget(self._back)
        buttons.addStretch(1)
        buttons.addWidget(self._next)
        buttons.addWidget(self._create)
        buttons.addWidget(self._cancel)
        layout.addLayout(buttons)

    def _game_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(tr("Step 1 of 3: the game. Picoripi reads the files with this game's plugin.")))
        form = QFormLayout()
        self._game = QComboBox()
        self._game.currentIndexChanged.connect(self._game_changed)
        form.addRow(tr("Game"), self._game)
        self._name = QLineEdit()
        form.addRow(tr("Project name"), self._name)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _files_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(tr("Step 2 of 3: the files. Each file gets a role. The plugin fills in the role "
                                   "and the platform from the file's content. The originals stay where they are.")))
        bar = QHBoxLayout()
        add = QPushButton(tr("Add files..."))
        add.clicked.connect(self._add_files)
        remove = QPushButton(tr("Remove selected"))
        remove.clicked.connect(self._remove_selected)
        bar.addWidget(add)
        bar.addWidget(remove)
        bar.addStretch(1)
        layout.addLayout(bar)
        self._files_tree = QTreeWidget()
        self._files_tree.setHeaderLabels([tr("File"), tr("Role"), tr("Platform")])
        self._files_tree.setRootIsDecorated(False)
        layout.addWidget(self._files_tree, 1)
        self._files_status = QLabel("")
        layout.addWidget(self._files_status)
        return page

    def _location_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(tr("Step 3 of 3: the location. The project folder holds the project file, the "
                                   "unpacked files and the translation. Choose it yourself.")))
        row = QHBoxLayout()
        self._folder = QLineEdit()
        self._folder.setPlaceholderText(tr("Choose a folder"))
        self._folder.textChanged.connect(self._update_summary)
        browse = QPushButton(tr("Browse..."))
        browse.clicked.connect(self._browse_folder)
        row.addWidget(self._folder, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._summary)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._progress_text = QLabel("")
        layout.addWidget(self._progress_text)
        self._cancel_unpack = QPushButton(tr("Cancel unpacking"))
        self._cancel_unpack.setVisible(False)
        self._cancel_unpack.clicked.connect(self._cancel_unpacking)
        layout.addWidget(self._cancel_unpack)
        layout.addStretch(1)
        return page

    # ----- jobs -----
    def _run(self, job: Any, on_done: Callable[[Any], None]) -> None:
        self._jobs.append(job)
        job.done.connect(on_done)
        job.done.connect(lambda _result, j=job: self._forget(j))
        job.failed.connect(self._on_failed)
        job.failed.connect(lambda _message, j=job: self._forget(j))
        job.start()

    def _forget(self, job: Any) -> None:
        if job in self._jobs:
            self._jobs.remove(job)

    def _on_failed(self, message: str) -> None:
        self._files_status.setText(tr("Something went wrong: {0}", message))

    def _on_plugins(self, choices: list) -> None:
        """The plugin list arrived. Files the user already added stay; they are read with the first game."""
        self._game.blockSignals(True)
        for display, folder in choices:
            self._game.addItem(display, folder)
        self._game.blockSignals(False)
        self._reread_files()

    def _game_changed(self, *_args: Any) -> None:
        """A new game: its roles and platforms replace the old ones. The files stay and are read again."""
        for position in range(self._files_tree.topLevelItemCount()):
            self._files_tree.topLevelItem(position).setData(0, Qt.ItemDataRole.UserRole + 1, False)
        self._roles, self._platforms = [], []
        self._reread_files()

    def _reread_files(self) -> None:
        """Run the plugin over every file on the list. Each file's role and platform are set when the answer comes."""
        paths = self._paths()
        plugin = self._game.currentData() or ""
        if not paths or not plugin:
            return
        self._files_status.setText(tr("Reading the files..."))
        self._run(FactsJob(plugin, paths, self._load_rules), self._on_facts)

    def _on_facts(self, facts: Dict[str, Any]) -> None:
        self._roles = facts.get("roles") or []
        self._platforms = facts.get("platforms") or []
        identities = {item["path"]: item for item in facts.get("identities") or []}
        for position in range(self._files_tree.topLevelItemCount()):
            item = self._files_tree.topLevelItem(position)
            path = item.data(0, Qt.ItemDataRole.UserRole)
            identity = identities.get(path) or {}
            if not item.data(0, Qt.ItemDataRole.UserRole + 1):  # the user has not picked a role yet
                self._set_combo(item, ROLE_COLUMN, self._roles, identity.get("role") or self._roles[0]["id"])
                self._set_combo(item, PLATFORM_COLUMN, self._platforms, identity.get("platform") or NOT_SET)
        self._files_status.setText(tr("Files: {0}", self._files_tree.topLevelItemCount()))

    # ----- files -----
    def _paths(self) -> List[str]:
        return [self._files_tree.topLevelItem(p).data(0, Qt.ItemDataRole.UserRole)
                for p in range(self._files_tree.topLevelItemCount())]

    def _add_files(self) -> None:
        names, _filter = QFileDialog.getOpenFileNames(self, tr("Add game files"), str(Path.home()),
                                                      tr("All files") + " (*)")
        self.add_paths(names)

    def add_paths(self, names: List[str]) -> None:
        """Add files to the list; the plugin reads the new ones (and the rest again) on a worker."""
        known = set(self._paths())
        for name in names:
            if name in known:
                continue
            item = QTreeWidgetItem([Path(name).name, "", ""])
            item.setToolTip(0, name)
            item.setData(0, Qt.ItemDataRole.UserRole, name)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
            self._files_tree.addTopLevelItem(item)
            self._set_combo(item, ROLE_COLUMN, self._roles, self._roles[0]["id"] if self._roles else NOT_SET)
            self._set_combo(item, PLATFORM_COLUMN, self._platforms, NOT_SET)
        if names:
            self._reread_files()

    def _remove_selected(self) -> None:
        for item in self._files_tree.selectedItems():
            self._files_tree.takeTopLevelItem(self._files_tree.indexOfTopLevelItem(item))

    def _set_combo(self, item: QTreeWidgetItem, column: int, choices: List[Dict[str, str]], value: str) -> None:
        combo = QComboBox()
        if column == PLATFORM_COLUMN:
            combo.addItem(tr("Not set"), NOT_SET)
        for choice in choices:
            combo.addItem(choice["label"], choice["id"])
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))
        combo.currentIndexChanged.connect(lambda _i, it=item: it.setData(0, Qt.ItemDataRole.UserRole + 1, True))
        self._files_tree.setItemWidget(item, column, combo)

    def _file_choices(self) -> Dict[str, Dict[str, str]]:
        """``{path: {"role", "platform"}}`` as the user left the file list."""
        result = {}
        for position in range(self._files_tree.topLevelItemCount()):
            item = self._files_tree.topLevelItem(position)
            path = item.data(0, Qt.ItemDataRole.UserRole)
            role_combo = self._files_tree.itemWidget(item, ROLE_COLUMN)
            platform_combo = self._files_tree.itemWidget(item, PLATFORM_COLUMN)
            result[path] = {"role": role_combo.currentData() or "" if role_combo else "",
                            "platform": platform_combo.currentData() or "" if platform_combo else ""}
        return result

    # ----- navigation -----
    def _show_page(self, index: int) -> None:
        index = max(0, min(2, index))
        self._pages.setCurrentIndex(index)
        self._back.setEnabled(index > 0 and self._unpack_job is None)
        self._next.setVisible(index < 2)
        self._create.setVisible(index == 2)
        self._create.setEnabled(self._unpack_job is None)
        if index == 2:
            self._update_summary()

    def _next_clicked(self) -> None:
        index = self._pages.currentIndex()
        if index == 0 and not self._name.text().strip():
            QMessageBox.warning(self, tr("New project"), tr("Give the project a name."))
            return
        if index == 1 and not self._paths():
            QMessageBox.warning(self, tr("New project"), tr("Add at least one file."))
            return
        self._show_page(index + 1)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("Project folder"), str(Path.home()))
        if folder:
            self._folder.setText(folder)

    def _update_summary(self, *_args: Any) -> None:
        folder = self._folder.text().strip()
        if not folder:
            self._summary.setText(tr("Choose the project folder."))
            return
        root = Path(folder)
        self._summary.setText("\n".join([
            tr("Project file: {0}", str(root / PROJECT_FILE_NAME)),
            tr("Unpacked files: {0} (only when the game needs unpacking)", str(root / "unpacked")),
            tr("Translation files: {0} (created now)", str(root / TRANSLATION_FOLDER)),
            tr("Originals: not copied; the project refers to them by path."),
        ]))

    # ----- create -----
    def _create_clicked(self) -> None:
        problem = self._problem()
        if problem:
            QMessageBox.warning(self, tr("New project"), problem)
            return
        choices = self._file_choices()
        sources = {choice["role"]: path for path, choice in choices.items()}
        folder = self._folder.text().strip()
        self._set_busy(True)
        self._progress.setValue(0)
        self._progress_text.setText(tr("Unpacking..."))
        job = UnpackJob(self._game.currentData(), sources, folder, self._load_rules)
        job.progress.connect(self._on_progress)
        job.cancelled.connect(self._on_unpack_cancelled)
        job.done.connect(lambda unpacked, s=sources, c=choices: self._on_unpacked(unpacked, s, c))
        job.failed.connect(self._on_unpack_failed)
        job.failed.connect(lambda _message, j=job: self._finish_job(j))
        job.cancelled.connect(lambda j=job: self._finish_job(j))
        self._unpack_job = job
        self._run(job, lambda _result: self._finish_job(job))

    def _problem(self) -> str:
        if not self._name.text().strip():
            return tr("Give the project a name.")
        if not self._folder.text().strip():
            return tr("Choose the project folder.")
        if (Path(self._folder.text().strip()) / PROJECT_FILE_NAME).exists():
            return tr("This folder already holds a project.")
        choices = self._file_choices()
        if not choices:
            return tr("Add at least one file.")
        roles = [choice["role"] for choice in choices.values()]
        if "" in roles:
            return tr("Give every file a role.")
        if len(set(roles)) != len(roles):
            return tr("Two files have the same role. Give each file its own role.")
        return ""

    def _set_busy(self, busy: bool) -> None:
        self._progress.setVisible(busy)
        self._cancel_unpack.setVisible(busy)
        self._create.setEnabled(not busy)
        self._back.setEnabled(not busy)

    def _finish_job(self, job: Any) -> None:
        if self._unpack_job is job:
            self._unpack_job = None
        self._set_busy(False)

    def _on_progress(self, percent: int, text: str) -> None:
        self._progress.setValue(max(0, min(100, percent)))
        self._progress_text.setText(text)

    def _cancel_unpacking(self) -> None:
        if self._unpack_job is not None:
            self._progress_text.setText(tr("Cancelling..."))
            self._unpack_job.requestInterruption()

    def _on_unpack_cancelled(self) -> None:
        self._progress_text.setText(tr("Unpacking was cancelled. Nothing was created."))

    def _on_unpack_failed(self, message: str) -> None:
        self._progress_text.setText(tr("Unpacking failed: {0}", message))

    def _on_unpacked(self, unpacked: Optional[str], sources: Dict[str, str], choices: Dict[str, Dict[str, str]]) -> None:
        """Unpacking is done (or not needed): the project is created from the folders the user chose."""
        folder = Path(self._folder.text().strip())
        base = sources.get("base") or next(iter(sources.values()))
        source = unpacked or base
        is_directory = Path(source).is_dir()
        translation = str(folder / TRANSLATION_FOLDER)
        if not is_directory:
            translation = str(folder / TRANSLATION_FOLDER / Path(source).name)
        platform = next((c["platform"] for c in choices.values() if c["platform"]), "")
        info = {
            "directory": str(folder),
            "name": self._name.text().strip(),
            "plugin": self._game.currentData() or "",
            "description": "",
            "source_path": source,
            "translation_path": translation,
            "is_directory_mode": is_directory,
            "auto_create_translations": True,
            "platform": platform,
            "metadata": {
                "source_roles": {role: path for role, path in sources.items()},
                "platform": platform,
                "unpacked": bool(unpacked),
            },
        }
        log_info(f"Wizard creates project {info['name']} in {folder} from {len(sources)} files.")
        self._on_create(info)
        self.accept()

    def reject(self) -> None:
        if self._unpack_job is not None:
            self._unpack_job.requestInterruption()
        super().reject()

    def closeEvent(self, event) -> None:
        for job in list(self._jobs):
            try:
                safe_shutdown_thread(job, None, 1000)
            except RuntimeError:  # Qt deleted a job that had already finished
                pass
        self._jobs.clear()
        super().closeEvent(event)
