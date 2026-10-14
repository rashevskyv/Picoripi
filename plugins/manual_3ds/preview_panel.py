"""The live preview of the 3DS manual: the page of the selected string, drawn as the console's viewer draws it.

The panel shows the top screen (400 x 240) and the bottom screen (320 x 240) one below the other, with the
viewer's chrome (header with the page badge and title, scroll track, bottom bar). The page column runs through
both screens: the wheel and a drag scroll it. The Y button (the bottom bar, or the footer button) switches Large
and Small text.

The page is built the way the console build builds it: every paragraph's current text is laid out with the
owner's tools (manual.layout_for, manual.to_edits) and written into the page's own BCLYT files
(bclyt.rewrite); the files are then drawn by console_render exactly as the console draws them (the simulator),
so what the panel shows is what the card shows. Drawing runs in a QThread worker; the panel only paints.
"""
from __future__ import annotations

import copy
import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from PyQt6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from core.i18n import tr
from plugins.manual_3ds import console_render as cr
from plugins.manual_3ds import repo_tools
from plugins.manual_3ds import sim_screens as ss
from plugins.manual_3ds import simulator
from utils.atomic_io import atomic_write_json
from utils.constants import user_plugin_dir
from utils.logging_utils import log_warning
from utils.thread_utils import WorkerThread

PLUGIN_NAME = "manual_3ds"
SETTINGS_FILE = "preview.json"
CHROME_DIR = "chrome"         # <data>/plugins/manual_3ds/chrome: screenshot crops of the viewer's chrome (git-ignored)
TOP_SIZE = ss.TOP
BOTTOM_SIZE = ss.BOTTOM
BOTTOM_X = ss.CARD_X          # the bottom screen is centred under the top screen
SCROLL_STEP = 48.0            # pixels per wheel notch
DEBOUNCE_MS = 120
CACHE_SIZE = 8
WORKER_STOP_MS = 3000
Y_BUTTON_START = 180          # the Y label area of the bottom bar starts here (x, in card pixels)
PAGE_NUMBER = re.compile(r"Page_(\d+)_(large|small)")
DEFECT_RGBA = (255, 0, 0, 60)
MARKED_DEFECTS = ("over_edge", "wrapped", "over_picture", "over_frame")

_GROUPS_LOCK = threading.Lock()
_ARCHIVES: Dict[Tuple[str, str], Any] = {}
_FLOWS: Dict[Tuple[str, str], Dict[str, List[Any]]] = {}
_TEXTURES: Dict[Tuple[str, str], cr.Textures] = {}
_INDEXES: Dict[Tuple[str, str], cr.Index] = {}
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


@dataclass
class PagePreview:
    """What the worker hands the panel: the drawn column and chrome (as QImages), and what the render shows wrong."""

    column: QImage
    overlay: QImage
    column_height: int
    number: int                                        # the console's page number
    title: str
    defects: List[simulator.Defect] = field(default_factory=list)
    defect_keys: Dict[str, List[str]] = field(default_factory=dict)   # string key -> defect kinds
    failed_keys: Dict[str, str] = field(default_factory=dict)         # string key -> the layout error
    missing_glyphs: List[str] = field(default_factory=list)
    runs: List[cr.TextRun] = field(default_factory=list)

    @property
    def scroll_max(self) -> int:
        return ss.scroll_range(self.column_height)


class _Request:
    """What a worker draws: the folder, the manual, the page group and the texts. Plain data."""

    def __init__(self, root: str, manual_name: str, group: str, texts: Dict[str, str], budgets: Dict[str, Any],
                 title: str, save_root: str = ""):
        self.root = root
        self.manual_name = manual_name
        self.group = group
        self.texts = texts
        self.budgets = budgets
        self.title = title
        self.save_root = save_root  # a folder the user just chose: the worker stores it before drawing
        self.key = (root, manual_name, group, hash(tuple(sorted(texts.items()))), title)


def _archive_of(tools: Any, manual_name: str) -> Any:
    """The manual's archive, read once per folder. Called from the worker only."""
    key = (str(tools.root), manual_name)
    with _GROUPS_LOCK:
        if key not in _ARCHIVES:
            _ARCHIVES[key] = tools.bcma.load(repo_tools.manual_path(tools, manual_name))
        return _ARCHIVES[key]


def _flows_of(tools: Any, manual_name: str) -> Dict[str, List[Any]]:
    """The owner's paragraphs of every page ({"small/Page_003_small_0": [Flow, ...]}), once per manual."""
    key = (str(tools.root), manual_name)
    archive = _archive_of(tools, manual_name)
    with _GROUPS_LOCK:
        if key not in _FLOWS:
            _FLOWS[key] = tools.manual.pages_of(archive, tools.manual.BASE_SLOT)
        return _FLOWS[key]


