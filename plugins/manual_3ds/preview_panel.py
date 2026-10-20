"""The live preview of the 3DS manual: the page of the selected string, drawn as the console's viewer draws it.

The panel shows the top screen (400 x 240) and the bottom screen (320 x 240) one below the other, with the
viewer's chrome (header with the page badge and title, scroll track, bottom bar). The page column runs through
both screens: the wheel and a drag scroll it. The Y button (the bottom bar, or the footer button) switches Large
and Small text. A click (a press and release without a drag) on a paragraph selects its string in the editor.

The footer selector adds the original beside the translation: the Russian (ru) or the English (en) text of the same
page, drawn the same way, with the scroll, the large/small size and the selection shared by both canvases.

The page is built the way the console build builds it: every paragraph's current text is laid out with the
owner's tools (manual.layout_for, manual.to_edits) and written into the page's own BCLYT files
(bclyt.rewrite); the files are then drawn by console_render exactly as the console draws them (the simulator),
so what the panel shows is what the card shows. Drawing runs in a QThread worker; the panel only paints.
"""
from __future__ import annotations

import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Tuple

from PIL import Image
from PyQt6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
                             QWidget)

from core.i18n import tr
from plugins.manual_3ds import console_render as cr
from plugins.manual_3ds import repo_tools
from plugins.manual_3ds import sim_screens as ss
from plugins.manual_3ds import simulator
from plugins.manual_3ds.page_build import (PLUGIN_NAME, RENDER_LOCK, RenderCancelled, archive_of, build_page, flows_of,
                                           index_of, load_folder, save_folder, textures_of)
from utils.constants import user_plugin_dir
from utils.logging_utils import log_warning
from utils.thread_utils import WorkerThread, safe_shutdown_thread

CHROME_DIR = "chrome"         # <data>/plugins/manual_3ds/chrome: screenshot crops of the viewer's chrome (git-ignored)
TOP_SIZE = ss.TOP
BOTTOM_SIZE = ss.BOTTOM
BOTTOM_X = ss.CARD_X          # the bottom screen is centred under the top screen
SCROLL_STEP = 48.0            # pixels per wheel notch
DEBOUNCE_MS = 120
CACHE_SIZE = 16               # two canvases per selection: the translation and the original
WORKER_STOP_MS = 3000
Y_BUTTON_START = 180          # the Y label area of the bottom bar starts here (x, in card pixels)
CLICK_SLOP = 4.0              # widget pixels a press may move and still be a click
PAGE_NUMBER = re.compile(r"Page_(\d+)_(large|small)")
DEFECT_RGBA = (255, 0, 0, 60)
HIGHLIGHT_RGBA = (255, 200, 0, 70)   # the selected paragraph: a translucent fill ...
HIGHLIGHT_EDGE = (230, 120, 0)       # ... and an outline, both over the page column
HIGHLIGHT_WIDTH = 2.0                # outline width in canvas units
REVEAL_ROWS = 60                     # a paragraph scrolled into view starts a third of the way down the top screen
MARKED_DEFECTS = ("over_edge", "wrapped", "over_picture", "over_frame", "covered", "over_cell", "text_overlap")
TRANSLATION = "translation"   # the request's language of the translation, and the canvas that shows it
ORIGINAL = "original"         # the canvas of the original (its requests carry the language "ru" or "en")
NO_ORIGINAL = "none"          # the selector's value: one canvas, as before


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


def key_rect(runs: List[cr.TextRun], owners: Dict[str, str], key: str) -> Optional[QRectF]:
    """The drawn lines of one string key as one rect in content units: x is the page x, y is the distance below the
    text origin (``-top``). On the canvas the rect's top row is ``PAGE_TOP + y - scroll``. None when no line belongs
    to the key (a marker or picture paragraph, an empty translation)."""
    rect: Optional[QRectF] = None
    for run in runs:
        if owners.get(run.pane) != key:
            continue
        line = QRectF(run.ink_left, -run.top, run.ink_right - run.ink_left, run.height)
        rect = line if rect is None else rect.united(line)
    return rect


