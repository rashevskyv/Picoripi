"""The Project Manager window: the projects the user added, in a list or a grid, with groups, details and a progress strip.

The window never parses project content. A scan child process (``ui/project_manager/scan_process.py``) reads the cards,
icons and string counts and reports one small event per project; the window updates the row the event names. Rows
change in place while a scan runs, so the scroll position and the selection stay where the user put them.
"""
from __future__ import annotations

import os
import time
import unicodedata
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import QProcess, QRect, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QCursor, QDesktopServices, QIcon, QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSplitter,
    QStackedWidget, QStyledItemDelegate, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.glossary.series import GROUP_METADATA_KEY, series_dir
from core.i18n import tr
from core.project.persist_mixin import next_project_sequence
from core.project_library import index, registry, resources, views
from core.project_library import build, share
from core.project_library.build import emulator_argv, emulator_platform, emulator_template_for
from core.project_library.cards import fallback_name, percent_translated, read_card
from core.project_library.discovery import find_projects, platform_from_parts
from core.project_library.flags import FLAG_NAMES, flags_of
from core.project_library.icons import ICON_SIZE, IMAGE_FILTER, save_user_icon
from core.project_library.plugin_facts import PLUGIN_MISSING, default_load_rules
from core.project_library.registry import EMULATOR_PREFIX
from core.project_library.scan import ICON_FILE_NAME
from ui.project_manager import image_labels
from ui.project_manager.emulator_dialog import EmulatorDialog
from ui.project_manager.group_glossary import (
    GroupGlossaryFileJob,
    InspectGlossaryJob,
    OpenProjectSyncJob,
    apply_folder_glossary_mutation,
    confirm_unlink_shared_glossary,
    prompt_link_shared_glossary,
    prompt_new_shared_glossary,
    read_project_group_glossary,
    same_project_file,
    update_project_group_glossary,
)
from ui.project_manager.jobs import BackgroundJob
from ui.project_manager.scan_process import ScanProcess
from ui.project_manager.tasks import ActionJob, ResourceJob
from utils.logging_utils import log_debug, log_error, log_info, log_warning
from utils.thread_utils import safe_shutdown_thread, single_shot

KEY_ROLE = Qt.ItemDataRole.UserRole
KIND_ROLE = Qt.ItemDataRole.UserRole + 1
DETAIL_ROLE = Qt.ItemDataRole.UserRole + 2
PERCENT_ROLE = Qt.ItemDataRole.UserRole + 3

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
COLUMNS = ("Project name", "Platform", "Series", "Plugin", "Progress", "Last opened", "Status")
PROGRESS_COLUMN = COLUMNS.index("Progress")
LIST_ICON_SIZE = 64
LIST_COLUMN_WIDTHS = (340, 70, 120, 130, 170, 110)  # the last column (Status) takes the rest
SEARCH_DELAY_MS = 150  # the list filters this long after the last key press


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def matches_search(row: Dict[str, Any], query: str) -> bool:
    """True when every word of ``query`` is part of the project name, series, platform, plugin, the manager's folder
    (group) the project is in, or its folder path.

    The match ignores case and the Unicode form. Words may sit in different fields: ``aria gba`` finds a GBA
    project named Aria.
    """
    fields = [_fold(str(row.get(name) or "")) for name in ("name", "series", "platform", "plugin", "folder", "path")]
    return all(any(word in field for field in fields) for word in _fold(query).split())


# ----- registry operations, run on a worker thread by BackgroundJob -----
def _op_add(reg: registry.Registry, path: str, project_id: str, platform: str) -> None:
    reg.add(path, project_id=project_id, platform=platform)


def _set_group_glossary(path: str, target: Optional[str], history: List[Tuple[str, Optional[str]]]) -> None:
    """Set the group glossary in one closed project file and record the old value in ``history``.

    Nothing is written when there is nothing to change. A missing project file is logged and skipped.
    """
    prev = read_project_group_glossary(path)
    if target is None and prev is None:
        return
    try:
        if update_project_group_glossary(path, target):
            history.append((path, prev))
    except FileNotFoundError as exc:
        log_warning(f"Group glossary not updated: {exc}")


def _restore_group_glossaries(history: List[Tuple[str, Optional[str]]]) -> None:
    for m_path, m_prev in reversed(history):
        try:
            update_project_group_glossary(m_path, m_prev, is_rollback=True)
        except Exception as rb_exc:
            log_error(f"Rollback failed for {m_path}: {rb_exc}")


def _op_remove(reg: registry.Registry, path: str, open_file: Optional[str] = None) -> Any:
    history: List[Tuple[str, Optional[str]]] = []
    if not open_file or not same_project_file(path, open_file):
        try:
            _set_group_glossary(path, None, history)
        except Exception as exc:
            raise OSError(f"Failed to remove project {path}: could not clear group glossary ({exc})") from exc
    reg.remove(path)
    return partial(_restore_group_glossaries, history)


def _op_set_name(reg: registry.Registry, path: str, name: str) -> None:
    reg.update_fields(path, name=name)


def _op_move(reg: registry.Registry, path: str, folder_id: Optional[str],
             open_file: Optional[str] = None) -> Any:
    target_glossary = reg.folder_glossary(folder_id) if folder_id else None
    history: List[Tuple[str, Optional[str]]] = []
    if not open_file or not same_project_file(path, open_file):
        try:
            _set_group_glossary(path, target_glossary, history)
        except Exception as exc:
            log_error(f"Failed to update group glossary when moving project {path}: {exc}")
            raise OSError(f"Failed to move project {path}: could not update group glossary ({exc})") from exc
    reg.update_fields(path, folder_id=folder_id)
    return partial(_restore_group_glossaries, history)


def _op_set_platform(reg: registry.Registry, path: str, platform: str) -> None:
    reg.update_fields(path, platform=platform)


def _op_create_folder(reg: registry.Registry, name: str) -> None:
    reg.create_folder(name)


def _op_rename_folder(reg: registry.Registry, folder_id: str, name: str) -> None:
    reg.rename_folder(folder_id, name)


def _op_delete_folder(reg: registry.Registry, folder_id: str,
                      open_file: Optional[str] = None) -> Any:
    affected = [entry["path"] for entry in reg.document["projects"] if entry.get("folder_id") == folder_id]
    history: List[Tuple[str, Optional[str]]] = []
    try:
        for p_path in affected:
            if not open_file or not same_project_file(p_path, open_file):
                _set_group_glossary(p_path, None, history)
    except Exception as exc:
        _restore_group_glossaries(history)
        raise OSError(f"Failed to delete folder {folder_id}: could not clear project group glossary ({exc})") from exc
    reg.delete_folder(folder_id)
    return partial(_restore_group_glossaries, history)


def _op_set_folder_glossary(reg: registry.Registry, folder_id: str, glossary_path: Optional[str],
                            open_file: Optional[str] = None) -> Any:
    return apply_folder_glossary_mutation(reg, folder_id, glossary_path, open_file)


def _op_set_view(reg: registry.Registry, **choices: Any) -> None:
    reg.set_view(**choices)


def _op_import(reg: registry.Registry, items: List[Dict[str, Any]],
               open_file: Optional[str] = None) -> Any:
    """Add the chosen projects. One folder per series name is created when it is missing."""
    folder_ids: Dict[str, str] = {}
    for folder in reg.document["folders"]:
        folder_ids.setdefault(folder["name"].casefold(), folder["id"])

    history: List[Tuple[str, Optional[str]]] = []
    try:
        for item in items:
            series = item.get("series") or ""
            folder_id = None
            if series:
                folder_id = folder_ids.get(series.casefold())
                if folder_id is None:
                    folder_id = reg.create_folder(series)
                    folder_ids[series.casefold()] = folder_id
            p_path = item["project_file"]
            added = reg.add(p_path, project_id=item.get("project_id", ""), platform=item.get("platform", ""),
                            folder_id=folder_id)
            target_glossary = reg.folder_glossary(folder_id) if added and folder_id else None
            if target_glossary and (not open_file or not same_project_file(p_path, open_file)):
                _set_group_glossary(p_path, target_glossary, history)
    except Exception as exc:
        _restore_group_glossaries(history)
        raise OSError(f"Failed to import projects: could not set group glossary ({exc})") from exc
    return partial(_restore_group_glossaries, history)


def _card_facts(project_file: str) -> tuple:
    """Project id and platform guess of a project added by hand. Raises ``ValueError`` when it is no project."""
    card = read_card(project_file)
    return card["project_id"], platform_from_parts([Path(project_file).parent.parent.name])


