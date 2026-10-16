"""The dialogue box of a Switch Pokémon game (``msg_00.bflyt``) drawn with the game's own layout and font.

The source folder comes from the project file (``metadata.source_path``, as the build reads it). The layout and the
fonts are read on a worker thread (AGENTS rule 5). The widget draws the page on the UI thread: a few lines of text.
Each text pane of the layout takes one line of the page. A line wider than its pane, or a page with more lines than
the box has panes, is reported under the preview.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QWidget

from core.containers.sarc import Sarc
from core.i18n import tr
from plugins.common import flyt_message as fm
from plugins.common.message_window import split_pages
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread

SCALE = 1.0
LAYOUT = "bin/appli/msg/bin/msg_00.arc"
LAYOUT_MEMBER = "blyt/msg_00.bflyt"
FCPX_MEMBER = "fcpx/system54_jpn.bfcpx"
FONT_DIR = "bin/font"
WINDOW_BG = (238, 240, 242, 255)     # the window texture is not read yet: a flat light box stands in for it
_MARGIN = 10


def source_folder(project_dir: str) -> Optional[str]:
    """The unpacked source folder of a project: ``metadata.source_path`` of its ``.uiproj`` file (None if absent)."""
    folder = Path(project_dir)
    project = next(iter(sorted(folder.glob("*.uiproj"))), None)
    if project is None:
        return None
    data = json.loads(project.read_text(encoding="utf-8"))
    source = str((data.get("metadata") or {}).get("source_path") or "")
    if not source:
        return None
    path = Path(source)
    if not path.is_absolute():
        path = project.parent / path
    return str(path)


def font_files(font_dir: Path, names: List[str]) -> List[Path]:
    """The scrambled font files of a layout's font names, in fallback order. Raises if one is missing."""
    out = []
    for name in names:
        path = _font_file(font_dir, name)
        if path is None:
            raise FileNotFoundError(f"font {name} is not in {font_dir}")
        out.append(path)
    return out


def sibling_layout_exists(project_dir: str) -> bool:
    """A cheap check for the host hook (UI thread): the dialogue layout sits in the ``source`` folder next to the
    project's own folder. Arceus has no such layout, so it keeps the BFN preview."""
    return (Path(project_dir).parent / "source" / LAYOUT).is_file()


def _font_file(font_dir: Path, name: str) -> Optional[Path]:
    """The scrambled font file of an ``.otf`` name in the game's font folder (BFOTF, any case)."""
    stem = name.rsplit(".", 1)[0].lower()
    for path in font_dir.iterdir():
        if path.suffix.lower() in (".bfotf", ".bfttf") and path.stem.lower() == stem:
            return path
    return None


class LayoutLoader(WorkerThread):
    """Reads the dialogue layout and its fonts. ``loaded`` carries ``(project folder, (layout, chain) or None)``."""

    loaded = pyqtSignal(object)

    def __init__(self, project_dir: str):
        super().__init__()
        self._project_dir = project_dir
        self._source_dir = ""
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        result: Any = None
        try:
            self._source_dir = source_folder(self._project_dir) or ""
            if not self._source_dir:
                raise FileNotFoundError("the project file has no source folder")
            root = Path(self._source_dir)
            arc = Sarc((root / LAYOUT).read_bytes())
            layout = fm.read_layout(arc.files[LAYOUT_MEMBER], arc.files[FCPX_MEMBER])
            faces = [fm.Face.from_bfotf(path.read_bytes()) for path in font_files(root / FONT_DIR, layout.fonts)]
            result = (layout, fm.FontChain(faces))
        except (OSError, ValueError, KeyError, IndexError, FileNotFoundError) as exc:
            log_debug(f"switch message preview: no dialogue layout for {self._source_dir}: {exc}")
        if not self._stop.is_set():
            self.loaded.emit((self._project_dir, result))


class SwitchMessagePreview(QWidget):
    """The dialogue box of the project (see GameRules.get_custom_preview_widget)."""

    def __init__(self, main_window: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._text = ""
        self._note = ""
        self._loaded: Optional[Tuple[fm.MessageLayout, fm.FontChain]] = None
        self._loader: Optional[LayoutLoader] = None
        self._source = ""
        self._image: Optional[QImage] = None
        self.setMinimumHeight(140)
        self._start_load()

    # -- host interface -------------------------------------------------------------------

    def refresh(self) -> None:
        self._render()

    def update_preview_text(self, text: object = None, original: object = None) -> None:
        self._text = text if isinstance(text, str) else ""
        self._render()

    def shutdown(self) -> None:
        if self._loader is not None:
            self._loader.cancel()
            self._loader = None
        self._loaded = None

    # -- loading --------------------------------------------------------------------------

    def _start_load(self) -> None:
        project_dir = getattr(getattr(self._mw, "project_manager", None), "project_dir", None)
        if not project_dir:
            self._note = tr("No project folder: the dialogue box needs the unpacked game.")
            return
        self._source = str(project_dir)
        self._loader = LayoutLoader(self._source)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()
        self._note = tr("Reading the game layout...")

    def _on_loaded(self, payload: object) -> None:
        project_dir, result = payload
        if project_dir != self._source:
            return
        if result is None:
            self._note = tr("The dialogue layout is not in this project's unpacked game.")
            return
        self._loaded = result
        self._render()

    # -- drawing --------------------------------------------------------------------------

    def _render(self) -> None:
        if self._loaded is None:
            self.update()
            return
        layout, chain = self._loaded
        page = (split_pages(self._text) or [[]])[0]
        lines = [[page[i][0]] if i < len(page) else [] for i in range(len(layout.panes))]
        wide = [i for i, pane in enumerate(layout.panes) if lines[i] and fm.overflow(pane, chain, lines[i][0])]
        image, _ = fm.render_window(layout, chain, lines, background=WINDOW_BG)
        self._image = _to_qimage(image)
        notes = []
        if wide:
            notes.append(tr("Line too wide for the box: %1") % ", ".join(str(i + 1) for i in wide))
        if len(page) > len(layout.panes):
            notes.append(tr("Too many lines for the box: %1 (box holds %2)")
                         % (len(page), len(layout.panes)))
        self._note = " ".join(notes)
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802 - Qt name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        if self._image is not None:
            painter.drawImage(_MARGIN, _MARGIN, self._image)
        if self._note:
            painter.setPen(QColor(230, 230, 230))
            painter.drawText(_MARGIN, self.height() - 12, self._note)
        painter.end()


def _to_qimage(image: Any) -> QImage:
    rgba = image.convert("RGBA")
    raw = rgba.tobytes("raw", "RGBA")
    return QImage(raw, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()


__all__ = ["LayoutLoader", "SwitchMessagePreview", "font_files", "sibling_layout_exists", "source_folder"]
