"""The Project Manager window: the list of added projects, their folders, grouping, sorting and details."""
from __future__ import annotations

from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QProcess, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QMenu,
    QMessageBox, QPushButton, QStackedWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.i18n import tr
from core.project_library import index, registry, views
from core.project_library.build import emulator_argv
from core.project_library.cards import percent_translated, read_card
from core.project_library.discovery import find_projects, platform_from_parts
from core.project_library.flags import FLAG_NAMES, flags_of
from core.project_library.plugin_facts import default_load_rules
from ui.project_manager.jobs import BackgroundJob, CardScanJob
from ui.project_manager.tasks import ActionJob, CountJob
from utils.logging_utils import log_debug, log_info
from utils.thread_utils import safe_shutdown_thread, single_shot

KEY_ROLE = Qt.ItemDataRole.UserRole
KIND_ROLE = Qt.ItemDataRole.UserRole + 1
DETAIL_ROLE = Qt.ItemDataRole.UserRole + 2

GROUP_CHOICES = (
    ("folder", "By folder"), ("platform", "By platform"), ("readiness", "By readiness"),
    ("text", "By text amount"), ("none", "No grouping"),
)
SORT_CHOICES = (
    ("name", "Project name"), ("lines", "Lines"), ("platform", "Platform"), ("readiness", "Readiness"), ("modified", "Modified"),
)
ISSUE_TEXT = {
    "project_file_missing": "The project file was not found.",
    "unreadable": "The project file cannot be read.",
    "plugin_missing": "The game plugin of this project is not installed.",
    "source_missing": "The original files path does not exist.",
    "translation_missing": "The translation files path does not exist.",
}
FLAG_LABELS = {"built": "Built", "verified_in_game": "Verified in game"}
COLUMNS = ("Project name", "Platform", "Lines", "Blocks", "Translated", "Modified", "Flags")


# ----- registry operations, run on a worker thread by BackgroundJob -----
def _op_add(reg: registry.Registry, path: str, project_id: str, platform: str) -> None:
    reg.add(path, project_id=project_id, platform=platform)


def _op_remove(reg: registry.Registry, path: str) -> None:
    reg.remove(path)


def _op_set_name(reg: registry.Registry, path: str, name: str) -> None:
    reg.update_fields(path, name=name)


def _op_move(reg: registry.Registry, path: str, folder_id: Optional[str]) -> None:
    reg.update_fields(path, folder_id=folder_id)


def _op_set_platform(reg: registry.Registry, path: str, platform: str) -> None:
    reg.update_fields(path, platform=platform)


def _op_create_folder(reg: registry.Registry, name: str) -> None:
    reg.create_folder(name)


def _op_rename_folder(reg: registry.Registry, folder_id: str, name: str) -> None:
    reg.rename_folder(folder_id, name)


def _op_delete_folder(reg: registry.Registry, folder_id: str) -> None:
    reg.delete_folder(folder_id)


def _op_set_view(reg: registry.Registry, **choices: Any) -> None:
    reg.set_view(**choices)


def _op_import(reg: registry.Registry, items: List[Dict[str, Any]]) -> None:
    """Add the chosen projects. One folder per series name is created when it is missing."""
    folder_ids: Dict[str, str] = {}
    for folder in reg.document["folders"]:
        folder_ids.setdefault(folder["name"].casefold(), folder["id"])
    for item in items:
        series = item.get("series") or ""
        folder_id = None
        if series:
            folder_id = folder_ids.get(series.casefold())
            if folder_id is None:
                folder_id = reg.create_folder(series)
                folder_ids[series.casefold()] = folder_id
        reg.add(item["project_file"], project_id=item.get("project_id", ""), platform=item.get("platform", ""),
                folder_id=folder_id)


def _card_facts(project_file: str) -> tuple:
    """Project id and platform guess of a project added by hand. Raises ``ValueError`` when it is no project."""
    card = read_card(project_file)
    return card["project_id"], platform_from_parts([Path(project_file).parent.parent.name])


def _load_state(directory: str) -> tuple:
    """The registry document and the cached index entries."""
    return registry.read(directory), index.read(directory)


