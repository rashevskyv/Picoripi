"""The live preview of a 3DS system string: its budget box, drawn with the console's system font.

The panel shows the box of the selected string (box.py) and a status line with the numbers: the widest line against
the width budget, the line count against the line budget, and the characters the font cannot draw. The font and the
widths come from the owner's repo_manual folder (the same folder the manual preview uses, set there). Drawing runs in
a QThread worker; the panel only paints the picture it gets back.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, List, Optional, Tuple

from PIL import Image
from PyQt6.QtCore import QObject, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from core.i18n import tr
from plugins.manual_3ds import console_render as cr
from plugins.manual_3ds import repo_tools
from plugins.manual_3ds.page_build import load_folder, save_folder
from plugins.system_3ds import box
from utils.logging_utils import log_warning
from utils.thread_utils import WorkerThread, safe_shutdown_thread

DEBOUNCE_MS = 120
CACHE_SIZE = 16
WORKER_STOP_MS = 3000


def _no_budget(_text: str) -> List[float]:
    return []


@dataclass
class _Request:
    """What a worker draws. ``line_widths_of`` reads widths.json once, so the worker calls it, not the UI thread."""

    root: str
    text: str
    width_budget: Optional[int]
    line_budget: Optional[int]
    save_root: str
    line_widths_of: Callable[[str], List[float]]

    @property
    def key(self) -> Tuple[str, str, Optional[int], Optional[int]]:
        return self.root, self.text, self.width_budget, self.line_budget


def draw_request(request: _Request, should_stop: Callable[[], bool]) -> Optional[box.BoxResult]:
    """Draw the box of one request; None when stopped. Raises repo_tools.ToolsError when the folder has no font."""
    root = request.root or load_folder()
    if not root:
        raise repo_tools.ToolsError(repo_tools.NO_FOLDER)
    tools = repo_tools.load_tools(root)
    font = repo_tools.load_font(tools)
    glyphs = cr.Glyphs(font, tools.bcfnt)
    widths = request.line_widths_of(request.text)
    if should_stop():
        return None
    return box.draw_box(request.text, widths, request.width_budget, request.line_budget, glyphs)


def _qimage(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    return QImage(rgba.tobytes("raw", "RGBA"), rgba.width, rgba.height, 4 * rgba.width,
                  QImage.Format.Format_RGBA8888).copy()


class BoxRenderWorker(WorkerThread):
    """Draws one request. ``rendered`` carries (generation, request key, BoxResult or an error message)."""

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
            try:
                save_folder(self._request.save_root)
            except OSError as exc:
                log_warning(f"system_3ds: the repo_manual folder was not saved: {exc!r}")
        result: Any = None
        try:
            result = draw_request(self._request, self._stop.is_set)
        except repo_tools.ToolsError as exc:
            result = str(exc)
        except Exception as exc:  # shown in the panel, never raised into the editor
            result = f"{exc!r}"
        if result is not None and not self._stop.is_set():
            self.rendered.emit(self._generation, self._request.key, result)


def status_text(result: box.BoxResult) -> str:
    """The status line: the numbers of the box, in plain words."""
    parts = []
    if result.width_budget is None:
        parts.append(tr("Widest line {0} px. No width budget for this string.", round(result.widest)))
    elif result.wide_lines:
        parts.append(tr("Line {0} is wider than the budget: {1} px, budget {2} px.",
                        ", ".join(str(number) for number in result.wide_lines), round(result.widest),
                        result.width_budget))
    else:
        parts.append(tr("Widest line {0} px, budget {1} px.", round(result.widest), result.width_budget))
    lines = len(result.line_widths)
    if result.line_budget is not None:
        if result.extra_lines:
            parts.append(tr("{0} lines, budget {1}: {2} past the budget.", lines, result.line_budget,
                            result.extra_lines))
        else:
            parts.append(tr("{0} lines, budget {1}.", lines, result.line_budget))
    if result.missing:
        parts.append(tr("Missing glyphs: {0}", "".join(result.missing)))
    return " ".join(parts)


class SystemPreviewPanel(QWidget):
    """The preview widget the system_3ds plugin hands to the main window (GameRules.get_custom_preview_widget)."""

    def __init__(self, main_window: Any, rules: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._rules = rules
        self._root = ""            # read by the worker from the user's settings, so the UI thread does no disk I/O
        self._save_pending = ""    # a folder the user chose; the next worker stores it
        self._image: Optional[QImage] = None
        self._generation = 0
        self._cache: "OrderedDict[Any, box.BoxResult]" = OrderedDict()
        self._workers: List[BoxRenderWorker] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_render)

        self._canvas = _Canvas(self)
        self._folder_button = QPushButton(tr("Choose folder..."), self)
        self._folder_button.clicked.connect(self._choose_folder)
        self._status = QLabel(self)
        self._status.setWordWrap(True)
        footer = QHBoxLayout()
        footer.addWidget(self._folder_button)
        footer.addWidget(self._status, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._canvas, 1)
        layout.addLayout(footer)
        self._set_message(tr("Select a string of a 3DS system menu."))

    # -- host interface ------------------------------------------------------------------------

    def refresh(self) -> None:
        """The editor selection or a text changed: redraw after a short pause."""
        self._timer.start(DEBOUNCE_MS)

    def update_preview_text(self, text: Any = None, original: Any = None) -> None:
        self.refresh()

    def shutdown(self) -> None:
        """Stop the workers and wait a bounded time for them. Call before the widget is deleted."""
        self._timer.stop()
        for worker in self._workers:
            worker.cancel()
        for worker in self._workers:
            safe_shutdown_thread(worker, worker, WORKER_STOP_MS)
        self._workers.clear()

    # -- requests -------------------------------------------------------------------------------

    def _start_render(self) -> None:
        self._generation += 1
        ds = self._mw.data_store
        index = ds.current_string_idx
        block = ds.physical_block_idx if ds.physical_block_idx != -1 else ds.current_block_idx
        if block is None or block < 0 or index is None or index < 0 or not self._rules.string_key(block, index):
            self._set_message(tr("Select a string of a 3DS system menu."))
            return
        text = self._mw.data_processor.get_current_string_text(block, index)[0] or ""
        request = _Request(self._root, text, self._rules.budget(block, index), self._rules.line_budget(block, index),
                           self._save_pending, partial(self._rules.line_widths_of))
        self._save_pending = ""
        if request.key in self._cache:
            self._cache.move_to_end(request.key)
            self._show_result(self._cache[request.key])
            return
        for worker in self._workers:
            worker.cancel()
        worker = BoxRenderWorker(self._generation, request, None)  # no parent: see shutdown
        worker.rendered.connect(self._on_rendered)
        self._reap()  # before the append: the new worker does not run yet and would be dropped
        self._workers.append(worker)
        self._status.setText(tr("Drawing the box..."))
        worker.start()

    def _on_rendered(self, generation: int, key: Any, payload: Any) -> None:
        self._reap()
        if generation != self._generation:
            return
        if isinstance(payload, str):
            if payload == repo_tools.NO_FOLDER:
                payload = tr("Set the repo_manual folder to draw the page.")
            self._set_message(payload)
            return
        self._cache[key] = payload
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        self._show_result(payload)

    def _reap(self) -> None:
        self._workers = [worker for worker in self._workers if worker.isRunning()]

    def _set_message(self, text: str) -> None:
        self._image = None
        self._status.setText(text)
        self._canvas.update()

    def _show_result(self, result: box.BoxResult) -> None:
        self._image = _qimage(result.image)
        self._status.setText(status_text(result))
        self._canvas.update()

    def _choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, tr("Choose the repo_manual folder"), self._root or "")
        if not chosen:
            return
        self._root = chosen
        self._save_pending = chosen
        self._cache.clear()
        self.refresh()


class _Canvas(QWidget):
    """Paints the box scaled to the space the panel gets, keeping the aspect ratio."""

    def __init__(self, owner: SystemPreviewPanel):
        super().__init__(owner)
        self._owner = owner
        self.setMinimumSize(200, 80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor(236, 236, 236))
            image = self._owner._image
            if image is None or image.width() < 1:
                return
            scale = min(self.width() / image.width(), self.height() / image.height(), 4.0)
            width, height = image.width() * scale, image.height() * scale
            target = QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)
            painter.drawImage(target, image)
        finally:
            painter.end()
