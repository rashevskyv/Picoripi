"""The new-project wizard of the Project Manager: game, files with roles and platform, location, then unpack and create.

The plugin reads the files on a worker. Each file's role (base game, update, DLC) and platform come from its own
header when the plugin does not say; the files step tells at once what blocks a create (a repeated role, a file this
game cannot read, a missing key file). Unpacking runs on a worker with progress and cancel; only a finished project
reaches ``on_create``, which creates it through the shared project-creation path. The project's icon is not asked
here: the Project Manager's row has Change icon.
"""
from __future__ import annotations

from collections import Counter
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QCompleter, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QStackedWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from core.i18n import tr
from core.project_library import build, images, plugin_facts
from ui.project_manager.tasks import FactsJob, PluginListJob, UnpackJob
from utils.logging_utils import log_info
from utils.thread_utils import safe_shutdown_thread

PROJECT_FILE_NAME = "project.uiproj"
TRANSLATION_FOLDER = "translation"
FILE_COLUMN, ROLE_COLUMN, PLATFORM_COLUMN, STATUS_COLUMN = 0, 1, 2, 3
NOT_SET = ""
TOUCHED = Qt.ItemDataRole.UserRole + 1     # True once the user picked the row's role or platform by hand
SOURCE_FOLDER = Qt.ItemDataRole.UserRole + 2   # True for an extracted game folder (checked for readable text on the worker)
PROBLEM_COLOR = QColor("#c0392b")
WARNING_COLOR = QColor("#b9770e")


