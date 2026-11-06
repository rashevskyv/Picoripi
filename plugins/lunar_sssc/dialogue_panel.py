"""The dialogue window preview of Lunar (GameRules.get_custom_preview_widget): the game's window, portrait and font.

The program's font and the portrait files are read in a worker thread; the widget only draws what the pure
logic in ``dialogue_preview`` returns. Portrait colours come from the plugin's ``face_palettes.json``; the
project's ``portrait_colours.json``, when it exists, overrides them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from core.i18n import tr
from plugins.common.switch_message_preview import source_folder
from ui.components.bfn_preview.helpers import _preview_icon
from utils.thread_utils import WorkerThread, safe_shutdown_thread

from . import dialogue_preview as dp
from . import portrait_colours as pc

WORKER_STOP_MS = 2000
PALETTE_FILE = "PEO.PAL"
STRIP_HEIGHT = 28
# The dark strip and bar of the BFN preview (ui/components/bfn_preview/chrome.py, BfnPreviewWindowBar).
BAR_STYLE = (
    "QFrame {"
    "  background: #181818;"
    "  border: 1px solid #2a2a2a;"
    "  border-radius: 4px;"
    "}"
    "QPushButton {"
    "  background: #1e1e1e;"
    "  color: #cccccc;"
    "  border: 1px solid #3a3a3a;"
    "  border-radius: 4px;"
    "}"
    "QPushButton:hover { background: #2d2d2d; color: #ffffff; }"
    "QLabel { color: #c8c8c8; font-size: 11px; border: none; background: transparent; }"
)


class ScaledPicture(QLabel):
    """A picture that fills its space, scaled both ways with its aspect kept and the pixels kept sharp."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._source = QPixmap()
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_picture(self, pixmap: QPixmap) -> None:
        self._source = pixmap
        self._fit()

    def clear_picture(self) -> None:
        self._source = QPixmap()
        self.clear()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        if self._source.isNull():
            return
        self.setPixmap(self._source.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.FastTransformation))


def load_sources(project_dir: str) -> Dict[str, Any]:
    """Glyphs, face members and palette of a project's source folder (reads only)."""
    source = source_folder(project_dir)
    if not source:
        raise ValueError("no source folder")
    root = Path(source)
    glyphs = dp.decode_glyphs((root / "SLUS_006.28").read_bytes())
    folder = root / "LUNADATA"
    files = {path.name: path.read_bytes() for path in sorted(folder.glob("FACE_*.TIZ"))}
    palette_path = folder / PALETTE_FILE
    palette = dp.palette_from_file(palette_path.read_bytes()) if palette_path.is_file() else None
    colours = pc.read_colours(Path(project_dir) / pc.COLOURS_FILE)
    return {"glyphs": glyphs, "files": files, "index": dp.index_faces(files), "palette": palette,
            "colours": colours}