def _call(function: Callable[..., Any], *args: Any) -> Callable[..., None]:
    """A slot for a Qt signal. Qt passes extra arguments (``checked``); this slot drops them."""
    return lambda *_ignored: function(*args)


class ImportScanJob(BackgroundJob):
    """Searches a folder for projects. Cancelling it stops the walk between folders."""

    def __init__(self, root: str):
        super().__init__(lambda: None)
        self._root = root

    def run(self) -> None:
        try:
            found = find_projects(self._root, cancelled=self.isInterruptionRequested)
        except OSError as exc:
            self.failed.emit(str(exc))
            return
        self.done.emit(found)


def format_modified(value: str) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


class ProjectManagerDialog(QDialog):
    """The list of projects the user added. Opens the chosen project through the callbacks given by the handler.

    ``save_flags(project_file, updates)`` and ``save_setting(name, value)`` store the user's choices; the handler decides
    whether an open project or a worker writes them.
    """

    def __init__(self, parent, library_dir: str, open_project: Callable[[str], None],
                 new_project: Callable[[], None], save_flags: Callable[[str, Dict[str, bool]], None],
                 save_setting: Callable[[str, str], None],
                 load_rules: Callable[[str], Any] = default_load_rules):
        super().__init__(parent)
        self.setWindowTitle(tr("Project Manager"))
        self.resize(1100, 620)
        self._dir = library_dir
        self._open_project = open_project
        self._new_project = new_project
        self._save_flags = save_flags
        self._save_setting = save_setting
        self._load_rules = load_rules
        self._document: Dict[str, Any] = {"projects": [], "folders": [], "view": dict(registry.DEFAULT_VIEW),
                                          "settings": {}}
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._cards: Dict[str, Dict[str, Any]] = {}
        self._flag_state: Dict[str, Dict[str, bool]] = {}
        self._scanned: set = set()
        self._loaded = False
        self._render_scheduled = False
        self._jobs: List[Any] = []
        self._items: Dict[str, QTreeWidgetItem] = {}
        self._status_labels: Dict[str, QLabel] = {}
        self._action_text: Dict[str, str] = {}
        self._action_jobs: Dict[str, ActionJob] = {}
        self._count_job: Optional[CountJob] = None
        self._build_ui()
        self._run(BackgroundJob(_load_state, library_dir), self._on_state)
        self._status.setText(tr("Loading projects..."))

    def reload(self) -> None:
        """Read the registry and the cache again; the list may have changed while the window was hidden."""
        self._scanned = set()
        self._loaded = False
        self._status.setText(tr("Loading projects..."))
        self._run(BackgroundJob(_load_state, self._dir), self._on_state)

    # ----- layout -----
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self._add_button = QToolButton()
        self._add_button.setText("+")
        self._add_button.setToolTip(tr("Add a project"))
        self._add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self._add_button)
        menu.addAction(tr("New project..."), self._new_project_clicked)
        menu.addAction(tr("Add existing project..."), self._add_existing_clicked)
        menu.addAction(tr("Import projects from a folder..."), self._import_clicked)
        self._add_button.setMenu(menu)
        bar.addWidget(self._add_button)

        new_folder = QPushButton(tr("New folder..."))
        new_folder.clicked.connect(self._new_folder_clicked)
        bar.addWidget(new_folder)
        emulator = QPushButton(tr("Emulator..."))
        emulator.setToolTip(tr("The command that starts your emulator. Used by Run in emulator."))
        emulator.clicked.connect(self._emulator_clicked)
        bar.addWidget(emulator)
        bar.addStretch(1)

        self._group = QComboBox()
        for value, label in GROUP_CHOICES:
            self._group.addItem(tr(label), value)
        self._sort = QComboBox()
        for value, label in SORT_CHOICES:
            self._sort.addItem(tr(label), value)
        self._descending = QCheckBox(tr("Descending"))
        bar.addWidget(QLabel(tr("Group")))
        bar.addWidget(self._group)
        bar.addWidget(QLabel(tr("Sort")))
        bar.addWidget(self._sort)
        bar.addWidget(self._descending)
        layout.addLayout(bar)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([tr(column) for column in COLUMNS])
        self._tree.setColumnCount(len(COLUMNS))
        self._tree.setAlternatingRowColors(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._context_menu)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.itemExpanded.connect(self._on_expanded)
        self._tree.header().setStretchLastSection(True)

        self._empty = QWidget()
        empty_layout = QVBoxLayout(self._empty)
        empty_label = QLabel(tr("No projects yet. Press + to add a project."))
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch(1)
        empty_layout.addWidget(empty_label)
        empty_layout.addStretch(1)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._tree)
        self._stack.addWidget(self._empty)
        layout.addWidget(self._stack, 1)

        self._status = QLabel("")
        layout.addWidget(self._status)

        self._group.currentIndexChanged.connect(self._view_changed)
        self._sort.currentIndexChanged.connect(self._view_changed)
        self._descending.toggled.connect(self._view_changed)

    # ----- jobs -----
    def _run(self, job: BackgroundJob, on_done: Callable[[Any], None]) -> None:
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
        self._status.setText(tr("Something went wrong: {0}", message))

    def _on_state(self, state: tuple) -> None:
        self._document, self._entries = state
        self._loaded = True
        self._render()
        self._scan_cards()
        self._schedule_counts()

    def _scan_cards(self) -> None:
        targets = []
        for entry in self._document["projects"]:
            key = registry.project_key(entry["path"])
            cached = (self._entries.get(key) or {}).get("card")
            targets.append((key, entry["path"], cached))
        if not targets:
            return
        job = CardScanJob(self._dir, targets)
        job.card_ready.connect(self._on_card)
        job.done.connect(self._on_scan_done)
        self._run(job, lambda _count: None)
        self._status.setText(tr("Refreshing {0} projects...", len(targets)))

    def _on_card(self, key: str, card: Dict[str, Any]) -> None:
        self._cards[key] = card
        self._scanned.add(key)
        self._schedule_render()

    def _on_scan_done(self, scanned: int) -> None:
        self._status.setText(tr("{0} projects.", len(self._document["projects"])))
        self._schedule_counts()

    # ----- counts of projects never opened -----
    def _schedule_counts(self) -> None:
        """Count the projects whose counts are missing or older than their file. One count job runs at a time."""
        if self._count_job is not None:
            return
        targets = []
        for entry in self._document["projects"]:
            key = registry.project_key(entry["path"])
            cached = self._entries.get(key) or {}
            card = self._cards.get(key) or cached.get("card") or {}
            mtime = card.get("mtime_ns")
            if mtime is None or "unreadable" in card.get("issues", []) or card.get("missing"):
                continue
            if cached.get("counted_mtime") == mtime:
                continue
            targets.append((key, entry["path"]))
        if not targets:
            return
        job = CountJob(self._dir, targets, self._load_rules)
        self._count_job = job
        job.counted.connect(self._on_counted)
        job.failed.connect(lambda _message: self._on_count_done(0))
        self._run(job, self._on_count_done)
        self._status.setText(tr("Counting {0} projects...", len(targets)))

    def _on_counted(self, key: str, fields: Dict[str, Any]) -> None:
        entry = self._entries.setdefault(key, {})
        entry.pop("count_error", None)
        entry.update(fields)
        self._schedule_render()

    def _on_count_done(self, _counted: int) -> None:
        self._count_job = None
        self._status.setText(tr("{0} projects.", len(self._document["projects"])))

    # ----- rendering -----
    def _schedule_render(self) -> None:
        """Rebuild the list soon. Several card results in a row become one rebuild."""
        if self._render_scheduled:
            return
        self._render_scheduled = True

        def fire() -> None:
            self._render_scheduled = False
            self._render()

        single_shot(150, self, fire)

    def _rows(self) -> List[Dict[str, Any]]:
        rows = []
        for entry in self._document["projects"]:
            path = entry["path"]
            key = registry.project_key(path)
            cached = self._entries.get(key) or {}
            card = self._cards.get(key) or cached.get("card") or {}
            counts = cached.get("counts")
            rows.append({
                "key": key,
                "path": path,
                "name": entry.get("name") or card.get("name") or Path(path).parent.name,
                "folder_id": entry.get("folder_id") or "",
                "platform": entry.get("platform") or "",
                "lines": counts.get("lines") if counts else None,
                "translated": percent_translated(counts) if counts else None,
                "blocks": card.get("blocks"),
                "modified": card.get("modified", ""),
                "issues": list(card.get("issues", [])),
                "last_opened": entry.get("last_opened") or "",
                "added": entry.get("added") or "",
                "plugin": card.get("plugin", ""),
                "refreshing": key not in self._scanned,
                "targets": list(cached.get("targets") or []),
                "groups": dict(cached.get("groups") or {}),
                "skipped": int(cached.get("skipped") or 0),
                "count_error": str(cached.get("count_error") or ""),
                "counted_at": cached.get("counted_at") or "",
                "flags": self._flag_state.get(key) or card.get("flags") or flags_of({}),
            })
        return rows

    def _render(self) -> None:
        expanded = {key for key, item in self._items.items() if item.isExpanded()}
        view = self._document.get("view", {})
        self._sync_controls(view)
        rows = self._rows()
        last = max((row for row in rows if row["last_opened"]), key=lambda r: r["last_opened"], default=None)
        folder_names = {folder["id"]: folder["name"] for folder in self._document["folders"]}
        sections = views.arrange(rows, view, folder_names, last["key"] if last else None)

        self._tree.clear()
        self._items = {}
        self._status_labels = {}  # the labels die with the tree; the texts stay in self._action_text
        self._stack.setCurrentWidget(self._tree if rows else self._empty)
        for kind, value, group_rows in sections:
            header = QTreeWidgetItem(self._tree, [f"{self._section_title(kind, value, folder_names)}  ({len(group_rows)})"])
            header.setFirstColumnSpanned(True)
            header.setData(0, KIND_ROLE, (kind, value))
            header.setExpanded(True)
            font = header.font(0)
            font.setBold(True)
            header.setFont(0, font)
            for row in group_rows:
                item = QTreeWidgetItem(header, self._cells(row))
                item.setData(0, KEY_ROLE, row["key"])
                item.setData(0, KIND_ROLE, ("project", row["path"]))
                detail = QTreeWidgetItem(item)
                detail.setFirstColumnSpanned(True)
                detail.setData(0, DETAIL_ROLE, row["key"])
                self._items[row["key"]] = item
                if row["key"] in expanded:
                    item.setExpanded(True)
                    self._on_expanded(item)
        self._tree.resizeColumnToContents(0)

    def _sync_controls(self, view: Dict[str, Any]) -> None:
        for combo, value in ((self._group, view.get("group_by")), (self._sort, view.get("sort_by"))):
            index = combo.findData(value)
            if index >= 0 and index != combo.currentIndex():
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)
        self._descending.blockSignals(True)
        self._descending.setChecked(bool(view.get("descending")))
        self._descending.blockSignals(False)

    @staticmethod
    def _section_title(kind: str, value: str, folder_names: Dict[str, str]) -> str:
        if kind == "last":
            return tr("Last opened")
        if kind == "folder":
            return folder_names.get(value) or tr("No folder")
        if kind == "platform":
            return value or tr("No platform")
        if kind == "readiness":
            return {"not_started": tr("Not started"), "in_progress": tr("In progress"),
                    "done": tr("Done"), "unknown": tr("Unknown")}[value]
        if kind == "text":
            return {"small": tr("Small"), "medium": tr("Medium"), "large": tr("Large"),
                    "unknown": tr("Unknown")}[value]
        return tr("All projects")

    @staticmethod
    def _cells(row: Dict[str, Any]) -> List[str]:
        flags = []
        if row["refreshing"]:
            flags.append(tr("refreshing..."))
        if "project_file_missing" in row["issues"]:
            flags.append(tr("Missing"))
        elif "unreadable" in row["issues"]:
            flags.append(tr("Unreadable"))
        elif not row["refreshing"]:
            flags.append(tr("Opens"))
        if row["issues"] and "project_file_missing" not in row["issues"] and "unreadable" not in row["issues"]:
            flags.append(tr("Needs attention"))
        for name in FLAG_NAMES:
            if row["flags"].get(name):
                flags.append(tr(FLAG_LABELS[name]))
        translated = "—" if row["translated"] is None else f"{row['translated']} %"
        return [
            row["name"],
            row["platform"] or "—",
            "—" if row["lines"] is None else f"{row['lines']:,}",
            "—" if row["blocks"] is None else str(row["blocks"]),
            translated,
            format_modified(row["modified"]),
            ", ".join(flags) or "—",
        ]

    # ----- selection helpers -----
    def _project_row(self, item: Optional[QTreeWidgetItem]) -> Optional[Dict[str, Any]]:
        if item is None:
            return None
        data = item.data(0, KIND_ROLE)
        if not data or data[0] != "project":
            return None
        key = item.data(0, KEY_ROLE)
        for row in self._rows():
            if row["key"] == key:
                return row
        return None

    def _folder_of(self, item: Optional[QTreeWidgetItem]) -> Optional[tuple]:
        if item is None:
            return None
        data = item.data(0, KIND_ROLE)
        if data and data[0] == "folder" and data[1][0] == "folder" and data[1][1]:
            return data[1][1]
        return None

    def _on_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        row = self._project_row(item)
        if row:
            self._open(row["path"])

    def _open(self, path: str) -> None:
        log_info(f"Project manager: opening {path}")
        self._open_project(path)
        self.close()

    # ----- details -----
    def _on_expanded(self, item: QTreeWidgetItem) -> None:
        if item.childCount() == 0:
            return
        detail = item.child(0)
        if detail.data(0, DETAIL_ROLE) is None or self._tree.itemWidget(detail, 0) is not None:
            return
        row = self._project_row(item)
        if row:
            self._tree.setItemWidget(detail, 0, self._detail_widget(row))

    def _detail_widget(self, row: Dict[str, Any]) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        path_label = QLabel(row["path"])
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        form = QFormLayout()
        form.addRow(tr("Platform"), QLabel(row["platform"] or "—"))
        form.addRow(tr("Plugin"), QLabel(row["plugin"] or "—"))
        form.addRow(tr("Lines"), QLabel("—" if row["lines"] is None else f"{row['lines']:,}"))
        form.addRow(tr("Translated"), QLabel("—" if row["translated"] is None else f"{row['translated']} %"))
        form.addRow(tr("Blocks"), QLabel("—" if row["blocks"] is None else str(row["blocks"])))
        form.addRow(tr("Modified"), QLabel(format_modified(row["modified"])))
        form.addRow(tr("Added"), QLabel(format_modified(row["added"])))
        form.addRow(tr("Last opened"), QLabel(format_modified(row["last_opened"])))
        form.addRow(tr("Counted"), QLabel(format_modified(row["counted_at"])))
        layout.addLayout(form)

        if row["groups"]:
            tree = QTreeWidget()
            tree.setHeaderLabels([tr("Folder"), tr("Blocks"), tr("Lines")])
            for name in sorted(row["groups"], key=str.casefold):
                group = row["groups"][name]
                tree.addTopLevelItem(QTreeWidgetItem([name, str(group["blocks"]), f"{group['lines']:,}"]))
            tree.setMaximumHeight(150)
            layout.addWidget(tree)

        attention = [tr(ISSUE_TEXT[issue]) for issue in row["issues"] if issue in ISSUE_TEXT]
        if row["count_error"]:
            attention.append(tr("The lines could not be counted: {0}.", row["count_error"]))
        if row["skipped"]:
            attention.append(tr("{0} blocks are not counted yet (archive members or missing files).", row["skipped"]))
        layout.addWidget(QLabel(tr("Needs attention:") + " " + (" ".join(attention) if attention
                                                              else tr("Nothing."))))

        flag_row = QHBoxLayout()
        for name in FLAG_NAMES:
            check = QCheckBox(tr(FLAG_LABELS[name]))
            check.setChecked(bool(row["flags"].get(name)))
            check.toggled.connect(partial(self._flag_toggled, row["path"], row["key"], name))
            flag_row.addWidget(check)
        flag_row.addStretch(1)
        layout.addLayout(flag_row)

        buttons = QHBoxLayout()
        open_button = QPushButton(tr("Open"))
        open_button.clicked.connect(_call(self._open, row["path"]))
        buttons.addWidget(open_button)
        reveal = QPushButton(tr("Show in folder"))
        reveal.clicked.connect(_call(self._reveal, row["path"]))
        buttons.addWidget(reveal)
        remove = QPushButton(tr("Remove from manager"))
        remove.clicked.connect(_call(self._remove_clicked, row))
        buttons.addWidget(remove)
        buttons.addWidget(self._action_button("Build mod", "build", row))
        buttons.addWidget(self._action_button("Export mod", "export", row))
        buttons.addWidget(self._action_button("Run in emulator", "run", row))
        buttons.addStretch(1)
        layout.addLayout(buttons)

        status = QLabel(self._action_text.get(row["key"], ""))
        status.setWordWrap(True)
        layout.addWidget(status)
        self._status_labels[row["key"]] = status
        return widget

    def _action_button(self, label: str, mode: str, row: Dict[str, Any]) -> QToolButton:
        """A button that lists the plugin's build targets. Off when the game declares none."""
        button = QToolButton()
        button.setText(tr(label))
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        for target in row["targets"]:
            action = menu.addAction(str(target["label"]))
            action.triggered.connect(_call(self._start_action, row["path"], target["id"], mode))
        button.setMenu(menu)
        if not row["targets"]:
            button.setEnabled(False)
            button.setToolTip(tr("This game declares no build target yet."))
        elif mode == "run" and not self._emulator_command():
            button.setEnabled(False)
            button.setToolTip(tr("Set the emulator command first (Emulator... button)."))
        return button

    @staticmethod
    def _reveal(path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def _flag_toggled(self, path: str, key: str, name: str, checked: bool) -> None:
        state = dict(self._flag_state.get(key) or {})
        state[name] = bool(checked)
        self._flag_state[key] = state
        self._save_flags(path, {name: bool(checked)})

    # ----- build, export and run -----
    def _emulator_command(self) -> str:
        return str((self._document.get("settings") or {}).get("emulator_command") or "").strip()

    def _emulator_clicked(self) -> None:
        text, ok = QInputDialog.getText(
            self, tr("Emulator command"),
            tr("Command that starts your emulator. Write {path} where the built file or folder goes."),
            text=self._emulator_command())
        if ok:
            value = text.strip()
            self._document.setdefault("settings", {})["emulator_command"] = value
            self._save_setting("emulator_command", value)

    def _start_action(self, project_file: str, target_id: str, mode: str) -> None:
        key = registry.project_key(project_file)
        if key in self._action_jobs:
            self._status.setText(tr("This project is already building."))
            return
        export_to = ""
        if mode == "export":
            export_to = QFileDialog.getExistingDirectory(self, tr("Export mod to folder"), str(Path.home()))
            if not export_to:
                return
        job = ActionJob(project_file, target_id, self._load_rules, export_to)
        self._action_jobs[key] = job
        self._set_action_text(key, tr("Working..."))
        job.progress.connect(lambda percent, text, k=key: self._set_action_text(k, f"{text} ({percent} %)"))
        job.done.connect(lambda path, k=key, m=mode: self._on_action_done(k, m, path))
        job.cancelled.connect(lambda k=key: self._on_action_ended(k, tr("Cancelled.")))
        job.failed.connect(lambda message, k=key: self._on_action_ended(k, tr("Failed: {0}", message)))
        self._run(job, lambda _path: None)

    def _on_action_done(self, key: str, mode: str, path: str) -> None:
        self._action_jobs.pop(key, None)
        if mode == "run":
            self._set_action_text(key, self._launch_emulator(path))
        elif mode == "export":
            self._set_action_text(key, tr("Exported to {0}", path))
        else:
            self._set_action_text(key, tr("Built: {0}", path))

    def _on_action_ended(self, key: str, text: str) -> None:
        self._action_jobs.pop(key, None)
        self._set_action_text(key, text)

    def _set_action_text(self, key: str, text: str) -> None:
        self._action_text[key] = text
        label = self._status_labels.get(key)
        if label is not None:
            label.setText(text)

    def _launch_emulator(self, path: str) -> str:
        """Start the emulator detached, with the path as argument. No shell is used."""
        argv = emulator_argv(self._emulator_command(), path)
        if not argv:
            return tr("Set the emulator command first (Emulator... button).")
        started, _pid = QProcess.startDetached(argv[0], argv[1:])
        if not started:
            return tr("The emulator did not start: {0}", argv[0])
        log_info(f"Started the emulator {argv[0]} with {path}.")
        return tr("Started the emulator with {0}", path)

    # ----- context menu and actions -----
    def _context_menu(self, position) -> None:
        item = self._tree.itemAt(position)
        menu = QMenu(self)
        row = self._project_row(item)
        folder = self._folder_of(item)
        if row:
            self._menu_item(menu, tr("Open"), self._open, row["path"])
            self._menu_item(menu, tr("Show in folder"), self._reveal, row["path"])
            menu.addSeparator()
            self._menu_item(menu, tr("Rename..."), self._rename_clicked, row)
            self._menu_item(menu, tr("Move to folder..."), self._move_clicked, row)
            self._menu_item(menu, tr("Remove from manager"), self._remove_clicked, row)
        elif folder:
            self._menu_item(menu, tr("Rename folder..."), self._rename_folder_clicked, folder)
            self._menu_item(menu, tr("Delete folder..."), self._delete_folder_clicked, folder)
        else:
            return
        menu.exec(self._tree.viewport().mapToGlobal(position))

    @staticmethod
    def _menu_item(menu: QMenu, text: str, function: Callable[..., None], *args: Any) -> None:
        action = menu.addAction(text)
        action.triggered.connect(_call(function, *args))

    def _rename_clicked(self, row: Dict[str, Any]) -> None:
        text, ok = QInputDialog.getText(self, tr("Rename project"), tr("Display name (empty = the project name):"),
                                        text=row["name"])
        if ok:
            self._mutate(partial(_op_set_name, path=row["path"], name=text.strip()))

    def _move_clicked(self, row: Dict[str, Any]) -> None:
        folders = [(tr("No folder"), "")] + [(folder["name"], folder["id"]) for folder in self._document["folders"]]
        labels = [label for label, _ in folders]
        current = next((i for i, (_, fid) in enumerate(folders) if fid == row["folder_id"]), 0)
        choice, ok = QInputDialog.getItem(self, tr("Move to folder"), tr("Folder:"), labels, current, False)
        if ok:
            folder_id = folders[labels.index(choice)][1]
            self._mutate(partial(_op_move, path=row["path"], folder_id=folder_id or None))

    def _remove_clicked(self, row: Dict[str, Any]) -> None:
        answer = QMessageBox.question(
            self, tr("Remove from manager"),
            tr("Remove this project from the Project Manager?\n\nNo project file is deleted."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._mutate(partial(_op_remove, path=row["path"]))

    def _new_folder_clicked(self) -> None:
        text, ok = QInputDialog.getText(self, tr("New folder"), tr("Folder name:"))
        if ok and text.strip():
            self._mutate(partial(_op_create_folder, name=text.strip()))

    def _rename_folder_clicked(self, folder_id: str) -> None:
        current = next((f["name"] for f in self._document["folders"] if f["id"] == folder_id), "")
        text, ok = QInputDialog.getText(self, tr("Rename folder"), tr("Folder name:"), text=current)
        if ok and text.strip():
            self._mutate(partial(_op_rename_folder, folder_id=folder_id, name=text.strip()))

    def _delete_folder_clicked(self, folder_id: str) -> None:
        answer = QMessageBox.question(
            self, tr("Delete folder"),
            tr("Delete this folder? Its projects move to the top level. No project file is deleted."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._mutate(partial(_op_delete_folder, folder_id=folder_id))

    def _view_changed(self, *_args: Any) -> None:
        choices = {"group_by": self._group.currentData(), "sort_by": self._sort.currentData(),
                   "descending": self._descending.isChecked()}
        self._document["view"] = {**self._document.get("view", {}), **choices}
        self._render()
        self._mutate(partial(_op_set_view, **choices))

    def _mutate(self, operation: Callable[..., Any]) -> None:
        if not self._loaded:
            return
        self._run(BackgroundJob(registry.mutate, self._dir, operation), self._on_document)

    def _on_document(self, document: Dict[str, Any]) -> None:
        self._document = document
        self._schedule_render()

    # ----- adding projects -----
    def _new_project_clicked(self) -> None:
        self._new_project()

    def _add_existing_clicked(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, tr("Add existing project"), str(Path.home()),
                                                    tr("Project files") + " (*.uiproj);;" + tr("All files") + " (*)")
        if not path:
            return
        job = BackgroundJob(_card_facts, path)
        job.done.connect(lambda facts, p=path: self._mutate(partial(_op_add, path=p, project_id=facts[0],
                                                                   platform=facts[1])))
        job.failed.connect(lambda _m: QMessageBox.warning(
            self, tr("Add existing project"), tr("This file is not a readable project.")))
        self._run(job, lambda _facts: None)

    def _import_clicked(self) -> None:
        root = QFileDialog.getExistingDirectory(self, tr("Import projects from a folder"), str(Path.home()))
        if not root:
            return
        self._status.setText(tr("Searching for projects..."))
        job = ImportScanJob(root)
        job.done.connect(self._import_found)
        job.failed.connect(lambda message: self._status.setText(tr("Search failed: {0}", message)))
        self._run(job, lambda _found: None)

    def _import_found(self, found: List[Dict[str, Any]]) -> None:
        known = {registry.project_key(p["path"]) for p in self._document["projects"]}
        candidates = []
        for item in found:
            item = dict(item)
            item["known"] = registry.project_key(item["project_file"]) in known
            candidates.append(item)
        self._status.setText(tr("{0} projects found.", len(candidates)))
        if not candidates:
            QMessageBox.information(self, tr("Import projects from a folder"), tr("No projects were found."))
            return
        dialog = ImportDialog(self, candidates)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.chosen():
            self._mutate(partial(_op_import, items=dialog.chosen()))

    def closeEvent(self, event) -> None:
        for job in list(self._jobs):
            try:
                safe_shutdown_thread(job, None, 1000)
            except RuntimeError as exc:  # Qt deleted a job that had already finished
                log_debug(f"Project manager job was already gone at close: {exc}")
        self._jobs.clear()
        self._action_jobs.clear()
        self._count_job = None
        super().closeEvent(event)


class ImportDialog(QDialog):
    """A checklist of the projects found in a folder. Duplicates, unreadable and known projects start unchecked."""

    def __init__(self, parent, candidates: List[Dict[str, Any]]):
        super().__init__(parent)
        self.setWindowTitle(tr("Import projects from a folder"))
        self.resize(900, 500)
        layout = QVBoxLayout(self)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([tr("Import"), tr("Series"), tr("Project name"), tr("Platform"), tr("Blocks"),
                                    tr("Note"), tr("Path")])
        self._candidates = candidates
        for candidate in candidates:
            note = []
            if candidate.get("error"):
                note.append(tr("Cannot be read"))
            if candidate.get("duplicate"):
                note.append(tr("Same project id as another found project"))
            if candidate.get("known"):
                note.append(tr("Already in the manager"))
            item = QTreeWidgetItem(self._tree, ["", candidate.get("series", ""), candidate.get("name", ""),
                                                candidate.get("platform") or "—",
                                                str(candidate.get("blocks", 0)), "; ".join(note),
                                                candidate["project_file"]])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = not (candidate.get("error") or candidate.get("duplicate") or candidate.get("known"))
            item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        for column in range(self._tree.columnCount()):
            self._tree.resizeColumnToContents(column)
        layout.addWidget(self._tree)
        buttons = QHBoxLayout()
        select_all = QPushButton(tr("Select all"))
        select_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        clear_all = QPushButton(tr("Select none"))
        clear_all.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        ok = QPushButton(tr("Import"))
        ok.clicked.connect(self.accept)
        cancel = QPushButton(tr("Cancel"))
        cancel.clicked.connect(self.reject)
        for button in (select_all, clear_all):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _set_all(self, state: Qt.CheckState) -> None:
        for position in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(position).setCheckState(0, state)

    def chosen(self) -> List[Dict[str, Any]]:
        result = []
        for position in range(self._tree.topLevelItemCount()):
            if self._tree.topLevelItem(position).checkState(0) == Qt.CheckState.Checked:
                result.append(self._candidates[position])
        return result