class ProjectWizard(QDialog):
    """Four steps in one dialog: Game, Files, Location, and the summary with the unpack progress."""

    def __init__(self, parent, load_rules: Callable[[str], Any], on_create: Callable[[Dict[str, Any]], None]):
        super().__init__(parent)
        self.setWindowTitle(tr("New project"))
        self.resize(980, 560)
        self._load_rules = load_rules
        self._on_create = on_create
        self._jobs: List[Any] = []
        self._roles: List[Dict[str, Any]] = []
        self._platforms: List[Dict[str, str]] = []
        self._unpack_job: Optional[UnpackJob] = None
        self._entries_before: Optional[List[str]] = None   # the project folder's names before a create
        self._key_status: Dict[str, Dict[str, Any]] = {}   # per file path: what the plugin and the header say
        self._picked_keys: Dict[str, str] = {}             # console -> key file the user chose in this wizard
        self._retry_console = ""                          # the console whose key file failed at unpack
        self._name_typed = False                           # the user typed a project name: a new game keeps it
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
        self._game.setEditable(True)        # type a part of the name to find the game in a long list
        self._game.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._game.lineEdit().setPlaceholderText(tr("Type a part of the game's name"))
        self._game.currentIndexChanged.connect(self._game_changed)
        form.addRow(tr("Game"), self._game)
        self._name = QLineEdit()
        self._name.setPlaceholderText(tr("The game's name is filled in; change it if you like"))
        self._name.textEdited.connect(self._name_edited)
        form.addRow(tr("Project name"), self._name)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _files_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel(tr("Step 2 of 3: the files. Add the game, its update and its DLC: files or unpacked folders. "
                          "Picoripi reads each file and sets its role and platform; you can change them. Select "
                          "several rows to give them one role. The originals stay where they are."))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        bar = QHBoxLayout()
        add = QPushButton(tr("Add files..."))
        add.clicked.connect(self._add_files)
        add_folder = QPushButton(tr("Add folder..."))
        add_folder.setToolTip(tr("An unpacked game: a folder with the game's files."))
        add_folder.clicked.connect(self._add_folder)
        remove = QPushButton(tr("Remove selected"))
        remove.clicked.connect(self._remove_selected)
        bar.addWidget(add)
        bar.addWidget(add_folder)
        bar.addWidget(remove)
        bar.addStretch(1)
        bar.addWidget(QLabel(tr("Role for the selected files:")))
        self._batch_role = QComboBox()
        self._batch_role.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        bar.addWidget(self._batch_role)
        self._apply_role = QPushButton(tr("Apply"))
        self._apply_role.clicked.connect(self._apply_batch_role)
        bar.addWidget(self._apply_role)
        layout.addLayout(bar)

        self._files_tree = QTreeWidget()
        self._files_tree.setHeaderLabels([tr("File"), tr("Role"), tr("Platform"), tr("Status")])
        self._files_tree.setRootIsDecorated(False)
        self._files_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._files_tree.itemSelectionChanged.connect(self._selection_changed)
        header = self._files_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(FILE_COLUMN, QHeaderView.ResizeMode.Stretch)
        for column in (ROLE_COLUMN, PLATFORM_COLUMN, STATUS_COLUMN):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._files_tree, 1)

        self._files_status = QLabel("")
        layout.addWidget(self._files_status)
        self._files_problems = QLabel("")
        self._files_problems.setWordWrap(True)
        self._files_problems.setStyleSheet(f"color: {PROBLEM_COLOR.name()};")
        layout.addWidget(self._files_problems)
        self._key_bar = QHBoxLayout()
        layout.addLayout(self._key_bar)
        self._selection_changed()
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
        self._progress_text.setWordWrap(True)
        layout.addWidget(self._progress_text)
        self._add_key = QPushButton(tr("Add key file..."))
        self._add_key.setVisible(False)
        self._add_key.clicked.connect(self._replace_key_file)
        layout.addWidget(self._add_key)
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
        """The plugin list arrived. No game is chosen yet: the user picks one, then its name fills the project name."""
        self._game.blockSignals(True)
        for display, folder in choices:
            self._game.addItem(display, folder)
        self._game.setCurrentIndex(-1)
        self._game.blockSignals(False)
        completer = QCompleter(self._game.model(), self._game)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._game.setCompleter(completer)

    def _name_edited(self, text: str) -> None:
        self._name_typed = bool(text.strip())

    def _game_changed(self, *_args: Any) -> None:
        """A new game: its name fills the project name, its roles and platforms replace the old ones. The files stay."""
        if not self._name_typed and self._game.currentIndex() >= 0:
            self._name.setText(self._game.currentText())
        for position in range(self._files_tree.topLevelItemCount()):
            self._files_tree.topLevelItem(position).setData(0, TOUCHED, False)
        self._roles, self._platforms = [], []
        self._key_status = {}
        self._picked_keys = {}
        self._add_key.setVisible(False)
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
        self._fill_batch_roles()
        for position in range(self._files_tree.topLevelItemCount()):
            item = self._files_tree.topLevelItem(position)
            identity = identities.get(item.data(0, Qt.ItemDataRole.UserRole)) or {}
            if not item.data(0, TOUCHED):  # the user has not picked a role yet
                self._set_combo(item, ROLE_COLUMN, self._roles, identity.get("role") or self._roles[0]["id"])
                self._set_combo(item, PLATFORM_COLUMN, self._platform_choices(), identity.get("platform") or NOT_SET)
        self._refresh_files_state()

    # ----- files -----
    def _paths(self) -> List[str]:
        return [self._files_tree.topLevelItem(p).data(0, Qt.ItemDataRole.UserRole)
                for p in range(self._files_tree.topLevelItemCount())]

    def _add_files(self) -> None:
        names, _filter = QFileDialog.getOpenFileNames(self, tr("Add game files"), str(Path.home()),
                                                      tr("All files") + " (*)")
        self.add_paths(names)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("Add an unpacked game folder"), str(Path.home()))
        if folder:
            self.add_paths([folder], source_folder=True)

    def add_paths(self, names: List[str], source_folder: bool = False) -> None:
        """Add files or folders to the list; the plugin reads the new ones (and the rest again) on a worker."""
        known = set(self._paths())
        for name in names:
            if name in known:
                continue
            # A folder is often named "source" or "romfs": its parents tell which game and platform it is.
            shown = str(Path(*Path(name).parts[-3:])) if source_folder else Path(name).name
            item = QTreeWidgetItem([shown, "", "", ""])
            item.setToolTip(FILE_COLUMN, name)
            item.setData(0, Qt.ItemDataRole.UserRole, name)
            item.setData(0, TOUCHED, False)
            item.setData(0, SOURCE_FOLDER, source_folder)
            self._files_tree.addTopLevelItem(item)
            self._set_combo(item, ROLE_COLUMN, self._roles, self._roles[0]["id"] if self._roles else NOT_SET)
            self._set_combo(item, PLATFORM_COLUMN, self._platform_choices(), NOT_SET)
        if names:
            self._refresh_files_state()
            self._reread_files()

    def _source_folder(self) -> str:
        """The extracted game folder on the list, or "" when the project is made from game files."""
        for position in range(self._files_tree.topLevelItemCount()):
            item = self._files_tree.topLevelItem(position)
            if item.data(0, SOURCE_FOLDER):
                return item.data(0, Qt.ItemDataRole.UserRole)
        return ""

    def _remove_selected(self) -> None:
        for item in self._files_tree.selectedItems():
            self._files_tree.takeTopLevelItem(self._files_tree.indexOfTopLevelItem(item))
        self._refresh_files_state()

    def _platform_choices(self) -> List[Dict[str, str]]:
        """The plugin's platforms, plus every platform a file's header named that the plugin does not list."""
        choices = list(self._platforms)
        known = {choice["id"] for choice in choices}
        for identity in self._key_status.values():
            platform = str(identity.get("platform") or "")
            if platform and platform not in known:
                choices.append({"id": platform, "label": plugin_facts.platform_label(platform)})
                known.add(platform)
        return choices

    def _set_combo(self, item: QTreeWidgetItem, column: int, choices: List[Dict[str, str]], value: str) -> None:
        combo = QComboBox()
        if column == PLATFORM_COLUMN:
            combo.addItem(tr("Not detected"), NOT_SET)
        for choice in choices:
            combo.addItem(choice["label"], choice["id"])
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))
        combo.currentIndexChanged.connect(partial(self._combo_changed, item))
        self._files_tree.setItemWidget(item, column, combo)

    def _combo_changed(self, item: QTreeWidgetItem, _index: int) -> None:
        item.setData(0, TOUCHED, True)
        self._refresh_files_state()

    def _fill_batch_roles(self) -> None:
        current = self._batch_role.currentData()
        self._batch_role.clear()
        for role in self._roles:
            self._batch_role.addItem(role["label"], role["id"])
        self._batch_role.setCurrentIndex(max(0, self._batch_role.findData(current)))
        self._selection_changed()

    def _selection_changed(self) -> None:
        self._apply_role.setEnabled(bool(self._files_tree.selectedItems()) and self._batch_role.count() > 0)

    def _apply_batch_role(self) -> None:
        """Give every selected file the role chosen beside the Apply button (for example 90 DLC files at once)."""
        role = self._batch_role.currentData()
        for item in self._files_tree.selectedItems():
            combo = self._files_tree.itemWidget(item, ROLE_COLUMN)
            if combo is not None:
                combo.setCurrentIndex(max(0, combo.findData(role)))
            item.setData(0, TOUCHED, True)
        self._refresh_files_state()

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

    def _key_ready(self, console: str, identity: Dict[str, Any]) -> bool:
        return bool(identity.get("key_ready")) or console in self._picked_keys

    def _file_problems(self, include_keys: bool = True) -> List[str]:
        """What stops a create in the file list, in words a user can act on. Empty when the files are fine.

        ``include_keys=False`` leaves out missing key files: Create asks for them itself (``_ask_key_files``).
        """
        problems: List[str] = []
        role_problem = self._role_problem()
        if role_problem:
            problems.append(role_problem)
        for path in self._paths():
            identity = self._key_status.get(path) or {}
            name = Path(path).name
            platform = plugin_facts.platform_label(str(identity.get("platform") or ""))
            if identity.get("status") == plugin_facts.STATUS_UNREADABLE:
                problems.append(tr("{0}: this game cannot read a {1} file itself. Remove it and add the unpacked "
                                   "folder of the game instead (Add folder...).", name, platform))
            console = str(identity.get("key") or "")
            if include_keys and console and not self._key_ready(console, identity):
                problems.append(tr("{0} is encrypted. Picoripi needs the key file for {1} to read it. Add the key "
                                   "file, or remove the file and add the unpacked folder instead.",
                                   name, tr(images.CONSOLE_LABEL[console])))
        return problems

    def _role_problem(self) -> str:
        choices = self._file_choices()
        roles = [choice["role"] for choice in choices.values()]
        if "" in roles:
            return tr("Give every file a role.")
        labels = {role["id"]: role["label"] for role in self._roles}
        multiple = {role["id"] for role in self._roles if role.get("multiple")}
        repeated = [role for role, count in Counter(roles).items() if count > 1 and role not in multiple]
        if repeated:
            return tr("Two files have the role {0}. Only DLC can repeat: give each other file its own role.",
                      labels.get(repeated[0], repeated[0]))
        return ""

    def _refresh_files_state(self) -> None:
        """Status column, the problem text, the key buttons and the Next button, from the current list."""
        for position in range(self._files_tree.topLevelItemCount()):
            item = self._files_tree.topLevelItem(position)
            text, color = self._status_text(self._key_status.get(item.data(0, Qt.ItemDataRole.UserRole)) or {})
            item.setText(STATUS_COLUMN, text)
            item.setForeground(STATUS_COLUMN, color if color is not None else self.palette().text().color())
        self._files_status.setText(tr("Files: {0}", self._files_tree.topLevelItemCount()))
        problems = self._file_problems()
        self._files_problems.setText("\n".join(problems))
        self._rebuild_key_buttons()
        self._next.setEnabled(self._pages.currentIndex() != 1 or not problems)

    def _status_text(self, identity: Dict[str, Any]) -> Tuple[str, Optional[QColor]]:
        status = identity.get("status")
        if status == plugin_facts.STATUS_UNREADABLE:
            return tr("Cannot read: add its folder"), PROBLEM_COLOR
        console = str(identity.get("key") or "")
        if console and not self._key_ready(console, identity):
            return tr("Needs the key file"), PROBLEM_COLOR
        if status == plugin_facts.STATUS_UNRECOGNISED:
            return tr("Not recognised by this game"), WARNING_COLOR
        if status == plugin_facts.STATUS_FOLDER:
            return tr("Folder"), None
        return (tr("Ready"), None) if identity else ("", None)

    def _missing_consoles(self) -> List[str]:
        missing: List[str] = []
        for path in self._paths():
            identity = self._key_status.get(path) or {}
            console = str(identity.get("key") or "")
            if console and not self._key_ready(console, identity) and console not in missing:
                missing.append(console)
        return missing

    def _rebuild_key_buttons(self) -> None:
        while self._key_bar.count():
            widget = self._key_bar.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        for console in self._missing_consoles():
            button = QPushButton(tr("Add the key file for {0}...", tr(images.CONSOLE_LABEL[console])))
            button.clicked.connect(partial(self._pick_key_file, console))
            self._key_bar.addWidget(button)
        self._key_bar.addStretch(1)

    def _pick_key_file(self, console: str) -> None:
        """Remember the key file the user chose; it is stored when the project is created."""
        path, _filter = QFileDialog.getOpenFileName(
            self, tr("Choose the key file for {0}", tr(images.CONSOLE_LABEL[console])), str(Path.home()),
            tr("All files") + " (*)")
        if path:
            self._picked_keys[console] = path
            self._refresh_files_state()

    # ----- navigation -----
    def _show_page(self, index: int) -> None:
        index = max(0, min(2, index))
        self._pages.setCurrentIndex(index)
        self._back.setEnabled(index > 0 and self._unpack_job is None)
        self._next.setVisible(index < 2)
        self._next.setEnabled(index != 1 or not self._file_problems())
        self._create.setVisible(index == 2)
        self._create.setEnabled(self._unpack_job is None)
        if index == 2:
            self._update_summary()

    def _next_clicked(self) -> None:
        index = self._pages.currentIndex()
        if index == 0 and self._game.currentIndex() < 0:
            QMessageBox.warning(self, tr("New project"), tr("Choose the game."))
            return
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
            (tr("Extracted game folder: {0}", self._source_folder()) if self._source_folder() else
             tr("Unpacked files: {0} (only when the game needs unpacking)", str(root / "unpacked"))),
            translation,
            tr("Originals: not copied; the project refers to them by path."),
        ]))

    # ----- create -----
    def _sources(self, choices: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        """``{role key: path}``; repeated DLC files are ``dlc``, ``dlc_2``, ``dlc_3``... (``plugin_facts.role_key``)."""
        sources: Dict[str, str] = {}
        seen: Counter = Counter()
        for path, choice in choices.items():
            seen[choice["role"]] += 1
            sources[plugin_facts.role_key(choice["role"], seen[choice["role"]])] = path
        return sources

    def _create_clicked(self) -> None:
        problem = self._problem()
        if problem:
            QMessageBox.warning(self, tr("New project"), problem)
            return
        choices = self._file_choices()
        sources = self._sources(choices)
        folder = self._folder.text().strip()
        key_paths = self._ask_key_files(choices)
        if key_paths is None:
            return
        self._entries_before = build.entries_before(folder)
        self._set_busy(True)
        self._add_key.setVisible(False)
        self._progress.setValue(0)
        self._progress_text.setText(tr("Unpacking..."))
        job = UnpackJob(self._game.currentData(), sources, folder, self._load_rules, key_paths,
                        existing_translation=self._existing_translation(), source_folder=self._source_folder())
        job.key_failed.connect(self._on_key_failed)
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

        Key files picked on the files step are used first. Asks only for files that have a role. A library the file's
        unpack loads (``libraries``, e.g. Oodle) is asked the same way when Picoripi has no path for it. Returns
        ``{console: path}``, or None when the user cancels a dialog.
        """
        needed: List[str] = []
        if self._source_folder():
            return {}
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
        picked: Dict[str, str] = dict(self._picked_keys)   # chosen on the files step or after a failed key
        for console in needed:
            if console in picked:
                continue
            label = tr(images.CONSOLE_LABEL[console])
            if console != "oodle":
                self._progress_text.setText(tr("The {0} image is encrypted and needs its key file.", label))
                self._retry_console = console
                self._add_key.setVisible(True)
            title = (tr("Choose the Oodle library file (oo2core or oo2ext DLL)") if console == "oodle"
                     else tr("Choose the key file for {0}", label))
            path, _filter = QFileDialog.getOpenFileName(
                self, title, str(Path.home()), tr("All files") + " (*)")
            if not path:
                self._progress_text.setText(tr("No key file was chosen. Nothing was created."))
                return None
            picked[console] = path
        return picked

    def _on_key_failed(self, console: str, _message: str) -> None:
        self._retry_console = console
        self._add_key.setVisible(True)

    def _replace_key_file(self) -> None:
        """The key file failed at unpack: choose another one and create again."""
        label = tr(images.CONSOLE_LABEL[self._retry_console])
        path, _filter = QFileDialog.getOpenFileName(
            self, tr("Choose the key file for {0}", label), str(Path.home()), tr("All files") + " (*)")
        if path:
            self._picked_keys[self._retry_console] = path
            self._create_clicked()

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
        if not self._file_choices():
            return tr("Add at least one file.")
        if self._source_folder() and len(self._file_choices()) != 1:
            return tr("Use one extracted game folder, or add game files. Remove the other sources.")
        problems = self._file_problems(include_keys=False)
        return problems[0] if problems else ""

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
        self._remove_made()
        self._progress_text.setText(tr("Unpacking was cancelled. Nothing was created."))

    def _on_unpack_failed(self, message: str) -> None:
        self._remove_made()
        self._progress_text.setText(tr("Unpacking failed: {0}", message))
        box = QMessageBox(QMessageBox.Icon.Warning, tr("New project"), tr("Unpacking failed: {0}", message),
                          QMessageBox.StandardButton.Ok, self)
        box.open()   # not exec(): the wizard keeps running, and the text stays under the summary too

    def _remove_made(self) -> None:
        """Remove what this create added to the folder: nothing stays after a failed or cancelled create."""
        build.remove_new_entries(self._folder.text().strip(), self._entries_before)

    def _on_unpacked(self, unpacked: Optional[str], sources: Dict[str, str], choices: Dict[str, Dict[str, str]]) -> None:
        """Unpacking is done (or not needed): the project is created from the folders the user chose."""
        folder = Path(self._folder.text().strip())
        base = sources.get("base") or next(iter(sources.values()))
        source = unpacked or base
        is_directory = Path(source).is_dir()
        existing = self._existing_translation()
        if existing and not is_directory:
            # A project of one file has a translation file, not a folder: nothing is created.
            self._remove_made()
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
            "entries_before": self._entries_before,
            "auto_create_translations": not existing,
            "platform": platform,
            "metadata": {
                "source_roles": {role: path for role, path in sources.items()},
                "platform": platform,
                "unpacked": bool(unpacked) and not bool(self._source_folder()),
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
