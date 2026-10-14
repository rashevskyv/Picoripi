"""The live preview of the 3DS manual: the page of the selected string, drawn like the console's viewer.

The panel shows the top screen (400 x 240) and the bottom screen (320 x 240) one below the other. The page
column runs through both: the wheel and a drag scroll it. The Y button (the bottom bar, or the footer button)
switches Large and Small text. Every paragraph of the page is drawn from the current translation text, so a
change in the editor shows here after a short pause. Drawing runs in a QThread worker; the panel only paints.
"""
from __future__ import annotations

import json
import re
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from core.i18n import tr
from plugins.manual_3ds import page_render, pictures, repo_tools
from utils.atomic_io import atomic_write_json
from utils.constants import user_plugin_dir
from utils.logging_utils import log_warning
from utils.thread_utils import WorkerThread

PLUGIN_NAME = "manual_3ds"
SETTINGS_FILE = "preview.json"
TOP_SIZE = (400, 240)
BOTTOM_SIZE = (320, 240)
BOTTOM_X = 40                 # the bottom screen is centred under the top screen
TAB_BAR = 24                  # the page tab bar at the top of the top screen
BADGE_RGB = (117, 183, 217)   # the light blue page-number badge of the console's title bar (sampled from the calibration shot)
BADGE_TOP = 5.0
BADGE_SIZE = 28.0
BADGE_FONT_PX = 17
TITLE_FONT_PX = 16
BOTTOM_BAR = 40               # the Back / Enlarge bar at the bottom of the bottom screen
VISIBLE_HEIGHT = (TOP_SIZE[1] - TAB_BAR) + (BOTTOM_SIZE[1] - BOTTOM_BAR)
SCROLL_STEP = 48.0            # pixels per wheel notch
DEBOUNCE_MS = 120
CACHE_SIZE = 8
WORKER_STOP_MS = 3000
Y_BUTTON_START = 200          # the Y label area of the bottom bar starts here (x, in canvas pixels)
PAGE_NUMBER = re.compile(r"Page_(\d+)_(large|small)")

_GROUPS_LOCK = threading.Lock()
_GROUPS: Dict[Tuple[str, str], Dict[str, List[Any]]] = {}
_ARCHIVES: Dict[Tuple[str, str], Any] = {}
_BANKS: Dict[Tuple[str, str], Any] = {}
_RENDER_LOCK = threading.Lock()


