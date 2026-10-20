"""The message window of the editor's preview column, drawn with the game's font and window geometry.

It shows the page of the selected string as the game draws it: the VSFONT glyphs of the translation copy,
the balloon or menu place of windows.py, the game's line breaks, centring and italic switches. Pages turn with
{page}. The window frame art is not drawn (the game takes it from its texture files); the text places are.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.font_formats.vagrant import CELL, COLUMNS, HEADER, ROW_BYTES, ROWS, TEXTURE, WIDTHS
from core.i18n import tr

from . import codec, windows

DEBOUNCE_MS = 60
SCALE = 2
GLYPH_KEY = Tuple[int, bool]


class MessageWindowPreview(QWidget):
    """The Vagrant Story message window for the preview column (GameRules.get_custom_preview_widget)."""

    def __init__(self, main_window: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._text = ""
        self._page = 0
        self._font: Optional[bytes] = None
        self._glyphs: Dict[GLYPH_KEY, QImage] = {}
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
        self._timer.start(DEBOUNCE_MS)

    def update_preview_text(self, text: Any = None, original: Any = None) -> None:
        if text is not None:
            self._text = str(text)
            self._page = 0
        self.refresh()

    def shutdown(self) -> None:
        self._timer.stop()

    # -- drawing ------------------------------------------------------------------------------

    def _turn(self, step: int) -> None:
        self._page += step
        self._render()

    def _glyph(self, font: bytes, code: int, italic: bool) -> QImage:
        key = (code, italic)
        if key not in self._glyphs:
            image = QImage(windows.CELL, windows.CELL, QImage.Format.Format_ARGB32)
            image.fill(0)
            which = 1 if italic else 0
            column, row = code % COLUMNS, code // COLUMNS
            set_top = HEADER + which * ROWS * CELL * ROW_BYTES      # the italic set starts below the regular one
            for y in range(CELL):
                line = set_top + (row * CELL + y) * ROW_BYTES
                for x in range(CELL):
                    px = column * CELL + x
                    byte = font[line + (px >> 1)]
                    ink = (byte >> 4) if px & 1 else (byte & 0xF)
                    if ink:
                        image.setPixelColor(x, y, QColor(255, 255, 255, ink * 17))
            self._glyphs[key] = image
        return self._glyphs[key]

    def _rules(self):
        return getattr(self._mw, "current_game_rules", None)

    def _message(self, text: str) -> None:
        self._picture.clear()
        self._status.setText(text)
        self._page_label.setText("")
        self._prev.setEnabled(False)
        self._next.setEnabled(False)

    def _render(self) -> None:
        rules = self._rules()
        if rules is None or not hasattr(rules, "preview_geometry"):
            return self._message(tr("No Vagrant Story project is open."))
        data = getattr(self._mw, "data_store", None)
        block = getattr(data, "physical_block_idx", -1)
        string = getattr(data, "current_string_idx", -1)
        if block is None or string is None or block < 0 or string < 0:
            return self._message(tr("Select a line to see its message window."))
        font = rules.preview_font()
        if font is None:
            return self._message(tr("The font file FONT/VSFONT.FNT is not in the project."))
        if font is not self._font:
            self._font, self._glyphs = font, {}
        rules.load_translation_map()
        geometry = rules.preview_geometry(block, string)
        widths = list(font[HEADER + TEXTURE:HEADER + TEXTURE + WIDTHS])
        raw = codec.encode(self._text, rules.char_codes)
        pages = windows.split_pages(raw, geometry["italic"])
        self._page = max(0, min(self._page, len(pages) - 1))
        lines = pages[self._page]
        image, notes = self._paint(font, widths, geometry, lines)
        self._picture.setPixmap(QPixmap.fromImage(image.scaled(image.width() * SCALE, image.height() * SCALE,
                                                               Qt.AspectRatioMode.IgnoreAspectRatio,
                                                               Qt.TransformationMode.FastTransformation)))
        self._page_label.setText(tr("Page {0} of {1}").format(self._page + 1, len(pages)))
        self._prev.setEnabled(self._page > 0)
        self._next.setEnabled(self._page < len(pages) - 1)
        self._status.setText(" ".join(notes))

    def _paint(self, font: bytes, widths: List[int], geometry: Dict[str, Any],
               lines: List[windows.Line]) -> Tuple[QImage, List[str]]:
        notes: List[str] = []
        limit = geometry.get("lines")
        step = geometry["step"]
        text_x, text_y = geometry["text_x"], geometry["text_y"]
        placed = []
        widest = 0
        for line in lines:
            runs, width = windows.place(line, geometry["italic"], widths, text_x, geometry.get("text_width"))
            placed.append(runs)
            widest = max(widest, width)
        height = geometry["height"] or (text_y + len(lines) * step + 4)
        if limit and len(lines) > limit:
            height = max(height, text_y + len(lines) * step + 4)
            notes.append(tr("This page has {0} lines; the window shows {1}.").format(len(lines), limit))
        width = geometry["width"] or (widest + 2 * text_x)
        image = QImage(max(1, width), max(1, height), QImage.Format.Format_ARGB32)
        if geometry["framed"]:
            image.fill(QColor(0, 0, 0, 150))
        else:
            image.fill(QColor(32, 32, 40, 255))
        painter = QPainter(image)
        for row, runs in enumerate(placed):
            for code, italic, x in runs:
                painter.drawImage(x, text_y + row * step, self._glyph(font, code, italic))
        painter.end()
        if geometry["kind"] == "row":
            notes.append(tr("Row text: {0} px wide (the row starts at +{1}).").format(widest, text_x))
        return image, notes
