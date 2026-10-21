"""The cutscene dialogue window preview of Symphony of the Night (see GameRules.get_custom_preview_widget).

The 8x8 font sheet is read from the project's font file (the translation copy when it exists) in a worker
thread; the window is drawn by ``text_window.render_page`` and shown at a whole-number zoom.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, List, Optional, Tuple

from PIL import Image
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QWidget

from core import font_formats
from core.i18n import tr
from plugins.castlevania_sotn import codec, hud, text_window
from plugins.castlevania_sotn.script import TAG_RE
from plugins.common.switch_message_preview import source_folder
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread, safe_shutdown_thread

WORKER_STOP_MS = 2000
ZOOM = 2
_MARGIN = 8
_FONT = json.loads((Path(__file__).with_name("font_sources.json")).read_text(encoding="utf-8"))[0]


def _project_folders(project_dir: str) -> Tuple[Optional[Path], Optional[Path]]:
    """(source folder, translation folder) of the project's ``.uiproj`` file; None where absent."""
    source = source_folder(project_dir)
    project = next(iter(sorted(Path(project_dir).glob("*.uiproj"))), None)
    if project is None:
        return None, None
    metadata = json.loads(project.read_text(encoding="utf-8")).get("metadata") or {}
    translation = str(metadata.get("translation_path") or "")
    return (Path(source) if source else None), (Path(translation) if translation else None)


def read_font_sheet(project_dir: str) -> Optional[Image.Image]:
    """The 8x8 font sheet (RGBA) of a project: its translation copy when written, else the source."""
    source, translation = _project_folders(project_dir)
    if source is None:
        return None
    path = source / _FONT["path"]
    if translation is not None and (translation / _FONT["path"]).is_file():
        path = translation / _FONT["path"]
    _metadata, sheets = font_formats.extract(_FONT["format"], path.read_bytes(), _FONT["params"])
    return sheets[0].convert("RGBA")


class FontLoader(WorkerThread):
    """Reads the font sheet in a worker. ``loaded`` carries ``(project folder, sheet or None)``."""

    loaded = pyqtSignal(object)

    def __init__(self, project_dir: str):
        super().__init__()
        self._project_dir = project_dir
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            sheet = read_font_sheet(self._project_dir)
        except (OSError, ValueError, KeyError, IndexError) as error:
            log_debug(f"castlevania_sotn preview: no font sheet in {self._project_dir}: {error}")
            sheet = None
        if not self._stop.is_set():
            self.loaded.emit((self._project_dir, sheet))


def read_hud_sheet(project_dir: str) -> Optional[Image.Image]:
    """The Richter HUD sheet of the project's prologue stage (ST0.BIN and F_GAME2.BIN, source copies)."""
    source, _translation = _project_folders(project_dir)
    if source is None:
        return None
    return hud.read_richter_hud(str(source / "ST" / "ST0" / "ST0.BIN"), str(source / "BIN" / "F_GAME2.BIN.pic"))


class HudLoader(WorkerThread):
    """Decodes the Richter HUD sheet in a worker. ``loaded`` carries ``(project folder, sheet or None)``."""

    loaded = pyqtSignal(object)

    def __init__(self, project_dir: str):
        super().__init__()
        self._project_dir = project_dir
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            sheet = read_hud_sheet(self._project_dir)
        except (OSError, ValueError, KeyError, IndexError) as error:
            log_debug(f"castlevania_sotn preview: no HUD sheet in {self._project_dir}: {error}")
            sheet = None
        if not self._stop.is_set():
            self.loaded.emit((self._project_dir, sheet))


def page_codes(text: str) -> List[List[int]]:
    """The first page of editor text as cell codes, one list per line (tags such as {WAIT 30} are not drawn)."""
    lines = TAG_RE.sub("", text).split("\n")
    return [list(codec.encode_cells(line)) for line in lines[:text_window.LINES]]


class SotnTextPreview(QWidget):
    """The cutscene window of the project's text (see GameRules.get_custom_preview_widget)."""

    def __init__(self, main_window: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._text = ""
        self._note = ""
        self._sheet: Optional[Image.Image] = None
        self._loader: Optional[FontLoader] = None
        self._source = ""
        self._image: Optional[QImage] = None
        self._hud: Optional[Image.Image] = None
        self._hud_loader: Optional[HudLoader] = None
        self.setMinimumHeight(text_window.CANVAS[1] * ZOOM + 2 * _MARGIN)
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
        if self._hud_loader is not None:
            self._hud_loader.cancel()
            safe_shutdown_thread(self._hud_loader, self._hud_loader, WORKER_STOP_MS)
            self._hud_loader = None
        self._sheet = None

    def _start_load(self) -> None:
        project_dir = getattr(getattr(self._mw, "project_manager", None), "project_dir", None)
        if not project_dir:
            self._note = tr("No project folder: the dialogue box needs the unpacked game.")
            return
        self._source = str(project_dir)
        self._loader = FontLoader(self._source)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()
        self._hud_loader = HudLoader(self._source)
        self._hud_loader.loaded.connect(self._on_hud_loaded)
        self._hud_loader.start()
        self._note = tr("Reading the game font...")

    def _on_loaded(self, payload: object) -> None:
        project_dir, sheet = payload
        if project_dir != self._source:
            return
        if sheet is None:
            self._note = tr("The dialogue font is not in this project's unpacked game.")
            return
        self._sheet = sheet
        self._render()

    def _on_hud_loaded(self, payload: object) -> None:
        project_dir, sheet = payload
        if project_dir != self._source:
            return
        self._hud = sheet
        self._render()

    def _with_hud(self, page: Image.Image) -> Image.Image:
        """The Richter hearts digits behind the window, on the prologue stage (ST0) only. Reads only."""
        if self._hud is None:
            return page
        rules = self._mw.current_game_rules
        data = self._mw.data_store
        if rules.get_stage_for_string(data.physical_block_idx, data.current_string_idx) != "ST0":
            return page
        frame = hud.draw_hearts(Image.new("RGBA", text_window.CANVAS, (0, 0, 0, 0)), self._hud)
        frame.alpha_composite(page)
        return frame

    def _speaker_cells(self) -> List[int]:
        """The speaker name of the selected line as cell codes (empty when it has none). Reads only."""
        rules = self._mw.current_game_rules
        data = self._mw.data_store
        name = rules.get_speaker_for_string(data.physical_block_idx, data.current_string_idx)
        return list(codec.encode_cells(name)) if name else []

    def _place(self) -> text_window.Place:
        """The selected line's window place (its script's POS command), or the default place. Reads only."""
        default = text_window.Place(*text_window.DEFAULT_PLACE)
        rules = self._mw.current_game_rules
        data = self._mw.data_store
        found = rules.get_dialogue_place(data.physical_block_idx, data.current_string_idx)
        return text_window.Place(*found) if found else default

    def _render(self) -> None:
        if self._sheet is None:
            self.update()
            return
        pages = TAG_RE.sub("", self._text).split("\n")
        page = text_window.render_dialogue(self._speaker_cells(), page_codes(self._text), self._sheet, self._place())
        page = self._with_hud(page)
        self._image = _to_qimage(text_window.scale_nearest(page, ZOOM))
        self._note = tr("Only the first page is drawn.") if len(pages) > text_window.LINES else ""
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
