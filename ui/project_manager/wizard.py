"""The new-project wizard of the Project Manager: game, files with roles and platform, location, then unpack and create.

The plugin reads the files on a worker. Unpacking runs on a worker with progress and cancel; only a finished
project reaches ``on_create``, which creates it through the shared project-creation path.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.i18n import tr
from core.project_library import images
from core.project_library.icons import IMAGE_FILTER, load_image
from ui.project_manager.jobs import BackgroundJob
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
        self._key_status: Dict[str, Dict[str, Any]] = {}   # per file path: the console its key file is for, and ready
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
        self._icon_path = ""
        icon_row = QHBoxLayout()
        self._icon_preview = QLabel()
        self._icon_preview.setFixedSize(64, 64)
        self._icon_preview.setToolTip(tr("Optional. Shown in the Project Manager list."))
        browse_icon = QPushButton(tr("Browse..."))
        browse_icon.clicked.connect(self._browse_icon)
        clear_icon = QPushButton(tr("Clear icon"))
        clear_icon.clicked.connect(self._clear_icon)
        icon_row.addWidget(self._icon_preview)
        icon_row.addWidget(browse_icon)
        icon_row.addWidget(clear_icon)
        icon_row.addStretch(1)
        form.addRow(tr("Icon (optional)"), icon_row)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    # ----- icon -----
    def _browse_icon(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, tr("Choose an icon"), str(Path.home()), tr("Images") + f" ({IMAGE_FILTER});;" + tr("All files") + " (*)")
        if path:
            self.set_icon(path)

    def set_icon(self, path: str) -> None:
        """Remember the picture for the project. Its preview is decoded on a worker; a non-picture is refused."""
        self._icon_path = path
        self._run(BackgroundJob(load_image, Path(path)), partial(self._on_icon_preview, path))

    def _on_icon_preview(self, path: str, image: Optional[QImage]) -> None:
        if path != self._icon_path:
            return  # the user picked another picture meanwhile
        if image is None:
            self._icon_path = ""
            self._icon_preview.clear()
            QMessageBox.warning(self, tr("New project"), tr("This file is not a picture."))
            return
        self._icon_preview.setPixmap(QPixmap.fromImage(
            image.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))

    def _clear_icon(self) -> None:
        self._icon_path = ""
        self._icon_preview.clear()

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
        self._use_existing = QCheckBox(tr("Use an existing translation folder"))
        self._use_existing.setToolTip(tr("The project reads its translations from this folder. Picoripi does not "
                                         "create the missing files in it."))
        self._use_existing.toggled.connect(self._existing_toggled)
        layout.addWidget(self._use_existing)
        existing_row = QHBoxLayout()
        self._existing_folder = QLineEdit()
        self._existing_folder.setPlaceholderText(tr("Choose the translation folder"))
        self._existing_folder.setEnabled(False)
        self._existing_folder.textChanged.connect(self._update_summary)
        self._browse_existing_button = QPushButton(tr("Browse..."))
        self._browse_existing_button.setEnabled(False)
        self._browse_existing_button.clicked.connect(self._browse_existing)
        existing_row.addWidget(self._existing_folder, 1)
        existing_row.addWidget(self._browse_existing_button)
        layout.addLayout(existing_row)
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
        self._key_status = {}
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
        self._key_status = identities
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

    def _existing_toggled(self, checked: bool) -> None:
        self._existing_folder.setEnabled(checked)
        self._browse_existing_button.setEnabled(checked)
        self._update_summary()

    def _browse_existing(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("Existing translation folder"), str(Path.home()))
        if folder:
            self._existing_folder.setText(folder)

    def _existing_translation(self) -> str:
        """The chosen existing translation folder, or "" when the project makes its own."""
        return self._existing_folder.text().strip() if self._use_existing.isChecked() else ""

    def _update_summary(self, *_args: Any) -> None:
        folder = self._folder.text().strip()
        if not folder:
            self._summary.setText(tr("Choose the project folder."))
            return
        root = Path(folder)
        existing = self._existing_translation()
        if self._use_existing.isChecked() and not existing:
            translation = tr("Translation files: choose the existing translation folder.")
        elif existing:
            translation = tr("Translation files: {0} (already there; not changed)", existing)
        else:
            translation = tr("Translation files: {0} (created now)", str(root / TRANSLATION_FOLDER))
        self._summary.setText("\n".join([
            tr("Project file: {0}", str(root / PROJECT_FILE_NAME)),
            tr("Unpacked files: {0} (only when the game needs unpacking)", str(root / "unpacked")),
            translation,
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
        key_paths = self._ask_key_files(choices)
        if key_paths is None:
            return
        self._set_busy(True)
        self._progress.setValue(0)
        self._progress_text.setText(tr("Unpacking..."))
        job = UnpackJob(self._game.currentData(), sources, folder, self._load_rules, key_paths,
                        existing_translation=self._existing_translation())
        job.progress.connect(self._on_progress)
        job.cancelled.connect(self._on_unpack_cancelled)
        job.done.connect(lambda unpacked, s=sources, c=choices: self._on_unpacked(unpacked, s, c))
        job.failed.connect(self._on_unpack_failed)
        job.failed.connect(lambda _message, j=job: self._finish_job(j))
        job.cancelled.connect(lambda j=job: self._finish_job(j))
        self._unpack_job = job
        self._run(job, lambda _result: self._finish_job(job))

    def _ask_key_files(self, choices: Dict[str, Dict[str, str]]) -> Optional[Dict[str, str]]:
        """The key file of each console that a chosen file needs and Picoripi has no live path for.

        Asks only for files that have a role. A library the file's unpack loads (``libraries``, e.g. Oodle) is asked
        the same way when Picoripi has no path for it. Returns ``{console: path}``, or None when the user cancels a dialog.
        """
        needed: List[str] = []
        for path, choice in choices.items():
            status = self._key_status.get(path) or {}
            console = str(status.get("key") or "")
            if choice["role"] and console and not status.get("key_ready") and console not in needed:
                needed.append(console)
            if choice["role"]:   # readiness of the libraries was read with the file, on the worker
                ready = set(status.get("libraries_ready") or [])
                for library in status.get("libraries") or []:
                    if library not in needed and library not in ready:
                        needed.append(library)
        picked: Dict[str, str] = {}
        for console in needed:
            label = tr(images.CONSOLE_LABEL[console])
            title = (tr("Choose the Oodle library file (oo2core or oo2ext DLL)") if console == "oodle"
                     else tr("Choose the key file for {0}", label))
            path, _filter = QFileDialog.getOpenFileName(
                self, title, str(Path.home()), tr("All files") + " (*)")
            if not path:
                self._progress_text.setText(tr("No key file was chosen. Nothing was created."))
                return None
            picked[console] = path
        return picked

    def _problem(self) -> str:
        if not self._name.text().strip():
            return tr("Give the project a name.")
        if not self._folder.text().strip():
            return tr("Choose the project folder.")
        if (Path(self._folder.text().strip()) / PROJECT_FILE_NAME).exists():
            return tr("This folder already holds a project.")
        if self._use_existing.isChecked():
            existing = self._existing_translation()
            if not existing:
                return tr("Choose the existing translation folder.")
            if not Path(existing).is_dir():
                return tr("The translation folder does not exist.")
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
        existing = self._existing_translation()
        if existing and not is_directory:
            # A project of one file has a translation file, not a folder: nothing is created.
            self._progress_text.setText(tr("This game is one file, so it cannot use an existing translation folder. "
                                           "Uncheck that option and create the project again."))
            return
        translation = existing or str(folder / TRANSLATION_FOLDER)
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
            "auto_create_translations": not existing,
            "platform": platform,
            "icon_source": self._icon_path,
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
