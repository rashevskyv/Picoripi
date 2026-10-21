"""The dialogue window preview of Lunar (GameRules.get_custom_preview_widget): the game's window, portrait and font.

The program's font and the portrait files are read in a worker thread; the widget only draws what the pure
logic in ``dialogue_preview`` returns. Portrait colours come from the project's ``portrait_colours.json`` when it
exists; other indices use ``PEO.PAL``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.i18n import tr
from plugins.common.switch_message_preview import source_folder
from utils.thread_utils import WorkerThread, safe_shutdown_thread

from . import dialogue_preview as dp
from . import portrait_colours as pc

WORKER_STOP_MS = 2000
ZOOM = 2
PALETTE_FILE = "PEO.PAL"


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

    def __init__(self, project_dir: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._project_dir = project_dir

    def run(self) -> None:
        try:
            result: Any = load_sources(self._project_dir)
        except (OSError, ValueError) as error:
            result = str(error)
        self.loaded.emit((self._project_dir, result))


class LunarDialoguePreview(QWidget):
    """The message window of the selected text in the game's font, with its portrait (GameRules hook)."""

    def __init__(self, main_window: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._text = ""
        self._page = 0
        self._sources: Optional[Dict[str, Any]] = None
        self._loader: Optional[SourceLoader] = None
        self._source_key = ""
        self._picture = QLabel(self)
        self._picture.setMinimumSize(320 * ZOOM, 240 * ZOOM)
        self._picture.setToolTip(tr("Portrait colours come from portrait_colours.json when the project has it; other indices use PEO.PAL."))
        self._prev = QPushButton(tr("Previous page"), self)
        self._next = QPushButton(tr("Next page"), self)
        self._prev.clicked.connect(lambda: self._turn(-1))
        self._next.clicked.connect(lambda: self._turn(1))
        self._page_label = QLabel(self)
        self._speaker = QLabel(self)
        self._status = QLabel(self)
        self._status.setWordWrap(True)
        buttons = QHBoxLayout()
        buttons.addWidget(self._prev)
        buttons.addWidget(self._page_label, 1)
        buttons.addWidget(self._next)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._picture, 1)
        layout.addLayout(buttons)
        layout.addWidget(self._speaker)
        layout.addWidget(self._status)
        self._start_load()

    # -- host interface -------------------------------------------------------------------

    def refresh(self) -> None:
        self._render()

    def update_preview_text(self, text: Any = None, original: Any = None) -> None:
        if text is not None:
            self._text = str(text)
            self._page = 0
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
            self._status.setText(tr("Open a game project to see the message window."))
            return
        if project_dir == self._source_key:
            return
        self._source_key = project_dir
        self._sources = None
        self._loader = SourceLoader(project_dir)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()
        self._status.setText(tr("Reading the game font and portraits..."))

    def _on_loaded(self, payload: Any) -> None:
        project_dir, result = payload
        if project_dir != self._source_key:
            return
        if isinstance(result, str):
            self._status.setText(tr("The game's font or portrait files are not in this project: {0}").format(result))
            return
        if result["palette"] is None:
            result["palette"] = [(v, v, v) for v in range(256)]
            self._status.setText(tr("The portrait palette file is missing; portraits are drawn in grey."))
        self._sources = result
        self._render()

    # -- drawing ----------------------------------------------------------------------------

    def _turn(self, step: int) -> None:
        self._page += step
        self._render()

    def _render(self) -> None:
        if self._sources is None:
            return
        layout = dp.parse_pages(self._text)
        if not layout.pages or not layout.pages[0]:
            self._picture.clear()
            self._speaker.clear()
            self._page_label.setText("")
            self._status.setText(tr("The text has no line to draw."))
            return
        self._page = min(max(self._page, 0), len(layout.pages) - 1)
        page = layout.pages[self._page]
        face = page[0].face
        portrait = None
        if face:
            portrait = dp.face_picture(self._sources["files"], self._sources["index"], face,
                                       self._sources["palette"], self._sources["colours"])
        image = dp.render_page(page, self._sources["glyphs"], portrait).convert("RGBA")
        self._picture.setPixmap(self._pixmap(image))
        self._page_label.setText(tr("Page {0} of {1}").format(self._page + 1, len(layout.pages)))
        name = dp.speaker_name(face) if face else None
        self._speaker.setText(tr("Speaker: {0}").format(name) if name else "")
        problems = list(layout.problems)
        self._status.setText("\n".join(problems))
        self._prev.setEnabled(self._page > 0)
        self._next.setEnabled(self._page < len(layout.pages) - 1)

    @staticmethod
    def _pixmap(image) -> QPixmap:
        raw = image.tobytes("raw", "RGBA")
        qimage = QImage(raw, image.width, image.height, image.width * 4, QImage.Format.Format_RGBA8888).copy()
        return QPixmap.fromImage(qimage).scaled(image.width * ZOOM, image.height * ZOOM)