def _load_state(directory: str) -> tuple:
    """The registry document, the cached index entries, and the cached icons as images (loaded off the window)."""
    document = registry.read(directory)
    entries = index.read(directory)
    images: Dict[str, QImage] = {}
    for key, entry in entries.items():
        file = str((entry.get("icon") or {}).get("file") or "")
        if file and Path(file).is_file():
            image = QImage(file)
            if not image.isNull():
                images[key] = image
    return document, entries, images


def _read_image(path: str) -> Optional[QImage]:
    image = QImage(path)
    return None if image.isNull() else image


def _call(function: Callable[..., Any], *args: Any) -> Callable[..., None]:
    """A slot for a Qt signal. Qt passes extra arguments (``checked``); this slot drops them."""
    return lambda *_ignored: function(*args)


def _message_page(text: str) -> QWidget:
    """A page of the list stack that shows one centred line."""
    page = QWidget()
    layout = QVBoxLayout(page)
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addStretch(1)
    layout.addWidget(label)
    layout.addStretch(1)
    return page


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


def series_summary(series: Optional[Dict[str, Any]]) -> str:
    """The series glossaries a project links (its own and the folders above), with their term count."""
    files = list((series or {}).get("files") or [])
    if not files:
        return tr("None")
    names = ", ".join(str(entry.get("name") or "") for entry in files)
    parts = [tr("{0} ({1:,} terms)", names, int((series or {}).get("terms") or 0))]
    link = {"linked": tr("linked"), "group": tr("from group"), "folders": tr("found in the folders above")}.get(str((series or {}).get("link") or ""))
    if link:
        parts.append(link)
    reusable = (series or {}).get("reusable")
    if isinstance(reusable, int):
        parts.append(tr("{0:,} texts translated in other games", reusable))
    return "; ".join(parts)


def series_of(path: str) -> str:
    """The series folder of a project, read from its folder layout.

    ``<Series>/<Game>/<Platform>/picoripi/project.uiproj`` has a platform folder one level above ``picoripi``;
    ``<Series>/<Game>/picoripi/project.uiproj`` has none. The root folder is not stored, so a project directly under
    the root shows the root's name here.
    """
    parts = Path(path).parts
    if len(parts) >= 5 and platform_from_parts([parts[-3]]):
        return parts[-5]
    return parts[-4] if len(parts) >= 4 else ""


def _initials(name: str) -> str:
    words = [word for word in name.replace("-", " ").split() if word]
    return "".join(word[0] for word in words[:2]).upper() or "?"


def _size_text(size: int) -> str:
    if size >= 1024 ** 3:
        return tr("{0} GB", f"{size / 1024 ** 3:,.1f}")
    if size >= 1024 ** 2:
        return tr("{0} MB", f"{size / 1024 ** 2:,.1f}")
    return tr("{0} KB", f"{size / 1024:,.1f}")


def _eta_text(seconds: float) -> str:
    if seconds < 90:
        return tr("about {0} s left", max(1, int(round(seconds))))
    return tr("about {0} min left", max(1, int(round(seconds / 60))))