class SourceLoader(WorkerThread):
    """Reads the sources of a project in a worker. ``loaded`` carries (project folder, payload or error text)."""

    loaded = pyqtSignal(object)

    def __init__(self, project_dir: str, read: Optional[Callable[[str], Dict[str, Any]]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._project_dir = project_dir
        self._read = read or load_sources

    def run(self) -> None:
        try:
            result: Any = self._read(self._project_dir)
        except (OSError, ValueError) as error:
            result = str(error)
        self.loaded.emit((self._project_dir, result))


class LunarDialoguePreview(QWidget):
    """The message window of the selected text in the game's font, with its portrait (GameRules hook).

    ``read_sources`` reads a project's glyphs and portraits in the worker; another Lunar plugin swaps it.
    """

    @staticmethod
    def read_sources(project_dir: str) -> Dict[str, Any]:
        return load_sources(project_dir)

    def __init__(self, main_window: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._text = ""
        self._page = 0
        self._sources: Optional[Dict[str, Any]] = None
        self._loader: Optional[SourceLoader] = None
        self._source_key = ""
        self._picture = ScaledPicture(self)
        # Same structure as the BFN preview (ui/components/bfn_preview/chrome.py): a dark strip on top with the
        # title, the picture, and a dark bar at the bottom with the < > page arrows and the page count.
        self._strip = QFrame(self)
        self._strip.setObjectName("lunar_preview_strip")
        self._strip.setFixedHeight(STRIP_HEIGHT)
        self._strip.setStyleSheet(BAR_STYLE)
        self._speaker = QLabel(self._strip)          # the one speaker name, shown in the strip
        self._speaker.setAlignment(Qt.AlignmentFlag.AlignCenter)
        strip_layout = QHBoxLayout(self._strip)
        strip_layout.setContentsMargins(6, 2, 6, 2)
        strip_layout.addWidget(self._speaker)
        self._bar = QFrame(self)
        self._bar.setObjectName("lunar_preview_bar")
        self._bar.setFixedHeight(STRIP_HEIGHT)
        self._bar.setStyleSheet(BAR_STYLE)
        self._prev = QPushButton(self._bar)
        self._next = QPushButton(self._bar)
        for button, kind, tip in ((self._prev, "prev", "Previous page"), (self._next, "next", "Next page")):
            button.setFixedSize(24, 22)
            button.setIcon(_preview_icon(kind, 12))
            button.setIconSize(QSize(12, 12))
            button.setToolTip(tr(tip))
        self._prev.clicked.connect(lambda: self._turn(-1))
        self._next.clicked.connect(lambda: self._turn(1))
        self._page_label = QLabel(self._bar)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar_layout = QHBoxLayout(self._bar)
        bar_layout.setContentsMargins(6, 2, 6, 2)
        bar_layout.setSpacing(4)
        bar_layout.addStretch(1)
        bar_layout.addWidget(self._prev)
        bar_layout.addWidget(self._page_label)
        bar_layout.addWidget(self._next)
        bar_layout.addStretch(1)
        self._status = QLabel(self)
        self._status.setWordWrap(True)
        self._status.hide()                          # shown only while there is a message to show
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._strip)
        layout.addWidget(self._picture, 1)
        layout.addWidget(self._bar)
        layout.addWidget(self._status)
        self._start_load()

    # -- host interface -------------------------------------------------------------------

    def refresh(self) -> None:
        # The widget can be built before the project folder is known (a plugin loaded at startup); a later
        # refresh is then the first chance to read the sources.
        self._start_load()
        self._render()

    def update_preview_text(self, text: Any = None, original: Any = None) -> None:
        if text is not None:
            self._text = str(text)
            self._page = 0
        self._start_load()
        self._render()

    def shutdown(self) -> None:
        if self._loader is not None:
            safe_shutdown_thread(self._loader, self._loader, WORKER_STOP_MS)
            self._loader = None

    # -- loading ----------------------------------------------------------------------------

    def _project_dir(self) -> Optional[str]:
        manager = getattr(self._mw, "project_manager", None)
        path = getattr(manager, "project_dir", None)
        return str(path) if path else None

    def _start_load(self) -> None:
        project_dir = self._project_dir()
        if not project_dir:
            self._show_status(tr("Open a game project to see the message window."))
            return
        if project_dir == self._source_key:
            return
        self._source_key = project_dir
        self._sources = None
        self._loader = SourceLoader(project_dir, self.read_sources)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()
        self._show_status(tr("Reading the game font and portraits..."))

    def _on_loaded(self, payload: Any) -> None:
        project_dir, result = payload
        if project_dir != self._source_key:
            return
        if isinstance(result, str):
            self._show_status(tr("The game's font or portrait files are not in this project: {0}").format(result))
            return
        if result["palette"] is None:
            result["palette"] = [(v, v, v) for v in range(256)]
            self._show_status(tr("The portrait palette file is missing; portraits are drawn in grey."))
        self._sources = result
        self._render()

    # -- drawing ----------------------------------------------------------------------------

    def _show_status(self, text: str) -> None:
        """A message line under the page row; an empty text takes no room."""
        self._status.setText(text)
        self._status.setVisible(bool(text))

    def _turn(self, step: int) -> None:
        self._page += step
        self._render()

    def _render(self) -> None:
        if self._sources is None:
            return
        layout = dp.parse_pages(self._text)
        if not layout.pages or not layout.pages[0]:
            self._picture.clear_picture()
            self._speaker.clear()
            self._page_label.setText("")
            self._show_status(tr("The text has no line to draw."))
            return
        self._page = min(max(self._page, 0), len(layout.pages) - 1)
        page = layout.pages[self._page]
        face = page[0].face
        pictures = [dp.face_picture(self._sources["files"], self._sources["index"], number,
                                    self._sources["palette"], self._sources["colours"]) if number else None
                    for number in (page[0].left, page[0].right)]
        image = dp.render_page(page, self._sources["glyphs"], pictures[0], pictures[1]).convert("RGBA")
        self._picture.set_picture(self._pixmap(image))
        self._page_label.setText(tr("Page {0} of {1}").format(self._page + 1, len(layout.pages)))
        name = dp.speaker_name(face) if face else None
        if name:
            self._speaker.setText(name)
        else:
            self._speaker.setText(tr("Speaker code {0}").format(f"{face:02X}") if face else "")
        problems = list(layout.problems)
        self._show_status("\n".join(problems))
        self._prev.setEnabled(self._page > 0)
        self._next.setEnabled(self._page < len(layout.pages) - 1)

    @staticmethod
    def _pixmap(image) -> QPixmap:
        raw = image.tobytes("raw", "RGBA")
        qimage = QImage(raw, image.width, image.height, image.width * 4, QImage.Format.Format_RGBA8888).copy()
        return QPixmap.fromImage(qimage)
