"""The message-box preview of a Generation III project: the game's own font, read from the base ROM in a worker.

The worker reads the project's facts, the font tables and the charmap once. The widget only draws: the text of the
selected message, page by page, in the window the game uses, with overflow warnings under the box.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.i18n import tr
from plugins.common import text_window_preview as tw
from plugins.common.gba_text_font import read_glyph_set, read_glyph_set_4bpp
from plugins.pokemon_fr import rom_project, rom_text
from utils.thread_utils import WorkerThread, safe_shutdown_thread

DEBOUNCE_MS = 120
WORKER_STOP_MS = 3000
SCALE = 2


class FontContext:
    """What the preview needs from a project: the glyphs, the charmap and the window."""

    def __init__(self, glyphs: Any, charmap: Any, window: tw.Window) -> None:
        self.glyphs = glyphs
        self.charmap = charmap
        self.window = window


def load_context(rom_dir: Path) -> FontContext:
    """Read the font of the unpacked game. Blocking file reads: call it from the worker only."""
    meta = json.loads((rom_dir / rom_project.META_FILE.name).read_text(encoding="utf-8"))
    facts = json.loads((rom_text.FACTS_DIR / meta["facts"]).read_text(encoding="utf-8"))
    font = facts.get("font")
    if not font:
        raise ValueError(tr("The font of this game is not in its facts yet."))
    reader = read_glyph_set_4bpp if font.get("kind") == "gen3_4bpp" else read_glyph_set
    glyphs = reader(rom_dir / rom_project.BASE_ROM.name, font)
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts.get("charmap", rom_text.CHARMAP_FILE))
    return FontContext(glyphs, charmap, tw.Window.from_facts(font["window"]))


class ContextLoader(WorkerThread):
    """Loads the context. ``loaded`` carries (generation, FontContext, or the error text)."""

    loaded = pyqtSignal(int, object)

    def __init__(self, generation: int, rom_dir: Path, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._generation = generation
        self._rom_dir = rom_dir
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            result: Any = load_context(self._rom_dir)
        except (OSError, ValueError, KeyError) as error:
            result = str(error)
        if not self._stop.is_set():
            self.loaded.emit(self._generation, result)


class MessageWindowPreview(QWidget):
    """The message box in the game's font, for the editor's preview column (GameRules.get_custom_preview_widget)."""

    def __init__(self, main_window: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._text = ""
        self._page = 0
        self._rom_dir: Optional[Path] = None
        self._generation = 0
        self._context: Optional[FontContext] = None
        self._error = ""
        self._worker: Optional[ContextLoader] = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._render)
        self._picture = QLabel(self)
        self._picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prev = QPushButton(tr("Previous page"), self)
        self._next = QPushButton(tr("Next page"), self)
        self._prev.clicked.connect(lambda: self._turn(-1))
        self._next.clicked.connect(lambda: self._turn(1))
        self._page_label = QLabel(self)
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
        layout.addWidget(self._status)

    # -- host interface -----------------------------------------------------------------------

    def refresh(self) -> None:
        """The selection or the text changed: redraw after a short pause."""
        self._timer.start(DEBOUNCE_MS)

    def update_preview_text(self, text: Any = None, original: Any = None) -> None:
        if text is not None:
            self._text = str(text)
            self._page = 0
        self.refresh()

    def shutdown(self) -> None:
        """Stop the loader and wait a bounded time for it. Call before the widget is deleted."""
        self._timer.stop()
        if self._worker is not None:
            self._worker.cancel()
            safe_shutdown_thread(self._worker, self._worker, WORKER_STOP_MS)
            self._worker = None

    # -- drawing -------------------------------------------------------------------------------

    def _rom_folder(self) -> Optional[Path]:
        """The ``rom`` folder beside the project's text folder, found from the open project (no disk read here)."""
        manager = getattr(self._mw, "project_manager", None)
        project = getattr(manager, "project", None) if manager is not None else None
        if project is None or not getattr(project, "blocks", None):
            return None
        path = manager.get_absolute_path(project.blocks[0].source_file)
        if not path:
            return None
        return Path(path).parent.parent / rom_project.ROM_DIR

    def _turn(self, step: int) -> None:
        self._page += step
        self._render()

    def _render(self) -> None:
        folder = self._rom_folder()
        if folder is None:
            self._show_message(tr("Open a game project to see the message box."))
            return
        if folder != self._rom_dir:
            self._rom_dir = folder
            self._context = None
            self._error = ""
            self._generation += 1
            self._start_loader(self._generation, folder)
        if self._context is None:
            self._show_message(self._error or tr("Loading the game's font..."))
            return
        ctx = self._context
        pages = tw.parse_pages(self._text, ctx.charmap.byte_of.get, ctx.charmap.byte_of.get("?", 0))
        self._page = min(max(self._page, 0), len(pages) - 1)
        image = tw.render_page(pages[self._page], ctx.glyphs, ctx.window)
        self._picture.setPixmap(QPixmap.fromImage(image.scaled(image.width() * SCALE, image.height() * SCALE,
                                                             Qt.AspectRatioMode.IgnoreAspectRatio,
                                                             Qt.TransformationMode.FastTransformation)))
        self._page_label.setText(tr("Page {0} of {1}", str(self._page + 1), str(len(pages))))
        self._prev.setEnabled(self._page > 0)
        self._next.setEnabled(self._page < len(pages) - 1)
        notes = [self._note(item, ctx.window) for item in tw.check_pages(pages, ctx.glyphs, ctx.window)
                 if item.page == self._page]
        self._status.setText("\n".join(notes))

    def _note(self, item: tw.Overflow, window: tw.Window) -> str:
        if item.kind == "wide":
            return tr("Line {0} is {1} px wide; the box holds {2} px.", str(item.line + 1), str(item.detail),
                      str(window.text_width))
        return tr("Line {0} does not fit the box; add a line scroll or a new page before it.", str(item.line + 1))

    def _show_message(self, text: str) -> None:
        self._picture.setPixmap(QPixmap())
        self._picture.setText(text)
        self._page_label.setText("")
        self._prev.setEnabled(False)
        self._next.setEnabled(False)
        self._status.setText("")

    def _start_loader(self, generation: int, folder: Path) -> None:
        if self._worker is not None:
            self._worker.cancel()
        self._worker = ContextLoader(generation, folder, self)
        self._worker.loaded.connect(self._on_loaded)
        self._worker.start()

    def _on_loaded(self, generation: int, result: Any) -> None:
        if generation != self._generation:
            return
        if isinstance(result, FontContext):
            self._context = result
        else:
            self._error = str(result)
        self._render()
