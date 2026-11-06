"""The talk window of the TotK engine (Tears of the Kingdom, Ocarina of Time on Switch 2), drawn with the game's font.

Shared by ``zelda_totk`` and ``zelda_oot_switch2`` (``GameRules.get_custom_preview_widget``); each plugin gives its
``BoxFacts``. Coordinates are a 1920 x 1080 screen.

Measured facts:
- Ocarina of Time (Switch 2): ``UI/Layout2Archive/Common`` -> ``MessageInGame_00.buil`` (Layout2, canvas 3840 x 2160).
  The message pane is 2200 x 200 at scale 0.9 (990 px at 1080p); its text styles are 92 and 67.5 px. The 67.5 px
  style (33.75 px at 1080p) is the one the shipped text fits: with ClarimoUDPE Light (the Russian slot's dialogue
  font, ``font_sources.json``) the widest of 34698 Russian talk lines is 974 px (99.9 % under 959). With 92 px,
  626 shipped lines would not fit. The pane-to-style link itself is not decoded.
- Tears of the Kingdom: talk lines reach 993 px with Rodin NTLG B at 45 px (``rules.get_string_layout``; config 1000).
- Three lines a page (the plugins' ``lines_per_page``); ``{pageBreak}`` starts a page.

Approximated, not read from the game: the line pitch (1.3 x the glyph size), the box picture (a flat dark box), the
colour ids of ``{color:n}`` (Breath of the Wild's list: red, light green, blue, grey, light green, orange, light grey).
Lines are not wrapped: the game shows the line breaks of the text, so a longer line is reported, not re-flowed.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw
from PyQt6.QtCore import QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QWidget

from core.i18n import tr
from plugins.common import flyt_message as fm
from plugins.common.switch_message_preview import source_folder
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread, safe_shutdown_thread

from .font_tool import fonts_in

RGBA = Tuple[int, int, int, int]
WHITE: RGBA = (255, 255, 255, 255)
COLOURS: Dict[int, RGBA] = {   # APPROXIMATED: Breath of the Wild's colour ids, not read from this game
    0: (255, 80, 80, 255), 1: (150, 230, 120, 255), 2: (110, 160, 255, 255), 3: (170, 170, 170, 255),
    4: (150, 230, 120, 255), 5: (255, 170, 60, 255), 6: (210, 210, 210, 255)}
BOX_COLOUR: RGBA = (16, 16, 16, 215)
PADDING = 28.0
PITCH = 1.3                    # APPROXIMATED line pitch in glyph sizes
MAX_PAGES = 6
WORKER_STOP_MS = 2000
_TAG = re.compile(r"\{(/?)([^{}:]*)(?::([^{}]*))?\}")

Run = Tuple[str, RGBA]
Line = List[Run]


@dataclass(frozen=True)
class BoxFacts:
    """One game's talk window: its fonts (paths from the source folder; ``names`` picks fonts out of an archive, in
    fallback order), the glyph size, the text width and the lines a page, all at 1080p."""
    fonts: Tuple[str, ...]
    names: Tuple[str, ...] = ()
    em: float = 45.0
    width: float = 1000.0
    lines: int = 3


OOT_SWITCH2_BOX = BoxFacts(fonts=("../Font2/Scalable/ClarimoUDPE-Light.Nin_Ounce_NVN2.bfotf.zs",
                                  "../Font2/Scalable/OT-UDTypos510Std-Regular.Nin_Ounce_NVN2.bfotf.zs"),
                           em=33.75, width=990.0)
TOTK_BOX = BoxFacts(fonts=("Font/Font.Nin_NX_NVN.bfarc.zs", "../Font/Font.Nin_NX_NVN.bfarc.zs"),
                    names=("RodinNTLG-B",), em=45.0, width=1000.0)


def parse_pages(text: str) -> List[List[Line]]:
    """Pages of lines of coloured runs. ``{color:n}`` sets the colour (-1 / 65535 or ``{/color}``: white),
    ``{pageBreak}`` starts a page; every other tag (delays, voice, sound, ruby) is not drawn."""
    pages: List[List[Line]] = [[[]]]
    colour = WHITE
    pos = 0
    source = text or ""

    def add(chunk: str) -> None:
        nonlocal pages
        for index, part in enumerate(chunk.split("\n")):
            if index:
                pages[-1].append([])
            if part:
                pages[-1][-1].append((part, colour))

    for match in _TAG.finditer(source):
        add(source[pos:match.start()])
        pos = match.end()
        closing, name, arg = match.group(1), match.group(2), match.group(3)
        if name == "pageBreak":
            pages.append([[]])
        elif name == "color":
            value = int(arg) if not closing and arg and arg.lstrip("-").isdigit() else -1
            colour = COLOURS.get(value, WHITE)
    add(source[pos:])
    for page in pages:   # a line break right before a page break leaves no empty line
        while len(page) > 1 and not page[-1]:
            page.pop()
    return [page for page in pages if any(page)] or [[[]]]


def line_width(line: Line, chain: fm.FontChain, em: float) -> float:
    return sum(chain.width(part, em) for part, _colour in line)


def render_page(page: List[Line], chain: fm.FontChain, facts: BoxFacts) -> Image.Image:
    """One page in the talk box: the box is the text width and ``facts.lines`` lines, plus padding."""
    pitch = facts.em * PITCH
    width = int(facts.width + 2 * PADDING)
    height = int(facts.lines * pitch + 2 * PADDING)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(image).rounded_rectangle((0, 0, width - 1, height - 1), radius=18, fill=BOX_COLOUR)
    ascent = chain.faces[0].ascent(facts.em) if chain.faces else facts.em * 0.8
    top = PADDING + (pitch - facts.em) / 2
    for row, line in enumerate(page):
        baseline = top + row * pitch + ascent
        pen = PADDING
        for part, colour in line:
            for ch in part:
                face = chain.face_of(ch)
                if face is None:
                    pen += facts.em / 2
                    continue
                face.draw(image, ch, pen, baseline, facts.em, colour)
                pen += face.advance(ch, facts.em)
    return image


def problems(pages: Sequence[List[Line]], chain: fm.FontChain, facts: BoxFacts) -> List[str]:
    notes = []
    for number, page in enumerate(pages, 1):
        widest = max((line_width(line, chain, facts.em) for line in page), default=0.0)
        if widest > facts.width:
            notes.append(tr("Page {0}: a line is {1} px, the box holds {2} px.", number, round(widest), round(facts.width)))
        if len(page) > facts.lines:
            notes.append(tr("Page {0}: {1} lines, the box holds {2}.", number, len(page), facts.lines))
    return notes


def load_chain(source_dir: str, facts: BoxFacts) -> fm.FontChain:
    """The fonts of ``facts`` from the source folder, in fallback order. Raises when none is there."""
    found: Dict[str, bytes] = {}
    for rel in facts.fonts:
        path = Path(source_dir, *rel.split("/"))
        if path.is_file():
            found.update(fonts_in(path))
    picked = [found[name] for name in facts.names if name in found] if facts.names else list(found.values())
    if not picked:
        raise FileNotFoundError(f"no talk window font in {source_dir}")
    return fm.FontChain([fm.Face.from_bfotf(data) for data in picked])


class FontLoader(WorkerThread):
    """Reads the fonts off the UI thread. ``loaded`` carries ``(project folder, chain or None)``."""

    loaded = pyqtSignal(object)

    def __init__(self, project_dir: str, facts: BoxFacts):
        super().__init__()
        self._project_dir = project_dir
        self._facts = facts
        self._stop = threading.Event()

    def cancel(self) -> None:
        self._stop.set()

    def run(self) -> None:
        chain = None
        try:
            chain = load_chain(source_folder(self._project_dir) or "", self._facts)
        except (OSError, ValueError, KeyError) as exc:
            log_debug(f"totk preview: no font for {self._project_dir}: {exc}")
        if not self._stop.is_set():
            self.loaded.emit((self._project_dir, chain))


class TalkWindowPreview(QWidget):
    """The pages of the current text in the talk window (see GameRules.get_custom_preview_widget)."""

    def __init__(self, main_window: Any, facts: BoxFacts, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._facts = facts
        self._text = ""
        self._chain: Optional[fm.FontChain] = None
        self._images: List[QImage] = []
        self._note = ""
        self._loader: Optional[FontLoader] = None
        self._source = str(getattr(getattr(main_window, "project_manager", None), "project_dir", None) or "")
        self.setMinimumHeight(160)
        if not self._source:
            self._note = tr("No project folder: the talk window needs the unpacked game.")
            return
        self._loader = FontLoader(self._source, facts)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()
        self._note = tr("Reading the game font...")

    # -- host interface -------------------------------------------------------------------

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
        self._chain = None

    # -- drawing --------------------------------------------------------------------------

    def _on_loaded(self, payload: object) -> None:
        project_dir, chain = payload
        if project_dir != self._source:
            return
        if chain is None:
            self._note = tr("The game font is not in this project's unpacked game.")
            self.update()
            return
        self._chain = chain
        self._render()

    def _render(self) -> None:
        if self._chain is not None:
            pages = parse_pages(self._text)
            self._images = [_to_qimage(render_page(page, self._chain, self._facts)) for page in pages[:MAX_PAGES]]
            self._note = " ".join(problems(pages, self._chain, self._facts))
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802 - Qt name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        y = 6.0
        for image in self._images:
            scale = min(1.0, (self.width() - 12) / max(1, image.width()))
            target = QRectF(6, y, image.width() * scale, image.height() * scale)
            painter.drawImage(target, image)
            y += target.height() + 6
        if self._note:
            painter.setPen(QColor(230, 230, 230))
            painter.drawText(8, self.height() - 10, self._note)
        painter.end()


def _to_qimage(image: Image.Image) -> QImage:
    raw = image.tobytes("raw", "RGBA")
    return QImage(raw, image.width, image.height, image.width * 4, QImage.Format.Format_RGBA8888).copy()