def paragraph_at(runs: List[cr.TextRun], owners: Dict[str, str], x: float, y: float) -> Optional[str]:
    """The string key of the drawn line under a point in content units (the inverse of key_rect), or None.

    Two lines may share the point (a label drawn beside the next paragraph's text): the one whose middle is nearest the
    point wins; at the same height the one drawn last is the one on top, and the one the user sees."""
    best: Optional[str] = None
    best_gap = float("inf")
    best_order = -1
    for run in runs:
        key = owners.get(run.pane)
        if key is None:
            continue
        top = -run.top
        if run.ink_left <= x <= run.ink_right and top <= y <= top + run.height:
            gap = abs(y - (top + run.height / 2))
            if gap < best_gap or (gap == best_gap and run.order > best_order):
                best, best_gap, best_order = key, gap, run.order
    return best


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
    owners: Dict[str, str] = field(default_factory=dict)              # pane name -> string key (what drew the pane)
    hints: Dict[str, str] = field(default_factory=dict)               # string key -> the fit numbers of its text

    @property
    def scroll_max(self) -> int:
        return ss.scroll_range(self.column_height)


def _no_name() -> str:
    return ""


def _no_budget(key: str) -> Optional[float]:
    return None


def _no_hint(key: str, text: str) -> str:
    return ""


class _Request:
    """What a worker draws: the folder, the manual, the page group, the texts and the language drawn.

    ``lang`` is TRANSLATION (the editor's texts) or "ru" / "en" (the original). ``block_name`` is the editor's name of
    the block (a project names it after the manual's file); when the tools do not know it, ``name_of`` gives the manual
    the plugin matched by the file's keys. ``name_of``, ``budget_of`` and ``hint_of`` may read the plugin's geometry
    once, so the worker calls them, not the UI thread. An original's key leaves out its texts: they do not change
    while the translation is edited, so the original is not drawn again for each edit.
    """

    def __init__(self, root: str, block_name: str, group: str, texts: Dict[str, str], title: str,
                 save_root: str = "", name_of: Callable[[], str] = _no_name,
                 budget_of: Callable[[str], Optional[float]] = _no_budget,
                 hint_of: Callable[[str, str], str] = _no_hint, lang: str = TRANSLATION):
        self.root = root
        self.block_name = block_name
        self.group = group
        self.texts = texts
        self.title = title
        self.save_root = save_root  # a folder the user just chose: the worker stores it before drawing
        self.name_of = name_of
        self.budget_of = budget_of
        self.hint_of = hint_of
        self.lang = lang
        judged = lang == TRANSLATION
        self.key = (lang, root, block_name, group, hash(tuple(sorted(texts.items()))) if judged else 0,
                    title if judged else "")