def _tile_icon(size: int, platform: str, series: str) -> QIcon:
    """The generated tile of a project without an icon: a colour for the platform, the series initials."""
    seed = platform or series or "?"
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor.fromHsv(sum(ord(c) for c in seed) * 37 % 360, 90, 150))
    painter = QPainter(pixmap)
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(max(10, size // 4))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, _initials(series or platform))
    painter.end()
    return QIcon(pixmap)


class ProgressDelegate(QStyledItemDelegate):
    """Draws the translated share of a project as a thin bar under the text of the Progress column."""

    def paint(self, painter, option, index) -> None:  # noqa: N802 - Qt's name
        super().paint(painter, option, index)
        percent = index.data(PERCENT_ROLE)
        if index.column() != PROGRESS_COLUMN or percent is None:
            return
        rect = option.rect
        bar = QRect(rect.left() + 6, rect.bottom() - 7, max(0, rect.width() - 12), 4)
        painter.save()
        painter.fillRect(bar, QColor(128, 128, 128, 80))
        painter.fillRect(QRect(bar.left(), bar.top(), bar.width() * int(percent) // 100, bar.height()),
                         QColor("#2e8b57"))
        painter.restore()


class ProjectManagerDialog(QDialog):
    """The list of projects the user added. Opens the chosen project through the callbacks given by the handler.

    ``save_flags(project_file, updates)`` and ``save_setting(name, value)`` store the user's choices; the handler decides
    whether an open project or a worker writes them. ``load_rules`` builds a plugin for the build and run actions.
    """

    def __init__(self, parent, library_dir: str, open_project: Callable[[str], None],
                 new_project: Callable[[], None], save_flags: Callable[[str, Dict[str, bool]], None],
                 save_setting: Callable[[str, str], None],
                 load_rules: Callable[[str], Any] = default_load_rules,
                 on_closed: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Project Manager"))
        self.resize(1100, 620)
        self._dir = library_dir
        self._open_project = open_project
        self._new_project = new_project
        self._save_flags = save_flags
        self._save_setting = save_setting
        self._load_rules = load_rules
        self._on_closed = on_closed  # called when the user closes the window; not when a project is opened from it
        self._closing_for_project = False
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(SEARCH_DELAY_MS)
        self._filter_timer.timeout.connect(self._render)
        self._document: Dict[str, Any] = {"projects": [], "folders": [], "view": dict(registry.DEFAULT_VIEW),
                                          "settings": {}}
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._cards: Dict[str, Dict[str, Any]] = {}
        self._flag_state: Dict[str, Dict[str, bool]] = {}
        self._scanned: set = set()
        self._loaded = False
        self._render_scheduled = False
        self._jobs: List[Any] = []
        self._mode = "list"
        # rows: the widgets, kept between renders so a change updates them in place
        self._items: Dict[str, QTreeWidgetItem] = {}
        self._headers: Dict[Tuple[str, str], QTreeWidgetItem] = {}
        self._grid_items: Dict[str, QListWidgetItem] = {}
        self._shown: List[Tuple[str, str, List[str]]] = []
        self._frozen: Optional[Tuple[Dict[str, Any], frozenset, List[Tuple[str, str, List[str]]]]] = None
        self._detail_signature: Dict[str, str] = {}
        self._status_labels: Dict[str, QLabel] = {}
        self._action_text: Dict[str, str] = {}
        self._action_jobs: Dict[str, ActionJob] = {}
        self._action_platform: Dict[str, str] = {}  # job key -> platform whose emulator command Run uses
        self._resource_trees: Dict[str, QTreeWidget] = {}  # row key -> the resource tree shown in its details
        self._resource_cache: Dict[str, Dict[str, Dict[str, int]]] = {}  # row key -> counts (kept for this window)
        self._resource_jobs: Dict[str, ResourceJob] = {}
        self._grid_detail_signature: Optional[str] = None  # the row the grid's details pane shows
        self._icon_images: Dict[str, QImage] = {}
        self._icons: Dict[str, QIcon] = {}
        self._tiles: Dict[Tuple[str, str], QIcon] = {}
        # the scan
        self._scan = ScanProcess(self)
        self._scan.event_received.connect(self._on_scan_event)
        self._scan.stopped.connect(self._on_scan_stopped)
        self._scan_active = False
        self._user_cancelled = False
        self._scan_total = 0
        self._scan_stale = 0
        self._scan_position = 0
        self._scan_name = ""
        self._planned = False  # True once the child sent its plan; before that the checked projects show the progress
        self._checked = 0
        self._eta_average: Optional[float] = None
        self._last_tick: Optional[float] = None
        self._open_sync_token = 0
        self._open_sync_job: Optional[OpenProjectSyncJob] = None
        self._open_sync_file: Optional[str] = None
        self._build_ui()
        self._run(BackgroundJob(_load_state, library_dir), self._on_state)
        self._status.setText(tr("Loading projects..."))

    def reload(self) -> None:
        """Read the registry and the cache again, and scan again; the list may have changed while the window was hidden."""
        self._scanned = set()
        self._loaded = False
        self._status.setText(tr("Loading projects..."))
        self._run(BackgroundJob(_load_state, self._dir), self._on_state)

    # ----- layout -----
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self._add_button = QToolButton()
        self._add_button.setText(tr("+ Add project"))
        self._add_button.setToolTip(tr("Add a project"))
        self._add_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self._add_button)
        menu.addAction(tr("New project..."), self._new_project_clicked)
        menu.addAction(tr("Add existing project..."), self._add_existing_clicked)
        menu.addAction(tr("Import projects from a folder..."), self._import_clicked)
        menu.addAction(tr("Import shared project..."), self._import_shared_clicked)
        self._add_button.setMenu(menu)
        bar.addWidget(self._add_button)

        new_folder = QPushButton(tr("New folder..."))
        new_folder.clicked.connect(self._new_folder_clicked)
        bar.addWidget(new_folder)
        group_glossary = QPushButton(tr("Group glossary..."))
        group_glossary.setToolTip(tr("Manage shared glossary for the selected folder or group"))
        group_glossary.clicked.connect(self._group_glossary_clicked)
        bar.addWidget(group_glossary)
        emulator = QPushButton(tr("Emulator..."))
        emulator.setToolTip(tr("One emulator command per platform. Run in emulator uses the command of its platform."))
        emulator.clicked.connect(self._emulator_clicked)
        bar.addWidget(emulator)
        bar.addStretch(1)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("Search projects"))
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumWidth(220)
        self._search.textChanged.connect(lambda _text: self._filter_timer.start())
        bar.addWidget(self._search)
        find_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Find), self)
        find_shortcut.activated.connect(self._focus_search)

        self._list_button = QToolButton()
        self._list_button.setText(tr("List"))
        self._list_button.setCheckable(True)
        self._list_button.setChecked(True)
        self._grid_button = QToolButton()
        self._grid_button.setText(tr("Grid"))
        self._grid_button.setCheckable(True)
        self._list_button.clicked.connect(partial(self._set_mode, "list"))
        self._grid_button.clicked.connect(partial(self._set_mode, "grid"))
        bar.addWidget(self._list_button)
        bar.addWidget(self._grid_button)

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

        # the progress strip: shown while a scan runs, never blocks the list
        self._strip = QFrame()
        self._strip.setFrameShape(QFrame.Shape.StyledPanel)
        strip = QHBoxLayout(self._strip)
        self._strip_label = QLabel("")
        self._strip_bar = QProgressBar()
        self._strip_bar.setMaximumWidth(260)
        self._strip_bar.setTextVisible(False)
        hide_button = QPushButton(tr("Hide"))
        hide_button.setToolTip(tr("Hide this strip. The scan goes on."))
        hide_button.clicked.connect(self._strip.hide)
        cancel_button = QPushButton(tr("Cancel scan"))
        cancel_button.clicked.connect(self._cancel_scan_clicked)
        strip.addWidget(self._strip_label, 1)
        strip.addWidget(self._strip_bar)
        strip.addWidget(hide_button)
        strip.addWidget(cancel_button)
        self._strip.hide()
        layout.addWidget(self._strip)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([tr(column) for column in COLUMNS])
        self._tree.setColumnCount(len(COLUMNS))
        for column, width in enumerate(LIST_COLUMN_WIDTHS):
            self._tree.setColumnWidth(column, width)
        self._tree.setAlternatingRowColors(True)
        self._tree.setIconSize(QSize(LIST_ICON_SIZE, LIST_ICON_SIZE))
        self._tree.setItemDelegate(ProgressDelegate(self._tree))
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(partial(self._context_menu, self._tree))
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.itemExpanded.connect(self._on_expanded)
        self._tree.header().setStretchLastSection(True)

        self._grid = QListWidget()
        self._grid.setViewMode(QListWidget.ViewMode.IconMode)
        self._grid.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self._grid.setGridSize(QSize(ICON_SIZE + 40, ICON_SIZE + 64))
        self._grid.setWordWrap(True)
        self._grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._grid.customContextMenuRequested.connect(partial(self._context_menu, self._grid))
        self._grid.itemDoubleClicked.connect(self._on_grid_double_click)
        self._grid.itemSelectionChanged.connect(self._refresh_grid_detail)
        # the grid's details: the same widget as the list's expanded row, under the grid for the selected project
        self._grid_details = QScrollArea()
        self._grid_details.setWidgetResizable(True)
        self._grid_details.hide()
        self._grid_page = QSplitter(Qt.Orientation.Vertical)
        self._grid_page.addWidget(self._grid)
        self._grid_page.addWidget(self._grid_details)
        self._grid_page.setStretchFactor(0, 3)
        self._grid_page.setStretchFactor(1, 2)

        self._empty = _message_page(tr("No projects yet. Press \"+ Add project\" to add a game."))
        self._no_match = _message_page(tr("No project matches this search."))

        self._stack = QStackedWidget()
        self._stack.addWidget(self._tree)
        self._stack.addWidget(self._grid_page)
        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._no_match)
        layout.addWidget(self._stack, 1)

        self._status = QLabel("")
        layout.addWidget(self._status)

        self._group.currentIndexChanged.connect(self._view_changed)
        self._sort.currentIndexChanged.connect(self._view_changed)
        self._descending.toggled.connect(self._view_changed)

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._list_button.setChecked(mode == "list")
        self._grid_button.setChecked(mode == "grid")
        self._render()

    # ----- jobs -----
    def _run(self, job: BackgroundJob, on_done: Callable[[Any], None]) -> None:
        self._jobs.append(job)
        job.done.connect(on_done)
        job.done.connect(lambda _result, j=job: self._forget(j))
        job.failed.connect(self._on_failed)
        job.failed.connect(lambda _message, j=job: self._forget(j))
        if hasattr(job, "cancelled"):
            job.cancelled.connect(lambda j=job: self._forget(j))
        job.start()

    def _forget(self, job: Any) -> None:
        if job in self._jobs:
            self._jobs.remove(job)

    def _on_failed(self, message: str) -> None:
        self._status.setText(tr("Something went wrong: {0}", message))

    def _on_state(self, state: tuple) -> None:
        self._document, self._entries, images = state
        self._icon_images.update(images)
        self._icons = {}
        self._loaded = True
        self._render()
        self._start_scan()

    # ----- the scan -----
    def _start_scan(self) -> None:
        """Scan every project in the list. One scan at a time: a new one replaces the running one."""
        targets = [(registry.project_key(entry["path"]), str(entry["path"])) for entry in self._document["projects"]]
        if not targets:
            self._scan_active = False
            self._strip.hide()
            self._status.setText("")   # nothing to load: the empty list says what to do
            return
        self._scan.shutdown()
        self._scan_active = True
        self._user_cancelled = False
        self._scan_total = len(targets)
        self._scan_stale = 0
        self._scan_position = 0
        self._scan_name = ""
        self._planned = False
        self._checked = 0
        self._eta_average = None
        self._last_tick = None
        self._scan.start(self._dir, targets)
        self._strip_bar.setRange(0, 0)  # busy until the first card: the child is still starting
        self._strip_label.setText(tr("Checking {0} projects...", len(targets)))
        self._strip.show()
        self._status.setText(tr("Checking {0} projects...", len(targets)))

    def _show_checking(self) -> None:
        """The check phase: the child reads every card, then checks each project's icon and files before it plans the
        counts. The checked projects are the progress."""
        if self._checked == 1:  # the first project: the bar stops being busy and counts the checked projects
            self._strip_bar.setRange(0, max(1, self._scan_total))
        self._strip_bar.setValue(self._checked)
        text = tr("Checking {0} of {1} projects...", self._checked, self._scan_total)
        self._strip_label.setText(text)
        self._status.setText(text)

    def _on_scan_event(self, event: Dict[str, Any]) -> None:
        kind = event.get("event")
        if kind == "card":
            key = str(event.get("key"))
            self._cards[key] = dict(event.get("card") or {})
            self._scanned.add(key)
            if "series" in event:
                self._entries.setdefault(key, {})["series_glossaries"] = dict(event.get("series") or {})
            self._schedule_render()
        elif kind == "checked":
            if not self._planned:
                self._checked = int(event.get("done") or 0)
                self._show_checking()
        elif kind == "icon":
            key = str(event.get("key"))
            path = str(event.get("file") or "")
            if path:
                self._run(BackgroundJob(_read_image, path), partial(self._on_icon_image, key))
            else:
                self._icon_images.pop(key, None)
                self._icons.pop(key, None)
                self._schedule_render()
        elif kind == "plan":
            self._planned = True
            self._scan_total = int(event.get("total") or 0)
            self._scan_stale = int(event.get("stale") or 0)
            self._scan_position = 0
            if self._scan_stale:
                self._strip_bar.setRange(0, max(1, self._scan_total))
                self._show_progress()
            else:
                self._strip.hide()
        elif kind == "progress":
            self._scan_position = int(event.get("done") or 0)
            self._scan_name = str(event.get("name") or "")
            self._tick()
            self._show_progress()
        elif kind == "counts":
            key = str(event.get("key"))
            fields = dict(event.get("fields") or {})
            entry = self._entries.setdefault(key, {})
            if "count_error" not in fields:
                entry.pop("count_error", None)  # a fresh count replaces an old error
            entry.update(fields)
            self._schedule_render()
        elif kind == "done":
            self._scan_active = False
            self._strip.hide()
            log_info(f"Project manager scan: {event.get('total')} projects checked, {event.get('counted')} counted, "
                     f"{event.get('plugin_missing')} plugin missing, {event.get('failed')} failed, "
                     f"{event.get('seconds')} s.")
            if int(event.get("failed") or 0):
                log_warning(f"Project manager: {event.get('failed')} projects could not be counted.")
            self._status.setText(tr("{0} projects.", len(self._document["projects"])))
            self._schedule_render()

    def _on_icon_image(self, key: str, image: Optional[QImage]) -> None:
        if image is not None:
            self._icon_images[key] = image
            self._icons.pop(key, None)
            self._schedule_render()

    def _tick(self) -> None:
        """Track how long each counted project takes: the average gives the time left."""
        now = time.monotonic()
        if self._last_tick is not None:
            sample = now - self._last_tick
            self._eta_average = sample if self._eta_average is None else 0.7 * self._eta_average + 0.3 * sample
        self._last_tick = now

    def _show_progress(self) -> None:
        done = self._scan_total - self._scan_stale + self._scan_position
        remaining = self._scan_stale - self._scan_position
        if self._eta_average is None or self._scan_position <= 0:
            eta = tr("estimating time left")
        else:
            eta = _eta_text(remaining * self._eta_average)
        text = tr("Scanning {0} of {1} — {2} — {3}", done, self._scan_total, self._scan_name, eta)
        self._strip_bar.setValue(done)
        self._strip_label.setText(text)
        self._strip.show()
        self._status.setText(text)

    def _cancel_scan_clicked(self) -> None:
        self._user_cancelled = True
        self._scan.cancel()
        self._strip.hide()

    def _on_scan_stopped(self, finished: bool) -> None:
        """The child ended. Its last event (done) already hid the strip; a cancel or a crash leaves what it wrote."""
        self._scan_active = False
        self._strip.hide()
        if self._user_cancelled:
            self._status.setText(tr("Scan cancelled."))
        elif not finished:
            self._status.setText(tr("Scan stopped."))
        self._schedule_render()

    # ----- rendering -----
    def _schedule_render(self) -> None:
        """Rebuild the list soon. Several events in a row become one render."""
        if self._render_scheduled:
            return
        self._render_scheduled = True

        def fire() -> None:
            self._render_scheduled = False
            self._render()

        single_shot(150, self, fire)

    def _rows(self) -> List[Dict[str, Any]]:
        rows = []
        folder_names = {folder["id"]: folder["name"] for folder in self._document["folders"]}
        for entry in self._document["projects"]:
            path = entry["path"]
            key = registry.project_key(path)
            cached = self._entries.get(key) or {}
            card = self._cards.get(key) or cached.get("card") or {}
            counts = cached.get("counts") or None
            rows.append({
                "key": key,
                "path": path,
                "name": entry.get("name") or card.get("name") or fallback_name(path),
                "folder_id": entry.get("folder_id") or "",
                "folder": folder_names.get(entry.get("folder_id") or "", ""),
                "platform": entry.get("platform") or "",
                "series": series_of(path),
                "counts": counts,
                "lines": counts.get("lines") if counts else None,
                "translated": percent_translated(counts) if counts else None,
                "blocks": card.get("blocks"),
                "modified": card.get("modified", ""),
                "issues": list(card.get("issues", [])),
                "last_opened": entry.get("last_opened") or "",
                "added": entry.get("added") or "",
                "plugin": card.get("plugin", ""),
                "images": list(card.get("images") or []),
                "source_roles": dict(card.get("source_roles") or {}),
                "refreshing": key not in self._scanned,
                "targets": list(cached.get("targets") or []),
                "groups": dict(cached.get("groups") or {}),
                "skipped": int(cached.get("skipped") or 0),
                "missing_translations": int(cached.get("missing_translations") or 0),
                "count_error": str(cached.get("count_error") or ""),
                "counted_at": cached.get("counted_at") or "",
                "glossary_series": dict(cached.get("series_glossaries") or {}),
                "flags": self._flag_state.get(key) or card.get("flags") or flags_of({}),
            })
        return rows

    def _render(self) -> None:
        """Bring the view in line with the registry and the cache.

        The order does not change while a scan runs: a count that arrives updates its row, it does not move it. The
        order is worked out again when the scan ends, or when a project is added or removed, or the view changes.
        """
        view = dict(self._document.get("view", {}))
        self._sync_controls(view)
        rows = self._rows()
        rows_by_key = {row["key"]: row for row in rows}
        query = self._search.text().strip()
        shown = [row for row in rows if matches_search(row, query)] if query else rows
        last = max((row for row in rows if row["last_opened"]), key=lambda r: r["last_opened"], default=None)
        folder_names = {folder["id"]: folder["name"] for folder in self._document["folders"]}
        keys = frozenset(row["key"] for row in shown)
        shape = self._shape_for(shown, view, folder_names, last["key"] if last else None)
        if self._scan_active and self._frozen is not None and self._frozen[0] == view and self._frozen[1] == keys:
            shape = self._frozen[2]
        self._frozen = (view, keys, shape)
        has_folders = bool(self._document.get("folders")) and view.get("group_by", "folder") == "folder"
        if not rows and not has_folders:
            self._stack.setCurrentWidget(self._empty)
        elif not shown and rows:
            self._stack.setCurrentWidget(self._no_match)
        else:
            self._stack.setCurrentWidget(self._grid_page if self._mode == "grid" else self._tree)
        if shape == self._shown and self._items:
            self._update_in_place(shape, rows_by_key)
        else:
            self._rebuild(shape, rows_by_key, folder_names)

    @staticmethod
    def _shape_for(rows: List[Dict[str, Any]], view: Dict[str, Any], folder_names: Dict[str, str],
                   last_key: Optional[str]) -> List[Tuple[str, str, List[str]]]:
        return [(kind, value, [row["key"] for row in group])
                for kind, value, group in views.arrange(rows, view, folder_names, last_key)]

    def _rebuild(self, shape: List[Tuple[str, str, List[str]]], rows_by_key: Dict[str, Dict[str, Any]],
                 folder_names: Dict[str, str]) -> None:
        """Build the widgets again. The scroll position, the selection and the open details are kept."""
        scroll = self._tree.verticalScrollBar().value()
        expanded = {key for key, item in self._items.items() if item.isExpanded()}
        selected = self._selected_key()
        self._tree.setUpdatesEnabled(False)  # one paint at the end instead of one per row
        self._grid.setUpdatesEnabled(False)
        self._tree.clear()
        self._grid.clear()
        self._items = {}
        self._headers = {}
        self._grid_items = {}
        self._status_labels = {}
        self._detail_signature = {}
        folder_glossaries = {folder["id"]: folder.get("glossary_path") for folder in self._document["folders"]
                             if folder.get("glossary_path")}
        for kind, value, keys in shape:
            header = QTreeWidgetItem(self._tree, [self._section_label(kind, value, folder_names, len(keys),
                                                                       folder_glossaries)])
            header.setFirstColumnSpanned(True)
            header.setData(0, KIND_ROLE, (kind, value))
            if kind == "folder" and folder_glossaries.get(value):
                header.setToolTip(0, tr("Shared glossary: {path}", path=folder_glossaries[value]))
            header.setExpanded(True)
            font = header.font(0)
            font.setBold(True)
            header.setFont(0, font)
            self._headers[(kind, value)] = header
            for key in keys:
                row = rows_by_key[key]
                item = QTreeWidgetItem(header)
                item.setData(0, KEY_ROLE, key)
                item.setData(0, KIND_ROLE, ("project", row["path"]))
                self._fill(item, row)
                detail = QTreeWidgetItem(item)
                detail.setFirstColumnSpanned(True)
                detail.setData(0, DETAIL_ROLE, key)
                self._items[key] = item
                grid_item = QListWidgetItem()
                grid_item.setData(KEY_ROLE, key)
                self._fill_grid(grid_item, row)
                self._grid.addItem(grid_item)
                self._grid_items[key] = grid_item
                if key in expanded:
                    item.setExpanded(True)
                    self._on_expanded(item)
        self._shown = shape
        self._tree.setUpdatesEnabled(True)
        self._grid.setUpdatesEnabled(True)
        self._tree.updateGeometries()
        self._tree.verticalScrollBar().setValue(scroll)
        self._restore_selection(selected)
        self._refresh_grid_detail()

    def _update_in_place(self, shape: List[Tuple[str, str, List[str]]], rows_by_key: Dict[str, Dict[str, Any]]) -> None:
        """The same projects in the same order: only the cells, icons and details that changed are set."""
        for _kind, _value, keys in shape:
            for key in keys:
                row = rows_by_key[key]
                item = self._items[key]
                self._fill(item, row)
                self._fill_grid(self._grid_items[key], row)
                if item.isExpanded():
                    self._refresh_detail(item, row)
        self._refresh_grid_detail()

    def _refresh_grid_detail(self) -> None:
        """Show the selected project's details under the grid. Rebuilt only when that project's row changed."""
        row = self._row_by_key(self._selected_key()) if self._mode == "grid" else None
        if row is None:
            self._grid_detail_signature = None
            old = self._grid_details.takeWidget()
            if old is not None:
                old.deleteLater()
            self._grid_details.hide()
            return
        signature = repr(sorted((name, repr(value)) for name, value in row.items()))
        if signature == self._grid_detail_signature:
            return
        self._grid_detail_signature = signature
        old = self._grid_details.takeWidget()
        if old is not None:
            old.deleteLater()
        self._grid_details.setWidget(self._detail_widget(row))
        self._grid_details.show()

    def _refresh_detail(self, item: QTreeWidgetItem, row: Dict[str, Any]) -> None:
        signature = repr(sorted((name, repr(value)) for name, value in row.items()))
        if self._detail_signature.get(row["key"]) == signature:
            return
        self._detail_signature[row["key"]] = signature
        detail = item.child(0)
        self._tree.setItemWidget(detail, 0, self._detail_widget(row))

    def _selected_key(self) -> Optional[str]:
        if self._mode == "grid":
            selected = self._grid.selectedItems()
            return selected[0].data(KEY_ROLE) if selected else None
        item = self._tree.currentItem()
        return item.data(0, KEY_ROLE) if item is not None else None

    def _restore_selection(self, key: Optional[str]) -> None:
        if key is None:
            return
        if key in self._items:
            self._tree.setCurrentItem(self._items[key])
        if key in self._grid_items:
            self._grid_items[key].setSelected(True)

    def _fill(self, item: QTreeWidgetItem, row: Dict[str, Any]) -> None:
        for column, text in enumerate(self._cells(row)):
            item.setText(column, text)
        item.setIcon(0, self._icon_for(row))
        images_text = "\n".join(image_labels.summary_lines(row.get("images") or []))
        item.setToolTip(0, f"{row['path']}\n{images_text}" if images_text else row["path"])
        item.setData(PROGRESS_COLUMN, PERCENT_ROLE, row["translated"])

    def _fill_grid(self, item: QListWidgetItem, row: Dict[str, Any]) -> None:
        item.setText(f"{row['name']}\n{self._progress_text(row)}")
        item.setIcon(self._icon_for(row))
        item.setToolTip(row["path"])

    def _icon_for(self, row: Dict[str, Any]) -> QIcon:
        """The project's icon: its picture (the user's or the plugin's), else the generated tile."""
        key = row["key"]
        if key in self._icons:
            return self._icons[key]
        image = self._icon_images.get(key)
        if image is not None:
            icon = QIcon(QPixmap.fromImage(image))
            self._icons[key] = icon
            return icon
        tile_key = (row["platform"], row["series"])
        if tile_key not in self._tiles:
            self._tiles[tile_key] = _tile_icon(ICON_SIZE, row["platform"], row["series"])
        return self._tiles[tile_key]

    @staticmethod
    def _progress_text(row: Dict[str, Any]) -> str:
        counts = row["counts"]
        if counts:
            needs = counts.get("needs_translation") or 0
            if needs > 0:
                return f"{counts.get('translated', 0):,} / {needs:,} · {row['translated']} %"
            return "—"
        if row["count_error"] or "plugin_missing" in row["issues"]:
            return "—"
        return "…"

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
    def _section_label(kind: str, value: str, folder_names: Dict[str, str], count: int,
                       folder_glossaries: Optional[Dict[str, str]] = None) -> str:
        title = ProjectManagerDialog._section_title(kind, value, folder_names)
        if kind == "folder" and folder_glossaries and folder_glossaries.get(value):
            glossary_name = Path(folder_glossaries[value]).stem
            return f"{title} · {tr('Glossary: {name}', name=glossary_name)}  ({count})"
        return f"{title}  ({count})"

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
        return [
            row["name"],
            row["platform"] or "—",
            row["series"] or "—",
            row["plugin"] or "—",
            ProjectManagerDialog._progress_text(row),
            format_modified(row["last_opened"]),
            ProjectManagerDialog._status_text(row),
        ]

    @staticmethod
    def _status_text(row: Dict[str, Any]) -> str:
        issues = set(row["issues"])
        flags = []
        if row["refreshing"]:
            flags.append(tr("refreshing..."))
        if "project_file_missing" in issues:
            flags.append(tr("Missing"))
        elif "unreadable" in issues:
            flags.append(tr("Unreadable"))
        elif not row["refreshing"]:
            flags.append(tr("Opens"))
        if "plugin_missing" in issues or row["count_error"] == PLUGIN_MISSING:
            flags.append(tr("Plugin missing"))
        if issues - {"project_file_missing", "unreadable", "plugin_missing"}:
            flags.append(tr("Needs attention"))
        for name in FLAG_NAMES:
            if row["flags"].get(name):
                flags.append(tr(FLAG_LABELS[name]))
        return ", ".join(flags) or "—"

    # ----- selection helpers -----
    def _project_row(self, item: Optional[QTreeWidgetItem]) -> Optional[Dict[str, Any]]:
        if item is None:
            return None
        data = item.data(0, KIND_ROLE)
        if not data or data[0] != "project":
            return None
        return self._row_by_key(item.data(0, KEY_ROLE))

    def _row_by_key(self, key: Optional[str]) -> Optional[Dict[str, Any]]:
        for row in self._rows():
            if row["key"] == key:
                return row
        return None

    def _folder_of(self, item: Optional[QTreeWidgetItem]) -> Optional[str]:
        if item is None:
            return None
        data = item.data(0, KIND_ROLE)
        if not data or data[0] != "folder":
            return None
        if isinstance(data[1], tuple) and len(data[1]) >= 2:
            return data[1][1] or None
        if isinstance(data[1], str) and data[1]:
            return data[1]
        return None

    def _on_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        row = self._project_row(item)
        if row:
            self._open(row["path"])

    def _on_grid_double_click(self, item: QListWidgetItem) -> None:
        row = self._row_by_key(item.data(KEY_ROLE))
        if row:
            self._open(row["path"])

    def _open(self, path: str) -> None:
        log_info(f"Project manager: opening {path}")
        self._open_project(path)
        self._closing_for_project = True  # the window closes for the project, not for the user: no quit
        try:
            self.close()
        finally:
            self._closing_for_project = False

    # ----- search and closing -----
    def _focus_search(self) -> None:
        self._search.setFocus()
        self._search.selectAll()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt's name
        """Esc clears the search while it has text; the next Esc closes the window."""
        if event.key() == Qt.Key.Key_Escape and self._search.text():
            self._search.clear()
            event.accept()
            return
        super().keyPressEvent(event)

    def done(self, result: int) -> None:
        """Every way to close the window ends here: the close button, Alt+F4, Esc (reject) and opening a project."""
        super().done(result)
        if not self._closing_for_project and self._on_closed is not None:
            self._on_closed()

    # ----- details -----
    def _on_expanded(self, item: QTreeWidgetItem) -> None:
        if item.childCount() == 0:
            return
        detail = item.child(0)
        if detail.data(0, DETAIL_ROLE) is None or self._tree.itemWidget(detail, 0) is not None:
            return
        row = self._project_row(item)
        if row:
            self._detail_signature[row["key"]] = repr(sorted((name, repr(value)) for name, value in row.items()))
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
        if row.get("images"):
            form.addRow(tr("Images it opens"), QLabel("\n".join(image_labels.summary_lines(row["images"]))))
        if row.get("source_roles"):
            roles = QLabel("\n".join(f"{role}: {path}" for role, path in row["source_roles"].items()))
            roles.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            roles.setWordWrap(True)
            form.addRow(tr("Source files"), roles)
        form.addRow(tr("Series glossary"), QLabel(series_summary(row.get("glossary_series"))))
        form.addRow(tr("Lines"), QLabel("—" if row["lines"] is None else f"{row['lines']:,}"))
        form.addRow(tr("Translated"), QLabel("—" if row["translated"] is None else f"{row['translated']} %"))
        form.addRow(tr("Blocks"), QLabel("—" if row["blocks"] is None else str(row["blocks"])))
        form.addRow(tr("Modified"), QLabel(format_modified(row["modified"])))
        form.addRow(tr("Added"), QLabel(format_modified(row["added"])))
        form.addRow(tr("Last opened"), QLabel(format_modified(row["last_opened"])))
        form.addRow(tr("Counted"), QLabel(format_modified(row["counted_at"])))
        layout.addLayout(form)

        layout.addWidget(self._resource_tree(row))
        if row["groups"]:
            tree = QTreeWidget()
            tree.setHeaderLabels([tr("Folder"), tr("Blocks"), tr("Lines")])
            for name in sorted(row["groups"], key=str.casefold):
                group = row["groups"][name]
                tree.addTopLevelItem(QTreeWidgetItem([name, str(group["blocks"]), f"{group['lines']:,}"]))
            tree.setMaximumHeight(150)
            layout.addWidget(tree)

        attention = [tr(ISSUE_TEXT[issue]) for issue in row["issues"] if issue in ISSUE_TEXT]
        if row["count_error"] and row["count_error"] != PLUGIN_MISSING:
            attention.append(tr("The lines could not be counted: {0}.", row["count_error"]))
        if row.get("missing_translations"):
            attention.append(tr("{0} blocks have no translation file yet.", row["missing_translations"]))
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
        change_icon = QPushButton(tr("Change icon..."))
        change_icon.clicked.connect(_call(self._icon_clicked, row))
        buttons.addWidget(change_icon)
        share_button = QPushButton(tr("Share project..."))
        share_button.clicked.connect(_call(self._share_clicked, row))
        buttons.addWidget(share_button)
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

    def _resource_tree(self, row: Dict[str, Any]) -> QTreeWidget:
        """The kinds of the project's source files. The files are counted on a worker the first time a row shows them."""
        key = row["key"]
        tree = QTreeWidget()
        tree.setHeaderLabels([tr("Resource"), tr("Files"), tr("Size")])
        tree.setRootIsDecorated(False)
        tree.setMaximumHeight(150)
        self._resource_trees[key] = tree
        if key in self._resource_cache:
            self._fill_resources(tree, self._resource_cache[key])
        else:
            self._show_resource_message(tree, tr("Counting the files..."))
            if key not in self._resource_jobs:
                self._start_resources(key, row["path"])
        return tree

    def _start_resources(self, key: str, project_file: str) -> None:
        job = ResourceJob(project_file, self._load_rules)
        self._resource_jobs[key] = job
        self._jobs.append(job)
        job.done.connect(lambda counts, k=key, j=job: self._resources_ended(k, j, counts))
        job.failed.connect(lambda _message, k=key, j=job: self._resources_ended(k, j, None))
        job.start()

    def _resources_ended(self, key: str, job: ResourceJob, counts: Optional[Dict[str, Dict[str, int]]]) -> None:
        self._forget(job)
        self._resource_jobs.pop(key, None)
        if counts is not None:
            self._resource_cache[key] = counts
        tree = self._resource_trees.get(key)
        if tree is None:
            return
        try:
            if counts is None:
                self._show_resource_message(tree, tr("The files could not be counted."))
            else:
                self._fill_resources(tree, counts)
        except RuntimeError:  # the row was drawn again, or the window closed, meanwhile
            pass

    @staticmethod
    def _show_resource_message(tree: QTreeWidget, text: str) -> None:
        tree.clear()
        tree.addTopLevelItem(QTreeWidgetItem([text, "", ""]))

    @staticmethod
    def _fill_resources(tree: QTreeWidget, counts: Dict[str, Dict[str, int]]) -> None:
        labels = {resources.TEXT: tr("Text files"), resources.FONT: tr("Font files"),
                  resources.TEXTURE: tr("Texture files"), resources.OTHER: tr("Other files")}
        tree.clear()
        for kind in resources.KINDS:
            bucket = counts.get(kind) or {}
            tree.addTopLevelItem(QTreeWidgetItem([labels[kind], f"{int(bucket.get('files', 0)):,}",
                                                  _size_text(int(bucket.get("bytes", 0)))]))

    def _action_button(self, label: str, mode: str, row: Dict[str, Any]) -> QToolButton:
        """A button that lists the plugin's build targets. Off when the game declares none."""
        button = QToolButton()
        button.setText(tr(label))
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        for target in row["targets"]:
            platform = emulator_platform(target["platforms"], row["platform"])
            action = menu.addAction(str(target["label"]))
            action.triggered.connect(_call(self._start_action, row["path"], target["id"], mode, platform))
            if mode == "run" and not self._emulator_template(platform):
                action.setEnabled(False)
                action.setToolTip(tr("Set the emulator command for this platform first (Emulator... button)."))
        button.setMenu(menu)
        if not row["targets"]:
            button.setEnabled(False)
            button.setToolTip(tr("This game declares no build target yet."))
        elif mode == "run" and not any(action.isEnabled() for action in menu.actions()):
            button.setEnabled(False)
            button.setToolTip(tr("Set the emulator command for this platform first (Emulator... button)."))
        return button

    @staticmethod
    def _reveal(path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def _flag_toggled(self, path: str, key: str, name: str, checked: bool) -> None:
        state = dict(self._flag_state.get(key) or {})
        state[name] = bool(checked)
        self._flag_state[key] = state
        self._save_flags(path, {name: bool(checked)})

    # ----- project icons -----
    def _icon_clicked(self, row: Dict[str, Any]) -> None:
        """Copy a user's picture to the project's icon.png, scaled. The scan picks the change up on its next run."""
        path, _filter = QFileDialog.getOpenFileName(
            self, tr("Choose an icon"), str(Path.home()),
            tr("Images") + f" ({IMAGE_FILTER});;" + tr("All files") + " (*)")
        if not path:
            return
        target = Path(row["path"]).parent / ICON_FILE_NAME
        job = BackgroundJob(save_user_icon, Path(path), target)
        job.done.connect(partial(self._on_icon_saved, row["key"]))
        job.failed.connect(lambda _message: self._status.setText(tr("The icon could not be saved.")))
        self._run(job, lambda _image: None)

    def _on_icon_saved(self, key: str, image: Optional[QImage]) -> None:
        if image is None:
            self._status.setText(tr("The icon could not be saved."))
            return
        self._icon_images[key] = image
        self._icons.pop(key, None)
        self._schedule_render()

    def _clear_icon_clicked(self, row: Dict[str, Any]) -> None:
        answer = QMessageBox.question(
            self, tr("Clear icon"),
            tr("Remove the icon file of this project? The game's own files are not touched."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        target = Path(row["path"]).parent / ICON_FILE_NAME
        job = BackgroundJob(_remove_file, target)
        job.done.connect(lambda _result, key=row["key"]: self._on_icon_cleared(key))
        job.failed.connect(lambda _message: self._status.setText(tr("The icon could not be removed.")))
        self._run(job, lambda _result: None)

    def _on_icon_cleared(self, key: str) -> None:
        self._icon_images.pop(key, None)
        self._icons.pop(key, None)
        self._schedule_render()

    # ----- build, export and run -----
    def _emulator_template(self, platform: str) -> str:
        return emulator_template_for(self._document.get("settings") or {}, platform)

    def _known_platforms(self) -> List[str]:
        """Every platform a build runs on, plus each stored emulator command, sorted. "" is a build with no platform
        (its target and project name none): its line appears only then, and its command is the shared one."""
        names = set()
        for row in self._rows():
            for target in row.get("targets") or []:
                names.add(emulator_platform(target.get("platforms") or [], row.get("platform") or ""))
        names.update(name[len(EMULATOR_PREFIX):] for name in self._document.get("settings") or {}
                     if name.startswith(EMULATOR_PREFIX))
        return sorted(names)

    def _emulator_clicked(self) -> None:
        dialog = EmulatorDialog(self, self._known_platforms(), self._document.get("settings") or {})
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        for name, value in dialog.changes().items():
            self._document.setdefault("settings", {})[name] = value
            self._save_setting(name, value)

    def _start_action(self, project_file: str, target_id: str, mode: str, platform: str = "") -> None:
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
        self._action_platform[key] = platform
        self._set_action_text(key, tr("Working..."))
        job.progress.connect(lambda percent, text, k=key: self._set_action_text(k, f"{text} ({percent} %)"))
        job.done.connect(lambda path, k=key, m=mode: self._on_action_done(k, m, path))
        job.cancelled.connect(lambda k=key: self._on_action_ended(k, tr("Cancelled.")))
        job.failed.connect(lambda message, k=key: self._on_action_ended(k, tr("Failed: {0}", message)))
        self._run(job, lambda _path: None)

    def _on_action_done(self, key: str, mode: str, path: str) -> None:
        self._action_jobs.pop(key, None)
        platform = self._action_platform.pop(key, "")
        if mode == "run":
            self._set_action_text(key, self._launch_emulator(path, platform))
        elif mode == "export":
            self._set_action_text(key, tr("Exported to {0}", path))
        else:
            warnings = build.read_warnings(path)
            if warnings:
                self._set_action_text(key, tr("Built: {0} ({1} warnings: {2})", path, len(warnings), warnings[0]))
            else:
                self._set_action_text(key, tr("Built: {0}", path))

    def _on_action_ended(self, key: str, text: str) -> None:
        self._action_jobs.pop(key, None)
        self._action_platform.pop(key, None)
        self._set_action_text(key, text)

    def _set_action_text(self, key: str, text: str) -> None:
        self._action_text[key] = text
        label = self._status_labels.get(key)
        if label is not None:
            label.setText(text)

    def _launch_emulator(self, path: str, platform: str = "") -> str:
        """Start the platform's emulator detached, with the path as argument. No shell is used."""
        argv = emulator_argv(self._emulator_template(platform), path)
        if not argv:
            return tr("Set the emulator command for this platform first (Emulator... button).")
        started, _pid = QProcess.startDetached(argv[0], argv[1:], build.emulator_working_dir(argv))
        if not started:
            return tr("The emulator did not start: {0}", argv[0])
        log_info(f"Started the emulator {argv[0]} with {path}.")
        return tr("Started the emulator with {0}", path)

    # ----- context menu and actions -----
    def _context_menu(self, view, position) -> None:
        if view is self._grid:
            item = self._grid.itemAt(position)
            row = self._row_by_key(item.data(KEY_ROLE)) if item is not None else None
            folder = None
        else:
            item = self._tree.itemAt(position)
            row = self._project_row(item)
            folder = self._folder_of(item)
        menu = QMenu(self)
        if row:
            self._menu_item(menu, tr("Open"), self._open, row["path"])
            self._menu_item(menu, tr("Show in folder"), self._reveal, row["path"])
            self._menu_item(menu, tr("Share project..."), self._share_clicked, row)
            menu.addSeparator()
            self._menu_item(menu, tr("Rename..."), self._rename_clicked, row)
            self._menu_item(menu, tr("Move to folder..."), self._move_clicked, row)
            self._menu_item(menu, tr("Change icon..."), self._icon_clicked, row)
            self._menu_item(menu, tr("Clear icon"), self._clear_icon_clicked, row)
            menu.addSeparator()
            self._menu_item(menu, tr("Remove from manager"), self._remove_clicked, row)
        elif folder:
            folder_entry = next((f for f in self._document["folders"] if f["id"] == folder), None)
            current_glossary = folder_entry.get("glossary_path") if folder_entry else None
            self._menu_item(menu, tr("Rename folder..."), self._rename_folder_clicked, folder)
            self._menu_item(menu, tr("Delete folder..."), self._delete_folder_clicked, folder)
            menu.addSeparator()
            if current_glossary:
                glossary_name = Path(current_glossary).stem
                info_action = menu.addAction(tr("Shared glossary: {name}", name=glossary_name))
                info_action.setEnabled(False)
                self._menu_item(menu, tr("Change shared glossary..."), self._link_folder_glossary_clicked, folder)
                self._menu_item(menu, tr("Unlink shared glossary"), self._unlink_folder_glossary_clicked, folder)
                self._menu_item(menu, tr("New shared glossary..."), self._new_folder_glossary_clicked, folder)
            else:
                self._menu_item(menu, tr("New shared glossary..."), self._new_folder_glossary_clicked, folder)
                self._menu_item(menu, tr("Link shared glossary..."), self._link_folder_glossary_clicked, folder)
        else:
            return
        menu.exec(view.viewport().mapToGlobal(position))

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
            open_file = self._open_project_file()
            self._mutate(partial(_op_move, path=row["path"], folder_id=folder_id or None, open_file=open_file))

    def _remove_clicked(self, row: Dict[str, Any]) -> None:
        answer = QMessageBox.question(
            self, tr("Remove from manager"),
            tr("Remove this project from the Project Manager?\n\nNo project file is deleted."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self._mutate(partial(_op_remove, path=row["path"], open_file=self._open_project_file()))

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
            open_file = self._open_project_file()
            self._mutate(partial(_op_delete_folder, folder_id=folder_id, open_file=open_file))

    def _open_project_file(self) -> Optional[str]:
        pm = getattr(self.parent(), "project_manager", None)
        return getattr(pm, "project_file_path", None)

    def _sync_open_project_if_needed(self) -> None:
        pm = getattr(self.parent(), "project_manager", None)
        open_file = getattr(pm, "project_file_path", None)
        project = getattr(pm, "project", None)
        if not pm or not open_file or not project:
            return
        key = registry.project_key(open_file)
        entry = next((p for p in self._document["projects"] if registry.project_key(p["path"]) == key), None)
        folder_id = entry.get("folder_id") if entry else None
        expected_glossary = None
        if folder_id:
            folder = next((f for f in self._document["folders"] if f["id"] == folder_id), None)
            expected_glossary = folder.get("glossary_path") if folder else None

        current = project.metadata.get(GROUP_METADATA_KEY)
        if expected_glossary == current:
            return

        if self._open_sync_job is not None:
            self._open_sync_job.requestInterruption()

        self._open_sync_token += 1
        current_token = self._open_sync_token
        target_file = str(Path(open_file).resolve())
        self._open_sync_file = target_file

        prev_glossary = current
        if expected_glossary:
            project.metadata[GROUP_METADATA_KEY] = expected_glossary
        else:
            project.metadata.pop(GROUP_METADATA_KEY, None)

        project.modified_at = datetime.now().isoformat()
        seq = next_project_sequence(open_file)
        job = OpenProjectSyncJob(open_file, expected_glossary, dict(project.metadata), request_seq=seq)
        self._open_sync_job = job

        def is_active() -> bool:
            if self._open_sync_token != current_token:
                return False
            cur_pm = getattr(self.parent(), "project_manager", None)
            cur_file = getattr(cur_pm, "project_file_path", None)
            if not cur_file or not same_project_file(cur_file, target_file):
                return False
            return True

        def on_done(managers: list, warnings: list) -> None:
            if not is_active():
                return
            glossary_handler = getattr(getattr(self.parent(), "translation_handler", None), "glossary_handler", None)
            if glossary_handler:
                glossary_handler.series_glossary_managers[:] = managers
                if getattr(glossary_handler, "dialog", None):
                    glossary_handler._attach_series_page()
            if warnings:
                msg = tr("Series glossaries loaded with warnings: {0}", "; ".join(warnings))
                self._status.setText(msg)
                log_warning(msg)

        def on_failed(err: str) -> None:
            if not is_active():
                return
            if prev_glossary is not None:
                project.metadata[GROUP_METADATA_KEY] = prev_glossary
            else:
                project.metadata.pop(GROUP_METADATA_KEY, None)
            msg = tr("Failed to save project with updated group glossary: {error}", error=err)
            self._status.setText(msg)
            log_error(msg)

        def on_cancelled() -> None:
            if not is_active():
                return
            if prev_glossary is not None:
                project.metadata[GROUP_METADATA_KEY] = prev_glossary
            else:
                project.metadata.pop(GROUP_METADATA_KEY, None)

        self._jobs.append(job)
        job.done.connect(on_done)
        job.done.connect(lambda _m, _w, j=job: self._forget(j))
        job.failed.connect(on_failed)
        job.failed.connect(lambda _msg, j=job: self._forget(j))
        job.cancelled.connect(on_cancelled)
        job.cancelled.connect(lambda j=job: self._forget(j))
        job.start()

    def _apply_folder_glossary(self, folder_id: str, glossary_path: Optional[str]) -> None:
        open_file = self._open_project_file()
        self._mutate(partial(_op_set_folder_glossary, folder_id=folder_id, glossary_path=glossary_path,
                             open_file=open_file))

    def _new_folder_glossary_clicked(self, folder_id: str) -> None:
        folder_entry = next((f for f in self._document["folders"] if f["id"] == folder_id), None)
        name = folder_entry["name"] if folder_entry else "group"
        target = prompt_new_shared_glossary(self, name)
        if not target:
            return
        job = GroupGlossaryFileJob("create", target)
        job.done.connect(lambda path: self._apply_folder_glossary(folder_id, path))
        job.failed.connect(lambda err: QMessageBox.warning(
            self, tr("Shared Glossary"), tr("Cannot create shared glossary: {error}", error=err)))
        self._run(job, lambda _p: None)

    def _link_folder_glossary_clicked(self, folder_id: str) -> None:
        source = prompt_link_shared_glossary(self)
        if not source:
            return
        self._status.setText(tr("Checking glossary format..."))
        job = InspectGlossaryJob(source)
        job.done.connect(lambda needs_conv: self._on_glossary_inspected(folder_id, source, needs_conv))
        job.failed.connect(lambda err: QMessageBox.warning(
            self, tr("Shared Glossary"), tr("Cannot read this glossary: {error}", error=err)))
        self._run(job, lambda _res: None)

    def _on_glossary_inspected(self, folder_id: str, source: Path, needs_conv: bool) -> None:
        self._status.setText("")
        overwrite = False
        collision_free = False
        if needs_conv:
            target_dir = series_dir()
            target_file = (target_dir / f"{source.stem}.json").resolve()
            norm_source = os.path.normcase(str(source.resolve()))
            norm_target = os.path.normcase(str(target_file))
            if norm_target == norm_source:
                collision_free = True
            elif target_file.exists():
                answer = QMessageBox.question(
                    self,
                    tr("Shared Glossary Exists"),
                    tr("A converted shared glossary named '{name}' already exists in {dir}.\n\nDo you want to replace it?",
                       name=target_file.name, dir=str(target_dir)),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    overwrite = True
                else:
                    return

        job = GroupGlossaryFileJob("link", source, overwrite=overwrite, collision_free=collision_free)
        job.done.connect(lambda path: self._apply_folder_glossary(folder_id, path))
        job.failed.connect(lambda err: QMessageBox.warning(
            self, tr("Shared Glossary"), tr("Cannot read this glossary: {error}", error=err)))
        self._run(job, lambda _p: None)

    def _unlink_folder_glossary_clicked(self, folder_id: str) -> None:
        folder_entry = next((f for f in self._document["folders"] if f["id"] == folder_id), None)
        name = folder_entry["name"] if folder_entry else ""
        if confirm_unlink_shared_glossary(self, name):
            self._apply_folder_glossary(folder_id, None)

    def _group_glossary_clicked(self) -> None:
        if not self._document["folders"]:
            QMessageBox.information(self, tr("Group glossary"), tr("Create a folder first."))
            return
        item = self._tree.currentItem()
        folder_id = self._folder_of(item)
        if not folder_id:
            row = self._project_row(item)
            if row and row.get("folder_id"):
                folder_id = row["folder_id"]
        if not folder_id:
            folders = [(f["name"], f["id"]) for f in self._document["folders"]]
            names = [name for name, _ in folders]
            choice, ok = QInputDialog.getItem(self, tr("Group glossary"),
                                              tr("Choose a folder to manage its shared glossary:"),
                                              names, 0, False)
            if not ok or not choice:
                return
            folder_id = folders[names.index(choice)][1]

        folder_entry = next((f for f in self._document["folders"] if f["id"] == folder_id), None)
        current_glossary = folder_entry.get("glossary_path") if folder_entry else None
        menu = QMenu(self)
        if current_glossary:
            glossary_name = Path(current_glossary).stem
            info = menu.addAction(tr("Shared glossary: {name}", name=glossary_name))
            info.setEnabled(False)
            self._menu_item(menu, tr("Change shared glossary..."), self._link_folder_glossary_clicked, folder_id)
            self._menu_item(menu, tr("Unlink shared glossary"), self._unlink_folder_glossary_clicked, folder_id)
            self._menu_item(menu, tr("New shared glossary..."), self._new_folder_glossary_clicked, folder_id)
        else:
            self._menu_item(menu, tr("New shared glossary..."), self._new_folder_glossary_clicked, folder_id)
            self._menu_item(menu, tr("Link shared glossary..."), self._link_folder_glossary_clicked, folder_id)
        menu.exec(QCursor.pos())

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
        before = {registry.project_key(p["path"]) for p in self._document["projects"]}
        before_glossaries = {f["id"]: f.get("glossary_path") for f in self._document.get("folders", [])}
        before_folders = {registry.project_key(p["path"]): p.get("folder_id") for p in self._document.get("projects", [])}
        self._document = document
        self._sync_open_project_if_needed()
        self._schedule_render()
        after = {registry.project_key(p["path"]) for p in document["projects"]}
        after_glossaries = {f["id"]: f.get("glossary_path") for f in document.get("folders", [])}
        after_folders = {registry.project_key(p["path"]): p.get("folder_id") for p in document.get("projects", [])}
        if after != before or before_glossaries != after_glossaries or before_folders != after_folders:
            self._start_scan()

    # ----- adding projects -----
    def _new_project_clicked(self) -> None:
        if not self._new_project():   # the wizard made no project
            return
        self._closing_for_project = True  # the new project opens in the main window: close without quitting
        try:
            self.close()
        finally:
            self._closing_for_project = False

    def _add_existing_clicked(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, tr("Add existing project"), str(Path.home()),
                                                    tr("Project files") + " (*.uiproj);;" + tr("All files") + " (*)")
        if path:
            self._add_project_file(path)

    def _add_project_file(self, path: str) -> None:
        job = BackgroundJob(_card_facts, path)
        job.done.connect(lambda facts, p=path: self._mutate(partial(_op_add, path=p, project_id=facts[0],
                                                                   platform=facts[1])))
        job.failed.connect(lambda _m: QMessageBox.warning(
            self, tr("Add existing project"), tr("This file is not a readable project.")))
        self._run(job, lambda _facts: None)

    # ----- sharing projects (core/project_library/share.py) -----
    def _share_clicked(self, row: Dict[str, Any]) -> None:
        name = (row.get("name") or Path(row["path"]).parent.parent.name or "project").strip()
        target, _filter = QFileDialog.getSaveFileName(self, tr("Share project"), str(Path.home() / f"{name}.zip"),
                                                      tr("Shared project") + " (*.zip)")
        if not target:
            return
        self._status.setText(tr("Packing the project..."))
        job = BackgroundJob(share.export_project, row["path"], target)
        job.done.connect(lambda manifest, t=target: self._on_shared(manifest, t))
        job.failed.connect(lambda message: QMessageBox.warning(self, tr("Share project"), message))
        self._run(job, lambda _manifest: None)

    def _on_shared(self, manifest: Dict[str, Any], target: str) -> None:
        self._status.setText(tr("Project packed: {0}", target))
        lines = [tr("The project is packed into {0}.", target),
                 tr("Translation files: {0}. Glossaries: {1}.", manifest["translation_files"], manifest["glossaries"]),
                 tr("The original game files are not in the package: the other person chooses their own."),
                 tr("Changes that are not saved in the editor are not in the package.")]
        if manifest["cleared"]:
            lines.append(tr("{0} paths outside the project folders were cleared. The other person sets them again.",
                            len(manifest["cleared"])))
        QMessageBox.information(self, tr("Share project"), "\n\n".join(lines))

    def _import_shared_clicked(self) -> None:
        package, _filter = QFileDialog.getOpenFileName(self, tr("Import shared project"), str(Path.home()),
                                                       tr("Shared project") + " (*.zip)")
        if not package:
            return
        job = BackgroundJob(share.read_manifest, package)
        job.done.connect(lambda manifest, p=package: self._import_shared_paths(p, manifest))
        job.failed.connect(lambda message: QMessageBox.warning(self, tr("Import shared project"), message))
        self._run(job, lambda _manifest: None)

    def _import_shared_paths(self, package: str, manifest: Dict[str, Any]) -> None:
        """Ask where the project goes and where this person's original game files are, then unpack it."""
        destination = QFileDialog.getExistingDirectory(
            self, tr("Folder for the project {0} (it gets the picoripi and translation folders)",
                     manifest.get("name", "")), str(Path.home()))
        if not destination:
            return
        title = tr("Your original game files (the sender used {0})", manifest.get("source_name") or "-")
        if manifest.get("is_directory_mode", True):
            source = QFileDialog.getExistingDirectory(self, title, destination)
        else:
            source, _filter = QFileDialog.getOpenFileName(self, title, destination)
        if not source:
            return
        self._status.setText(tr("Unpacking the shared project..."))
        job = BackgroundJob(share.import_package, package, destination, source)
        job.done.connect(self._on_shared_imported)
        job.failed.connect(lambda message: QMessageBox.warning(self, tr("Import shared project"), message))
        self._run(job, lambda _result: None)

    def _on_shared_imported(self, result: Dict[str, Any]) -> None:
        self._status.setText(tr("Shared project imported: {0}", result["project_file"]))
        self._add_project_file(result["project_file"])
        if result.get("cleared"):
            QMessageBox.information(self, tr("Import shared project"), tr(
                "{0} paths of the sender were cleared (fonts, references and similar). Set them again in the "
                "project settings if the project needs them.", len(result["cleared"])))

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
            open_file = self._open_project_file()
            self._mutate(partial(_op_import, items=dialog.chosen(), open_file=open_file))

    def closeEvent(self, event) -> None:
        self._scan.shutdown()
        for job in list(self._jobs):
            try:
                safe_shutdown_thread(job, None, 1000)
            except RuntimeError as exc:  # Qt deleted a job that had already finished
                log_debug(f"Project manager job was already gone at close: {exc}")
        self._jobs.clear()
        self._action_jobs.clear()
        super().closeEvent(event)


def _remove_file(path: Path) -> bool:
    """Delete one file if it exists (the project's icon). A worker runs this."""
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return True


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