def load_folder() -> str:
    """The repo_manual folder the user chose, or "" (per user, outside the repository)."""
    try:
        data = json.loads((user_plugin_dir(PLUGIN_NAME) / SETTINGS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    value = data.get("repo_manual", "") if isinstance(data, dict) else ""
    return value if isinstance(value, str) else ""


def save_folder(folder: str) -> None:
    target = user_plugin_dir(PLUGIN_NAME)
    target.mkdir(parents=True, exist_ok=True)
    atomic_write_json(target / SETTINGS_FILE, {"repo_manual": folder}, indent=2, ensure_ascii=False)


def _persist_folder(folder: str) -> None:
    """Store the chosen folder. Called from the render worker: the disk write stays off the UI thread."""
    try:
        save_folder(folder)
    except OSError as exc:
        log_warning(f"manual_3ds: the repo_manual folder was not saved: {exc!r}")


def page_name_of(string_key: str) -> Optional[str]:
    """"small/Page_003_small_1#4" -> "Page_003", or None for an index entry."""
    match = PAGE_NUMBER.search(string_key.split("#", 1)[0])
    return match.group(0).rsplit("_", 1)[0] if match else None


class _Request:
    """What a worker draws: the folder, the manual, the page group and the texts. Plain data."""

    def __init__(self, root: str, manual_name: str, group: str, texts: Dict[str, str], budgets: Dict[str, Any],
                 save_root: str = ""):
        self.root = root
        self.manual_name = manual_name
        self.group = group
        self.texts = texts
        self.budgets = budgets
        self.save_root = save_root  # a folder the user just chose: the worker stores it before drawing
        self.key = (root, manual_name, group, hash(tuple(sorted(texts.items()))))


def _archive_of(tools: Any, manual_name: str) -> Any:
    """The manual's archive, read once per folder. Called from the worker only."""
    key = (str(tools.root), manual_name)
    with _GROUPS_LOCK:
        if key not in _ARCHIVES:
            _ARCHIVES[key] = tools.bcma.load(repo_tools.manual_path(tools, manual_name))
        return _ARCHIVES[key]


def _groups_of(tools: Any, manual_name: str) -> Dict[str, List[Any]]:
    key = (str(tools.root), manual_name)
    archive = _archive_of(tools, manual_name)
    with _GROUPS_LOCK:
        if key not in _GROUPS:
            _GROUPS[key] = page_render.groups_of(tools, archive)
        return _GROUPS[key]


def _bank_of(tools: Any, manual_name: str) -> Any:
    """The decoded textures of the manual, kept across renders of the same folder (one worker at a time)."""
    key = (str(tools.root), manual_name)
    archive = _archive_of(tools, manual_name)
    with _GROUPS_LOCK:
        if key not in _BANKS:
            _BANKS[key] = pictures.TextureBank(archive, f"{tools.manual.BASE_SLOT}_texture")
        return _BANKS[key]


def draw_request(request: _Request, should_stop: Any) -> page_render.ColumnRender:
    """The worker's job: decode the page (cached per folder) and draw its column. Raises repo_tools.ToolsError."""
    root = request.root or load_folder()
    if not root:
        raise repo_tools.ToolsError(repo_tools.NO_FOLDER)
    tools = repo_tools.load_tools(root)
    font = repo_tools.load_font(tools)
    groups = _groups_of(tools, request.manual_name)
    bank = _bank_of(tools, request.manual_name)
    widths = repo_tools.widths_of(tools)
    homoglyphs = tools.manual.load_homoglyphs()
    with _RENDER_LOCK:  # the layout model keeps per-flow state; one drawing at a time
        return page_render.render_column(tools, font, widths, homoglyphs, groups, request.group,
                                         request.texts, request.budgets, should_stop, bank=bank)


class PageRenderWorker(WorkerThread):
    """Draws one request. ``rendered`` carries (generation, request key, ColumnRender or an error message)."""

    rendered = pyqtSignal(int, object, object)

    def __init__(self, generation: int, request: _Request, parent: QObject):
        super().__init__(parent)
        self._generation = generation
        self._request = request
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        if self._request.save_root:
            _persist_folder(self._request.save_root)
        try:
            result: Any = draw_request(self._request, self._stop.is_set)
        except page_render.RenderCancelled:
            return
        except repo_tools.ToolsError as exc:
            result = str(exc)
        except Exception as exc:  # shown in the panel, never raised into the editor
            result = f"{exc!r}"
        if not self._stop.is_set():
            self.rendered.emit(self._generation, self._request.key, result)


class _Screens(QWidget):
    """The painted canvas: both screens, 400 x 480 px in canvas units, scaled to the space the panel gets."""

    def __init__(self, owner: "ManualPreviewPanel"):
        super().__init__(owner)
        self._owner = owner
        self._drag_y: Optional[float] = None
        self.setMinimumSize(200, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt name
        return QSize(TOP_SIZE[0], TOP_SIZE[1] + BOTTOM_SIZE[1])

    def _transform(self) -> Tuple[float, float, float]:
        """-> (scale, left, top) of the canvas inside the widget, keeping the aspect ratio."""
        canvas_h = TOP_SIZE[1] + BOTTOM_SIZE[1]
        scale = max(0.1, min(self.width() / TOP_SIZE[0], self.height() / canvas_h))
        return scale, (self.width() - TOP_SIZE[0] * scale) / 2, (self.height() - canvas_h * scale) / 2

    def _to_canvas(self, point: QPointF) -> QPointF:
        scale, left, top = self._transform()
        return QPointF((point.x() - left) / scale, (point.y() - top) / scale)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        try:
            scale, left, top = self._transform()
            painter.translate(left, top)
            painter.scale(scale, scale)
            self._owner.paint_screens(painter)
        finally:
            painter.end()

    def wheelEvent(self, event: Any) -> None:
        self._owner.scroll_by(-event.angleDelta().y() / 120.0 * SCROLL_STEP)
        event.accept()

    def mousePressEvent(self, event: Any) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = self._to_canvas(event.position())
        if point.y() >= TOP_SIZE[1] + BOTTOM_SIZE[1] - BOTTOM_BAR and point.x() >= Y_BUTTON_START:
            self._owner.toggle_size()
            return
        self._drag_y = point.y()

    def mouseMoveEvent(self, event: Any) -> None:
        if self._drag_y is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        point = self._to_canvas(event.position())
        self._owner.scroll_by(self._drag_y - point.y())
        self._drag_y = point.y()

    def mouseReleaseEvent(self, event: Any) -> None:
        self._drag_y = None


class ManualPreviewPanel(QWidget):
    """The preview widget the manual_3ds plugin hands to the main window (see GameRules.get_custom_preview_widget)."""

    def __init__(self, main_window: Any, rules: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._rules = rules
        self._root = ""  # read from the user's settings by the worker, so the UI thread does no disk I/O
        self._save_pending = ""  # a folder the user chose; the next render worker stores it
        self._large = True
        self._scroll = 0.0
        self._result: Optional[page_render.ColumnRender] = None
        self._message = ""
        self._generation = 0
        self._cache: "OrderedDict[Any, page_render.ColumnRender]" = OrderedDict()
        self._workers: List[PageRenderWorker] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_render)
        self._page_number = ""
        self._tab_title = ""

        self._screens = _Screens(self)
        self._size_button = QPushButton(self)
        self._size_button.clicked.connect(self.toggle_size)
        self._folder_button = QPushButton(tr("Choose folder..."), self)
        self._folder_button.clicked.connect(self._choose_folder)
        self._status = QLabel(self)
        self._status.setWordWrap(True)
        footer = QHBoxLayout()
        footer.addWidget(self._size_button)
        footer.addWidget(self._folder_button)
        footer.addWidget(self._status, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._screens, 1)
        layout.addLayout(footer)
        self._update_buttons()

    # -- host interface ------------------------------------------------------------------------

    def refresh(self) -> None:
        """The editor selection or a text changed: redraw after a short pause."""
        self._timer.start(DEBOUNCE_MS)

    def update_preview_text(self, text: Any = None, original: Any = None) -> None:
        self.refresh()

    def shutdown(self) -> None:
        """Stop the worker and wait a bounded time for it. Call before the widget is deleted."""
        self._timer.stop()
        for worker in self._workers:
            worker.cancel()
        for worker in self._workers:
            worker.wait(WORKER_STOP_MS)
        self._workers.clear()

    # -- what the canvas shows ----------------------------------------------------------------

    def scroll_by(self, delta: float) -> None:
        self._scroll = self._clamped(self._scroll + delta)
        self._screens.update()

    def toggle_size(self) -> None:
        self._large = not self._large
        self._scroll = 0.0
        self._update_buttons()
        self.refresh()

    def paint_screens(self, painter: QPainter) -> None:
        painter.fillRect(0, 0, TOP_SIZE[0], TOP_SIZE[1] + BOTTOM_SIZE[1], QColor(34, 34, 34))
        top = QRectF(0, 0, TOP_SIZE[0], TOP_SIZE[1])
        bottom = QRectF(BOTTOM_X, TOP_SIZE[1], BOTTOM_SIZE[0], BOTTOM_SIZE[1])
        painter.fillRect(top, QColor(*page_render.PAPER_RGB))
        painter.fillRect(QRectF(0, 0, BOTTOM_X, TOP_SIZE[1]), QColor(96, 96, 96))
        painter.fillRect(QRectF(BOTTOM_X + BOTTOM_SIZE[0], 0, BOTTOM_X, TOP_SIZE[1]), QColor(96, 96, 96))
        painter.fillRect(bottom, QColor(*page_render.PAPER_RGB))
        if self._result is not None:
            upper = QRectF(BOTTOM_X, TAB_BAR, BOTTOM_SIZE[0], TOP_SIZE[1] - TAB_BAR)
            lower = QRectF(BOTTOM_X, TOP_SIZE[1], BOTTOM_SIZE[0], BOTTOM_SIZE[1] - BOTTOM_BAR)
            upper_rows = TOP_SIZE[1] - TAB_BAR
            painter.drawImage(upper, self._result.image, QRectF(0, self._scroll, BOTTOM_SIZE[0], upper_rows))
            painter.drawImage(lower, self._result.image,
                              QRectF(0, self._scroll + upper_rows, BOTTOM_SIZE[0], BOTTOM_SIZE[1] - BOTTOM_BAR))
        else:
            painter.setPen(QColor(60, 60, 60))
            painter.drawText(QRectF(BOTTOM_X + 12, TAB_BAR + 12, BOTTOM_SIZE[0] - 24, VISIBLE_HEIGHT - 24),
                             Qt.AlignmentFlag.AlignCenter.value | Qt.TextFlag.TextWordWrap.value,
                             self._message or tr("Select a string of a manual page."))
        self._paint_tab_bar(painter)
        bar = QRectF(BOTTOM_X, TOP_SIZE[1] + BOTTOM_SIZE[1] - BOTTOM_BAR, BOTTOM_SIZE[0], BOTTOM_BAR)
        painter.fillRect(bar, QColor(44, 44, 44))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRectF(BOTTOM_X + 60, bar.top(), 120, BOTTOM_BAR),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), tr("Back"))
        painter.drawText(QRectF(BOTTOM_X + Y_BUTTON_START - 40, bar.top(), 160, BOTTOM_BAR),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                         tr("Y  Small text") if self._large else tr("Y  Large text"))

    def _clamped(self, value: float) -> float:
        if self._result is None:
            return 0.0
        return min(max(0.0, value), max(0.0, self._result.height - VISIBLE_HEIGHT))

    def _paint_tab_bar(self, painter: QPainter) -> None:
        """The title bar: the page number in a blue badge, then the page's title (its Index entry, translated)."""
        painter.fillRect(QRectF(BOTTOM_X, 0, BOTTOM_SIZE[0], TAB_BAR), QColor(255, 255, 255))
        if not self._page_number:
            return
        painter.save()
        try:
            badge = QRectF(BOTTOM_X, BADGE_TOP, BADGE_SIZE, BADGE_SIZE)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(*BADGE_RGB))
            painter.drawRoundedRect(badge, 3, 3)
            font = painter.font()
            font.setPixelSize(BADGE_FONT_PX)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), self._page_number)
            font.setPixelSize(TITLE_FONT_PX)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor(0, 0, 0))
            title = QRectF(BOTTOM_X + BADGE_SIZE + 10, BADGE_TOP, BOTTOM_SIZE[0] - BADGE_SIZE - 16, BADGE_SIZE)
            painter.drawText(title, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self._tab_title)
        finally:
            painter.restore()

    def _update_buttons(self) -> None:
        self._size_button.setText(tr("Show small text") if self._large else tr("Show large text"))

    def _set_status(self, text: str) -> None:
        self._status.setText(text)

    # -- requests -------------------------------------------------------------------------------

    def _start_render(self) -> None:
        self._generation += 1
        ds = self._mw.data_store
        index = ds.current_string_idx
        block = ds.physical_block_idx if ds.physical_block_idx != -1 else ds.current_block_idx
        if block is None or block < 0 or index is None or index < 0:
            self._show_message(tr("Select a string of a manual page."))
            return
        string_key = self._rules.string_key(index)
        page = page_name_of(string_key) if string_key else None
        if page is None:
            self._show_message(tr("The index is not drawn here. Select a string of a page."))
            return
        part = "large" if self._large else "small"
        group = f"{part}/{page}_{part}"
        indices = self._rules.strings_of_group(group)
        texts = {key: self._mw.data_processor.get_current_string_text(block, i)[0] for key, i in indices.items()}
        budgets = {key: self._rules.preview_budget(key) for key in indices}
        request = _Request(self._root, self._rules.manual_name(), group, texts, budgets, self._save_pending)
        self._save_pending = ""
        page_no = int(page.split("_")[1])
        # The badge shows the printed page number: the file Page_002 is page 3 (checked on the calibration shot).
        self._page_number = str(page_no + 1)
        title_index = self._rules.index_string_of_page(page_no)
        self._tab_title = ""
        if title_index is not None:
            self._tab_title = self._mw.data_processor.get_current_string_text(block, title_index)[0] or ""
        if request.key in self._cache:
            self._cache.move_to_end(request.key)
            self._show_result(self._cache[request.key])
            return
        for worker in self._workers:
            worker.cancel()
        worker = PageRenderWorker(self._generation, request, self)
        worker.rendered.connect(self._on_rendered)
        self._workers.append(worker)
        self._reap()
        self._set_status(tr("Drawing the page..."))
        worker.start()

    def _on_rendered(self, generation: int, key: Any, payload: Any) -> None:
        self._reap()
        if generation != self._generation:
            return
        if isinstance(payload, str):
            if payload == repo_tools.NO_FOLDER:
                payload = tr("Set the repo_manual folder to draw the page.")
            elif payload.startswith("missing:") or payload.startswith("not a folder:"):
                payload = tr("Not a repo_manual folder: {0}", payload)
            self._show_message(payload)
            return
        self._cache[key] = payload
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        self._show_result(payload)

    def _reap(self) -> None:
        self._workers = [worker for worker in self._workers if worker.isRunning()]

    def _show_message(self, text: str) -> None:
        self._result = None
        self._page_number = ""  # no page is drawn: the title bar must not show the last page's badge
        self._tab_title = ""
        self._message = text
        self._set_status(text)
        self._screens.update()

    def _show_result(self, result: page_render.ColumnRender) -> None:
        self._result = result
        self._message = ""
        self._scroll = self._clamped(self._scroll)
        over = len(result.overflow_keys)
        missing = "".join(sorted(result.missing_glyphs))
        self._set_status(tr("{0} paragraph(s) over the line width. Missing glyphs: {1}", over, missing or "-"))
        self._screens.update()

    def _choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, tr("Choose the repo_manual folder"), self._root or "")
        if not chosen:
            return
        self._root = chosen
        self._save_pending = chosen
        self._cache.clear()
        self.refresh()