def _qimage(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    return QImage(rgba.tobytes("raw", "RGBA"), rgba.width, rgba.height, 4 * rgba.width, QImage.Format.Format_RGBA8888).copy()


def draw_request(request: _Request, should_stop: Any) -> PagePreview:
    """The worker's job: build the page from the texts, draw it as the console does. Raises repo_tools.ToolsError."""
    root = request.root or load_folder()
    if not root:
        raise repo_tools.ToolsError(repo_tools.NO_FOLDER)
    tools = repo_tools.load_tools(root)
    font = repo_tools.load_font(tools)
    # Two manuals can share one key list (face_raiders, face_raiders_n3ds): the block's own name picks the archive.
    manual_name = request.block_name if request.block_name in tools.manual.MANUALS else request.name_of()
    archive = archive_of(tools, manual_name)
    flows = flows_of(tools, manual_name)
    textures = textures_of(tools, manual_name)
    index = index_of(tools, manual_name)
    part, page_name = request.group.split("/", 1)
    page = int(page_name.split("_")[1])
    budgets = {key: request.budget_of(key) for key in request.texts}
    with RENDER_LOCK:  # the owner's layout model keeps per-flow state; one page at a time
        files, owners, failed = build_page(tools, archive, flows, part, page, request.texts, budgets, should_stop)
    if not files:
        raise repo_tools.ToolsError(f"no {part} page {page} in the manual")
    glyphs = cr.Glyphs(font, tools.bcfnt)
    rendered = simulator.render_page(files, textures, glyphs)
    column = rendered.column
    if should_stop():
        raise RenderCancelled()
    judged = request.lang == TRANSLATION   # the original is drawn for comparison: nothing of it is judged
    defects = (simulator.page_defects(rendered, textures, manual_name, index.number_of(page), f"Page_{page:03d}", part)
               if judged else [])
    defect_keys: Dict[str, List[str]] = {}
    for defect in defects:
        key = owners.get(defect.pane)
        if key is not None:
            defect_keys.setdefault(key, []).append(defect.kind)
    title = (request.title or index.title_of(page)) if judged else index.title_of(page)
    pages = cr.page_numbers(archive.read(f"{tools.manual.BASE_SLOT}_{part}"), part)
    info = ss.PageInfo(index.number_of(page), title, index.category_of(page), has_previous=page - 1 in pages,
                       has_next=page + 1 in pages, large=(part == "large"))
    chrome = ss.Chrome.load(user_plugin_dir(PLUGIN_NAME) / CHROME_DIR)
    overlay = ss.overlay(info, chrome, glyphs)
    hints = {key: request.hint_of(key, text) for key, text in request.texts.items() if text} if judged else {}
    return PagePreview(_qimage(column), _qimage(overlay), column.height, info.number, title, defects, defect_keys, failed,
                       rendered.missing, rendered.runs, owners, hints)


class PageRenderWorker(WorkerThread):
    """Draws one request. ``rendered`` carries (generation, request key, PagePreview or an error message)."""

    rendered = pyqtSignal(int, object, object)

    def __init__(self, generation: int, request: _Request, parent: Optional[QObject]):
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
    """One painted canvas: both screens, 400 x 480 px in canvas units, scaled to the space the panel gets.

    ``side`` is TRANSLATION or ORIGINAL: which result the owner paints here, and which one a click selects from."""

    def __init__(self, owner: "ManualPreviewPanel", side: str):
        super().__init__(owner)
        self._owner = owner
        self._side = side
        self._press: Optional[QPointF] = None         # the widget point of a press that may become a click or a drag
        self._press_canvas: Optional[QPointF] = None  # the same point on the canvas
        self._drag_y: Optional[float] = None
        self._moved = False
        self.setMinimumSize(200, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt name
        return QSize(TOP_SIZE[0], TOP_SIZE[1] + BOTTOM_SIZE[1])

    def _transform(self) -> Tuple[float, float, float]:
        """-> (scale, left, top) of the canvas inside the widget, keeping the aspect ratio."""
        canvas_h = TOP_SIZE[1] + BOTTOM_SIZE[1]
        ratio = self.devicePixelRatioF()
        fit = max(0.1, min(self.width() / TOP_SIZE[0], self.height() / canvas_h))
        # A whole number of device pixels per canvas pixel keeps the 3DS pixels crisp; a smaller space scales down.
        scale = (int(fit * ratio) / ratio) if fit * ratio >= 1.0 else fit
        left = round((self.width() - TOP_SIZE[0] * scale) / 2 * ratio) / ratio
        top = round((self.height() - canvas_h * scale) / 2 * ratio) / ratio
        return scale, left, top

    def _to_canvas(self, point: QPointF) -> QPointF:
        scale, left, top = self._transform()
        return QPointF((point.x() - left) / scale, (point.y() - top) / scale)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        try:
            scale, left, top = self._transform()
            # Whole-number zoom: nearest-neighbour keeps the console's pixels sharp; only a shrink is smoothed.
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, scale * self.devicePixelRatioF() < 1.0)
            painter.translate(left, top)
            painter.scale(scale, scale)
            self._owner.paint_screens(painter, self._side)
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
        self._press = event.position()
        self._press_canvas = point
        self._drag_y = point.y()
        self._moved = False

    def mouseMoveEvent(self, event: Any) -> None:
        if self._press is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        if not self._moved:
            if (event.position() - self._press).manhattanLength() <= CLICK_SLOP:
                return   # still a click: the page does not move yet
            self._moved = True
        point = self._to_canvas(event.position())
        self._owner.scroll_by(self._drag_y - point.y())
        self._drag_y = point.y()

    def mouseReleaseEvent(self, event: Any) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        if not self._moved and self._press_canvas is not None:
            self._owner.select_at(self._side, self._press_canvas)
        self._press = None
        self._press_canvas = None
        self._drag_y = None
        self._moved = False


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
        self._result: Optional[PagePreview] = None        # the translation
        self._original_result: Optional[PagePreview] = None
        self._message = ""
        self._original_message = ""
        self._generation = 0
        self._cache: "OrderedDict[Any, PagePreview]" = OrderedDict()
        self._workers: List[PageRenderWorker] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_render)
        self._page_file = ""
        self._current_key = ""
        self._block = -1                                  # the block of the page on the canvases (a click selects in it)
        self._source = NO_ORIGINAL
        self._highlight: Optional[QRectF] = None          # the selected paragraph's lines, in content units (key_rect)
        self._original_highlight: Optional[QRectF] = None
        self._deferred: List[_Request] = []               # the original's request, started when the translation is drawn

        self._screens = _Screens(self, TRANSLATION)
        self._original_screens = _Screens(self, ORIGINAL)
        self._original_screens.setVisible(False)
        self._source_box = QComboBox(self)
        self._source_box.addItem(tr("No original"), NO_ORIGINAL)
        self._source_box.addItem(tr("Original: Russian (ru)"), "ru")
        self._source_box.addItem(tr("Original: English (en)"), "en")
        self._source_box.currentIndexChanged.connect(self._source_changed)
        self._caption = QLabel(tr("Translation"), self)
        self._caption.setVisible(False)
        self._size_button = QPushButton(self)
        self._size_button.clicked.connect(self.toggle_size)
        self._folder_button = QPushButton(tr("Choose folder..."), self)
        self._folder_button.clicked.connect(self._choose_folder)
        self._status = QLabel(self)
        self._status.setWordWrap(True)
        selector = QHBoxLayout()
        selector.addWidget(self._source_box)
        selector.addStretch(1)
        selector.addWidget(self._caption)
        canvases = QHBoxLayout()
        canvases.setSpacing(4)
        canvases.addWidget(self._original_screens, 1)
        canvases.addWidget(self._screens, 1)
        footer = QHBoxLayout()
        footer.addWidget(self._size_button)
        footer.addWidget(self._folder_button)
        footer.addWidget(self._status, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(selector)
        layout.addLayout(canvases, 1)
        layout.addLayout(footer)
        self._update_buttons()

    # -- host interface ------------------------------------------------------------------------

    def refresh(self) -> None:
        """The editor selection or a text changed: redraw after a short pause."""
        self._timer.start(DEBOUNCE_MS)

    def update_preview_text(self, text: Any = None, original: Any = None) -> None:
        self.refresh()

    def shutdown(self) -> None:
        """Stop the workers and wait a bounded time for them. Call before the widget is deleted.

        A worker still loading the manual's files is parked (utils.thread_utils): it has no parent, so deleting the
        panel never destroys a running thread (Qt aborts the process then)."""
        self._timer.stop()
        for worker in self._workers:
            worker.cancel()
        # The problem scan's page render stops with the panel (close, plugin switch); after the cancels, so a preview
        # build holding page_build.RENDER_LOCK lets go of it first.
        self._rules.stop_scan_render()
        for worker in self._workers:
            safe_shutdown_thread(worker, worker, WORKER_STOP_MS)
        self._workers.clear()

    # -- what the canvases show ----------------------------------------------------------------

    def scroll_by(self, delta: float) -> None:
        self._scroll = self._clamped(self._scroll + delta)
        self._refresh_canvases()

    def toggle_size(self) -> None:
        self._large = not self._large
        self._scroll = 0.0
        self._update_buttons()
        self.refresh()

    def paint_screens(self, painter: QPainter, side: str = TRANSLATION) -> None:
        original = side == ORIGINAL
        result = self._original_result if original else self._result
        highlight = self._original_highlight if original else self._highlight
        message = self._original_message if original else self._message
        painter.fillRect(0, 0, TOP_SIZE[0], TOP_SIZE[1] + BOTTOM_SIZE[1], QColor(34, 34, 34))
        card = QRectF(BOTTOM_X, 0, BOTTOM_SIZE[0], TOP_SIZE[1] + BOTTOM_SIZE[1])
        painter.fillRect(card, QColor(255, 255, 255))
        if result is None:
            text = message or ("" if original else tr("Select a string of a manual page."))
            if text:
                painter.setPen(QColor(60, 60, 60))
                painter.drawText(QRectF(BOTTOM_X + 12, ss.PAGE_TOP + 12, BOTTOM_SIZE[0] - 24, ss.VISIBLE_ROWS - 24),
                                 Qt.AlignmentFlag.AlignCenter.value | Qt.TextFlag.TextWordWrap.value, text)
            return
        top = ss.PAGE_TOP - cr.TOP_MARGIN_ROWS - self._scroll
        painter.drawImage(QPointF(BOTTOM_X, top), result.column, QRectF(0, 0, cr.COLUMN_WIDTH, result.column.height()))
        if not original:
            for defect in result.defects:
                if defect.kind in MARKED_DEFECTS:
                    row = ss.PAGE_TOP - defect.page_y - self._scroll
                    painter.fillRect(QRectF(BOTTOM_X, row, BOTTOM_SIZE[0], 20), QColor(*DEFECT_RGBA))
        if highlight is not None:
            self._paint_highlight(painter, highlight)
        painter.drawImage(QPointF(0, 0), result.overlay)
        # Ink past the card's edge lies over the scroll track on the top screen, as on the console.
        strip_top = ss.HEADER_ROWS + len(ss.HEADER_SHADOW)
        painter.drawImage(QRectF(BOTTOM_X + cr.COLUMN_WIDTH, strip_top, cr.OVERRUN, TOP_SIZE[1] - strip_top), result.column,
                          QRectF(cr.COLUMN_WIDTH, strip_top - top, cr.OVERRUN, TOP_SIZE[1] - strip_top))
        x0, y0, x1, y1 = ss.bar_rect(result.column_height, self._scroll)
        painter.fillRect(QRectF(x0 - 1, y0 - 1, x1 - x0 + 3, y1 - y0 + 3), QColor(*ss.BAR_OUTLINE))
        painter.fillRect(QRectF(x0, y0, x1 - x0 + 1, y1 - y0 + 1), QColor(*ss.BAR_FILL))

    def _paint_highlight(self, painter: QPainter, rect: QRectF) -> None:
        """Outline the selected paragraph: the same transform as the page column (content y -> canvas row)."""
        canvas = QRectF(BOTTOM_X + rect.left(), ss.PAGE_TOP + rect.top() - self._scroll, rect.width(), rect.height())
        painter.fillRect(canvas, QColor(*HIGHLIGHT_RGBA))
        painter.save()
        painter.setPen(QPen(QColor(*HIGHLIGHT_EDGE), HIGHLIGHT_WIDTH))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(canvas)
        painter.restore()

    def select_at(self, side: str, point: QPointF) -> None:
        """A click on a canvas: the paragraph under it becomes the selected string, through the main window's
        selection (list_selection_handler.navigate_to_physical_string), so the history and the panels follow it.
        A click on the header, the bottom bar or a blank part of the page selects nothing."""
        result = self._original_result if side == ORIGINAL else self._result
        if result is None or point.y() < ss.PAGE_TOP or point.y() >= ss.BOTTOM_BAR_ROW:
            return
        key = paragraph_at(result.runs, result.owners, point.x() - BOTTOM_X, point.y() - ss.PAGE_TOP + self._scroll)
        index = self._rules.string_index_of(self._block, key) if key is not None else None
        if index is None:
            return
        self._mw.list_selection_handler.navigate_to_physical_string(self._block, index)

    def _reveal(self) -> None:
        """Scroll the selected paragraph into view. A paragraph whose top is in view stays where it is (no jump while
        the user edits it); a paragraph taller than the view is in view once its top is. The translation's outline
        decides; the original's serves when the translation draws none."""
        rect = self._highlight if self._highlight is not None else self._original_highlight
        if rect is None:
            return
        top, bottom = rect.top(), rect.bottom()
        top_in_view = self._scroll <= top < self._scroll + ss.VISIBLE_ROWS
        fits = bottom <= self._scroll + ss.VISIBLE_ROWS or bottom - top > ss.VISIBLE_ROWS
        if top_in_view and fits:
            return
        self._scroll = self._clamped(top - REVEAL_ROWS)

    def _clamped(self, value: float) -> float:
        sizes = [result.scroll_max for result in (self._result, self._original_result) if result is not None]
        if not sizes:
            return 0.0
        return min(max(0.0, value), float(max(sizes)))

    def _refresh_canvases(self) -> None:
        self._screens.update()
        self._original_screens.update()

    def _update_buttons(self) -> None:
        self._size_button.setText(tr("Show small text") if self._large else tr("Show large text"))

    def _set_status(self, text: str) -> None:
        self._status.setText(text)

    # -- requests -------------------------------------------------------------------------------

    def _source_changed(self, _index: int) -> None:
        """The selector chose the original: its canvas shows or hides, and the page is drawn again."""
        self._source = self._source_box.currentData() or NO_ORIGINAL
        shown = self._source != NO_ORIGINAL
        self._original_screens.setVisible(shown)
        self._caption.setVisible(shown)
        self._original_result = None
        self._original_highlight = None
        self._original_message = ""
        self.refresh()

    def _start_render(self) -> None:
        self._generation += 1
        ds = self._mw.data_store
        index = ds.current_string_idx
        block = ds.physical_block_idx if ds.physical_block_idx != -1 else ds.current_block_idx
        if block is None or block < 0 or index is None or index < 0:
            self._show_message(tr("Select a string of a manual page."))
            return
        if not self._rules.manual_loaded(block):
            self._show_message(tr("This manual is not read yet. The page is drawn when it is."))
            return
        string_key = self._rules.string_key(block, index)
        page = page_name_of(string_key) if string_key else None
        if page is None:
            self._show_message(tr("The index is not drawn here. Select a string of a page."))
            return
        # A newly selected string brings the view to its own size; the size button still shows the other size of
        # the same page until the selection changes.
        if string_key != self._current_key and string_key.startswith("large/") != self._large:
            self._large = not self._large
            self._scroll = 0.0
            self._update_buttons()
        part = "large" if self._large else "small"
        group = f"{part}/{page}_{part}"
        indices = self._rules.strings_of_group(block, group)
        texts = {key: self._mw.data_processor.get_current_string_text(block, i)[0] for key, i in indices.items()}
        page_no = int(page.split("_")[1])
        title_index = self._rules.index_string_of_page(block, page_no)
        title = ""
        if title_index is not None:
            title = self._mw.data_processor.get_current_string_text(block, title_index)[0] or ""
        block_name = str(ds.block_names.get(str(block), ""))
        name_of = partial(self._rules.manual_name, block)
        budget_of = partial(self._rules.preview_budget, block)
        hint_of = partial(self._rules.fit_hint, block)
        request = _Request(self._root, block_name, group, texts, title, self._save_pending, name_of, budget_of, hint_of)
        self._save_pending = ""
        self._page_file = page
        self._current_key = string_key or ""
        self._block = block
        requests = [request]
        if self._source == "ru":
            # The console's own Russian, as the page's files hold it: no text is laid out, so the lines are the console's.
            stored = {key: "" for key in indices}
            requests.append(_Request(self._root, block_name, group, stored, "", "", name_of, budget_of, hint_of, lang="ru"))
            self._original_message = ""
        elif self._source == "en":
            english = self._rules.english_texts(block, group)
            if any(english.values()):
                requests.append(_Request(self._root, block_name, group, english, "", "", name_of, budget_of, hint_of,
                                         lang="en"))
                self._original_message = ""
            else:
                self._original_result = None
                self._original_highlight = None
                self._original_message = tr("No English text on this page: it does not line up with the Russian.")
                self._original_screens.update()
        self._start_requests(requests)

    def _start_requests(self, requests: List[_Request]) -> None:
        """Show the cached requests now; start a worker for each other one (the running workers of an earlier
        selection stop first). The translation is drawn first: the original waits for its result, so the two renders
        do not share the processor and the translation shows as soon as it would alone."""
        pending: List[_Request] = []
        for request in requests:
            if request.key in self._cache:
                self._cache.move_to_end(request.key)
                self._apply(request.lang, self._cache[request.key])
            else:
                pending.append(request)
        self._deferred = []
        if not pending:
            return
        for worker in self._workers:
            worker.cancel()
        translation = [request for request in pending if request.lang == TRANSLATION]
        if translation:
            self._deferred = [request for request in pending if request.lang != TRANSLATION]
            self._launch(translation)
            self._set_status(tr("Drawing the page..."))
        else:
            self._launch(pending)

    def _launch(self, requests: List[_Request]) -> None:
        for request in requests:
            worker = PageRenderWorker(self._generation, request, None)  # no parent: see shutdown
            worker.rendered.connect(self._on_rendered)
            self._reap()  # before the append: the new worker does not run yet and would be dropped
            self._workers.append(worker)
            worker.start()

    def _apply(self, lang: str, result: PagePreview) -> None:
        if lang == TRANSLATION:
            self._show_result(result)
        else:
            self._show_original(result)

    def _on_rendered(self, generation: int, key: Any, payload: Any) -> None:
        self._reap()
        if generation != self._generation:
            return
        lang = key[0]
        if lang == TRANSLATION and self._deferred:
            deferred, self._deferred = self._deferred, []
            self._launch(deferred)
        if isinstance(payload, str):
            if payload == repo_tools.NO_FOLDER:
                payload = tr("Set the repo_manual folder to draw the page.")
            elif payload.startswith(repo_tools.NO_MANUAL):
                payload = tr("The repo_manual folder has no console files of the manual {0}, so its pages cannot be drawn.",
                             payload[len(repo_tools.NO_MANUAL):])
            elif payload.startswith("missing:") or payload.startswith("not a folder:"):
                payload = tr("Not a repo_manual folder: {0}", payload)
            if lang == TRANSLATION:
                self._show_message(payload)
            else:
                self._original_result = None
                self._original_highlight = None
                self._original_message = payload
                self._original_screens.update()
            return
        self._cache[key] = payload
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        self._apply(lang, payload)

    def _reap(self) -> None:
        self._workers = [worker for worker in self._workers if worker.isRunning()]

    def _show_message(self, text: str) -> None:
        self._result = None
        self._highlight = None
        self._original_result = None
        self._original_highlight = None
        self._original_message = ""
        self._message = text
        self._set_status(text)
        self._refresh_canvases()

    def _show_result(self, result: PagePreview) -> None:
        self._result = result
        self._message = ""
        self._scroll = self._clamped(self._scroll)
        # The selected string belongs to the drawn page only in its own size (a large key is not drawn in small text).
        drawn = self._current_key.startswith(("large" if self._large else "small") + "/")
        self._highlight = key_rect(result.runs, result.owners, self._current_key) if drawn else None
        self._reveal()
        kinds = sorted({defect.kind for defect in result.defects})
        own = result.defect_keys.get(self._current_key, [])
        status = tr("Console page {0} (file {1}). {2} defect(s) on the render: {3}. Missing glyphs: {4}",
                    result.number, self._page_file, len(result.defects), ", ".join(kinds) or "-",
                    "".join(result.missing_glyphs) or "-")
        if own:
            status += " " + tr("This paragraph: {0}.", ", ".join(sorted(set(own))))
        if drawn and self._highlight is None:
            status += " " + tr("This string draws no text on the page.")
        hint = result.hints.get(self._current_key, "")
        if hint:
            status += " " + hint
        if result.failed_keys:
            status += " " + tr("{0} paragraph(s) kept the stored text (the layout refused the translation).",
                               len(result.failed_keys))
        self._set_status(status)
        self._refresh_canvases()

    def _show_original(self, result: PagePreview) -> None:
        self._original_result = result
        self._original_message = ""
        self._scroll = self._clamped(self._scroll)
        drawn = self._current_key.startswith(("large" if self._large else "small") + "/")
        self._original_highlight = key_rect(result.runs, result.owners, self._current_key) if drawn else None
        self._reveal()
        self._refresh_canvases()

    def _choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, tr("Choose the repo_manual folder"), self._root or "")
        if not chosen:
            return
        self._root = chosen
        self._save_pending = chosen
        self._cache.clear()
        self.refresh()
