"""Brilliant Diamond / Shining Pearl field dialogue preview: the game's TextMesh Pro face (efigs font) drawn at the
measured pen origin and baseline. The box picture is not drawn (flat background). Facts: config.json "dialogue_box"."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QWidget

from core.i18n import tr
from plugins.common import flyt_message as fm
from plugins.common.message_window import split_pages
from plugins.common.switch_message_preview import source_folder
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread, safe_shutdown_thread

CONFIG_PATH = Path(__file__).with_name("config.json")
CANVAS = (1100, 150)
WORKER_STOP_MS = 2000
_MARGIN = 10


def load_facts() -> Dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["dialogue_box"]


def render_line(face: fm.TmpFace, text: str, facts: Dict[str, Any],
                background: Optional[Tuple[int, int, int, int]] = None) -> Tuple[Image.Image, List[str]]:
    """The first line of ``text`` at the measured px size, pen x and baseline. Returns the image and the characters
    the font lacks. Only one line is drawn: the line pitch and the wrap width are not measured yet.
    ``background`` defaults to the box background in the facts; (0, 0, 0, 0) gives the glyphs alone."""
    px = float(facts["px"])
    image = Image.new("RGBA", CANVAS, background or tuple(facts["background"]))
    origin_x, origin_y = facts["canvas_origin"]
    pen = float(facts["pen_x"]) - origin_x
    baseline = float(facts["baseline_y"]) - origin_y
    missing: List[str] = []
    for ch in text:
        if not face.has(ch):
            if ch != " " and ch not in missing:
                missing.append(ch)
            pen += px * 0.3
            continue
        face.draw(image, ch, pen, baseline, px, (*tuple(facts["colour"]), 255))
        pen += face.advance(ch, px)
    return image, missing


class FaceLoader(WorkerThread):
    """Reads the efigs TMP face of the project. ``loaded`` carries ``(project folder, face or None)``."""

    loaded = pyqtSignal(object)

    def __init__(self, project_dir: str):
        super().__init__()
        self._project_dir = project_dir
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        face: Optional[fm.TmpFace] = None
        try:
            facts = load_facts()
            root = Path(source_folder(self._project_dir) or "")
            font = root / facts["font_dir"]
            asset = json.loads((font / f"{facts['font_name']}.json").read_text(encoding="utf-8"))
            atlas = Image.open(font / f"{facts['font_name']}.png")
            face = fm.TmpFace(asset, atlas)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log_debug(f"dialogue preview: no TMP face in {self._project_dir}: {exc}")
        if not self._stop.is_set():
            self.loaded.emit((self._project_dir, face))


class DialogueBoxPreview(QWidget):
    """The dialogue box text of the project (see GameRules.get_custom_preview_widget)."""

    def __init__(self, main_window: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._text = ""
        self._note = ""
        self._face: Optional[fm.TmpFace] = None
        self._loader: Optional[FaceLoader] = None
        self._source = ""
        self._image: Optional[QImage] = None
        self.setMinimumHeight(160)
        self._start_load()

    def refresh(self) -> None:
        self._render()

    def update_preview_text(self, text: object = None, original: object = None) -> None:
        self._text = text if isinstance(text, str) else ""
        self._render()

    def shutdown(self) -> None:
        if self._loader is not None:
            self._loader.cancel()
            safe_shutdown_thread(self._loader, self._loader, WORKER_STOP_MS)
            self._loader = None
        self._face = None

    def _start_load(self) -> None:
        project_dir = getattr(getattr(self._mw, "project_manager", None), "project_dir", None)
        if not project_dir:
            self._note = tr("No project folder: the dialogue box needs the unpacked game.")
            return
        self._source = str(project_dir)
        self._loader = FaceLoader(self._source)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()
        self._note = tr("Reading the game font...")

    def _on_loaded(self, payload: object) -> None:
        project_dir, face = payload
        if project_dir != self._source:
            return
        if face is None:
            self._note = tr("The dialogue font is not in this project's unpacked game.")
            return
        self._face = face
        self._render()

    def _render(self) -> None:
        if self._face is None:
            self.update()
            return
        facts = load_facts()
        page = (split_pages(self._text) or [[]])[0]
        line = page[0][0] if page else ""
        image, missing = render_line(self._face, line, facts)
        self._image = _to_qimage(image)
        notes = [tr("Only the first line is drawn: the line pitch and the wrap width are not measured yet.")]
        if len(page) > 1:
            notes.append(tr("More lines on this page are not drawn yet."))
        if missing:
            notes.append(tr("Not in the box font: %1") % " ".join(missing))
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


def _to_qimage(image: Image.Image) -> QImage:
    rgba = image.convert("RGBA")
    raw = rgba.tobytes("raw", "RGBA")
    return QImage(raw, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()


__all__ = ["DialogueBoxPreview", "FaceLoader", "load_facts", "render_line"]