def _textures_of(tools: Any, manual_name: str) -> cr.Textures:
    key = (str(tools.root), manual_name)
    archive = _archive_of(tools, manual_name)
    with _GROUPS_LOCK:
        if key not in _TEXTURES:
            files: Dict[str, bytes] = {}
            for member in ("Common_texture", f"{tools.manual.BASE_SLOT}_texture"):
                try:
                    files.update(archive.read(member))
                except KeyError:
                    pass
            _TEXTURES[key] = cr.Textures(files)
        return _TEXTURES[key]


def _index_of(tools: Any, manual_name: str) -> cr.Index:
    key = (str(tools.root), manual_name)
    archive = _archive_of(tools, manual_name)
    with _GROUPS_LOCK:
        if key not in _INDEXES:
            _INDEXES[key] = cr.read_index(archive.read(f"{tools.manual.BASE_SLOT}_index")["Index.bclyt"])
        return _INDEXES[key]


def _qimage(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    return QImage(rgba.tobytes("raw", "RGBA"), rgba.width, rgba.height, 4 * rgba.width, QImage.Format.Format_RGBA8888).copy()


class RenderCancelled(Exception):
    """The caller asked the render to stop."""


def build_page(tools: Any, archive: Any, flows_by_key: Dict[str, List[Any]], part: str, page: int, texts: Dict[str, str],
               budgets: Dict[str, Any], should_stop: Any) -> Tuple[List[bytes], Dict[str, str], Dict[str, str]]:
    """The page's BCLYT files with the current texts laid out on them, as the console build writes them.

    -> (files in draw order, pane name -> string key, string key -> layout error). A paragraph the owner's layout
    cannot place keeps the stored text (the console build would stop; the panel shows the page anyway).
    """
    manual = tools.manual
    slot = manual.BASE_SLOT
    files = archive.read(f"{slot}_{part}")
    widths = repo_tools.widths_of(tools)
    table = manual.load_homoglyphs()
    out: List[bytes] = []
    owners: Dict[str, str] = {}
    failed: Dict[str, str] = {}
    backdrop = files.get(f"Page_{page:03d}_{part}_bg.bclyt")
    if backdrop is not None:
        out.append(backdrop)
    prefix = f"Page_{page:03d}_{part}_"
    subs = sorted((name for name in files if name.startswith(prefix) and name[len(prefix):-6].isdigit()),
                  key=lambda name: int(name[len(prefix):-6]))
    for file_name in subs:
        if should_stop():
            raise RenderCancelled()
        data = files[file_name]
        page_key = f"{part}/{file_name.removesuffix('.bclyt')}"
        edits: Dict[str, Any] = {}
        for index, flow in enumerate(flows_by_key.get(page_key, [])):
            key = f"{page_key}#{index}"
            for pane in flow.panes:
                owners[pane.name] = key
            text = texts.get(key)
            if not text:
                continue
            try:
                # The build's own steps on a copy: mark_panes_out reassigns the copy's lines (the shared flow
                # keeps its panes for the next render).
                laid = copy.copy(flow)
                manual.mark_panes_out(laid, text)
                rendered = manual.apply_homoglyphs(text, table)
                budget = budgets.get(key)
                limit = (float(budget) if budget else cr.COLUMN_WIDTH) + manual.WIDTH_SLACK
                lines = manual.layout_for(rendered, laid, limit, widths)
                edits.update(manual.to_edits(lines, laid))
            except Exception as exc:  # the owner's layout refuses the text: the page keeps the stored text there
                failed[key] = repr(exc)
        out.append(tools.bclyt.rewrite(data, edits) if edits else data)
    return out, owners, failed


def draw_request(request: _Request, should_stop: Any) -> PagePreview:
    """The worker's job: build the page from the texts, draw it as the console does. Raises repo_tools.ToolsError."""
    root = request.root or load_folder()
    if not root:
        raise repo_tools.ToolsError(repo_tools.NO_FOLDER)
    tools = repo_tools.load_tools(root)
    font = repo_tools.load_font(tools)
    archive = _archive_of(tools, request.manual_name)
    flows = _flows_of(tools, request.manual_name)
    textures = _textures_of(tools, request.manual_name)
    index = _index_of(tools, request.manual_name)
    part, page_name = request.group.split("/", 1)
    page = int(page_name.split("_")[1])
    with _RENDER_LOCK:  # the owner's layout model keeps per-flow state; one page at a time
        files, owners, failed = build_page(tools, archive, flows, part, page, request.texts, request.budgets, should_stop)
    if not files:
        raise repo_tools.ToolsError(f"no {part} page {page} in the manual")
    renderer = cr.PageRenderer(textures, cr.Glyphs(font, tools.bcfnt))
    column = renderer.render(files)
    if should_stop():
        raise RenderCancelled()
    layouts = [cr.parse(data) for data in files]
    defects = simulator.defects_of(renderer.runs, sorted(renderer.missing), layouts, textures, request.manual_name,
                                   index.number_of(page), f"Page_{page:03d}", part)
    defect_keys: Dict[str, List[str]] = {}
    for defect in defects:
        key = owners.get(defect.pane)
        if key is not None:
            defect_keys.setdefault(key, []).append(defect.kind)
    title = request.title or index.title_of(page)
    pages = cr.page_numbers(archive.read(f"{tools.manual.BASE_SLOT}_{part}"), part)
    info = ss.PageInfo(index.number_of(page), title, index.category_of(page), has_previous=page - 1 in pages,
                       has_next=page + 1 in pages, large=(part == "large"))
    chrome = ss.Chrome.load(user_plugin_dir(PLUGIN_NAME) / CHROME_DIR)
    overlay = ss.overlay(info, chrome, renderer.glyphs)
    return PagePreview(_qimage(column), _qimage(overlay), column.height, info.number, title, defects, defect_keys, failed,
                       sorted(renderer.missing), renderer.runs)


class PageRenderWorker(WorkerThread):
    """Draws one request. ``rendered`` carries (generation, request key, PagePreview or an error message)."""

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
        except RenderCancelled:
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
        if point.y() >= ss.BOTTOM_BAR_ROW and point.x() >= BOTTOM_X + Y_BUTTON_START:
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
        self._result: Optional[PagePreview] = None
        self._message = ""
        self._generation = 0
        self._cache: "OrderedDict[Any, PagePreview]" = OrderedDict()
        self._workers: List[PageRenderWorker] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_render)
        self._page_file = ""
        self._current_key = ""

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
        card = QRectF(BOTTOM_X, 0, BOTTOM_SIZE[0], TOP_SIZE[1] + BOTTOM_SIZE[1])
        painter.fillRect(card, QColor(255, 255, 255))
        if self._result is None:
            painter.setPen(QColor(60, 60, 60))
            painter.drawText(QRectF(BOTTOM_X + 12, ss.PAGE_TOP + 12, BOTTOM_SIZE[0] - 24, ss.VISIBLE_ROWS - 24),
                             Qt.AlignmentFlag.AlignCenter.value | Qt.TextFlag.TextWordWrap.value,
                             self._message or tr("Select a string of a manual page."))
            return
        result = self._result
        top = ss.PAGE_TOP - cr.TOP_MARGIN_ROWS - self._scroll
        painter.drawImage(QPointF(BOTTOM_X, top), result.column, QRectF(0, 0, cr.COLUMN_WIDTH, result.column.height()))
        for defect in result.defects:
            if defect.kind in MARKED_DEFECTS:
                row = ss.PAGE_TOP - defect.page_y - self._scroll
                painter.fillRect(QRectF(BOTTOM_X, row, BOTTOM_SIZE[0], 20), QColor(*DEFECT_RGBA))
        painter.drawImage(QPointF(0, 0), result.overlay)
        # Ink past the card's edge lies over the scroll track on the top screen, as on the console.
        strip_top = ss.HEADER_ROWS + len(ss.HEADER_SHADOW)
        painter.drawImage(QRectF(BOTTOM_X + cr.COLUMN_WIDTH, strip_top, cr.OVERRUN, TOP_SIZE[1] - strip_top), result.column,
                          QRectF(cr.COLUMN_WIDTH, strip_top - top, cr.OVERRUN, TOP_SIZE[1] - strip_top))
        x0, y0, x1, y1 = ss.bar_rect(result.column_height, self._scroll)
        painter.fillRect(QRectF(x0 - 1, y0 - 1, x1 - x0 + 3, y1 - y0 + 3), QColor(*ss.BAR_OUTLINE))
        painter.fillRect(QRectF(x0, y0, x1 - x0 + 1, y1 - y0 + 1), QColor(*ss.BAR_FILL))

    def _clamped(self, value: float) -> float:
        if self._result is None:
            return 0.0
        return min(max(0.0, value), float(self._result.scroll_max))

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
        page_no = int(page.split("_")[1])
        title_index = self._rules.index_string_of_page(page_no)
        title = ""
        if title_index is not None:
            title = self._mw.data_processor.get_current_string_text(block, title_index)[0] or ""
        request = _Request(self._root, self._rules.manual_name(), group, texts, budgets, title, self._save_pending)
        self._save_pending = ""
        self._page_file = page
        self._current_key = string_key or ""
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
        self._message = text
        self._set_status(text)
        self._screens.update()

    def _show_result(self, result: PagePreview) -> None:
        self._result = result
        self._message = ""
        self._scroll = self._clamped(self._scroll)
        kinds = sorted({defect.kind for defect in result.defects})
        own = result.defect_keys.get(self._current_key, [])
        status = tr("Console page {0} (file {1}). {2} defect(s) on the render: {3}. Missing glyphs: {4}",
                    result.number, self._page_file, len(result.defects), ", ".join(kinds) or "-",
                    "".join(result.missing_glyphs) or "-")
        if own:
            status += " " + tr("This paragraph: {0}.", ", ".join(sorted(set(own))))
        if result.failed_keys:
            status += " " + tr("{0} paragraph(s) kept the stored text (the layout refused the translation).",
                               len(result.failed_keys))
        self._set_status(status)
        self._screens.update()

    def _choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, tr("Choose the repo_manual folder"), self._root or "")
        if not chosen:
            return
        self._root = chosen
        self._save_pending = chosen
        self._cache.clear()
        self.refresh()
