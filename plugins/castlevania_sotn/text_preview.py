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
from core.project_library import console_keys
from plugins.castlevania_sotn import codec, hud, menu_screens, menu_strings, menu_text, scroll, text_window
from plugins.castlevania_sotn.script import TAG_RE
from plugins.common.switch_message_preview import source_folder
from utils.logging_utils import log_debug
from utils.thread_utils import WorkerThread, safe_shutdown_thread

WORKER_STOP_MS = 2000
ZOOM = 2
_MARGIN = 8
_INFO_BAR_CROP = (56, 192, 368, 224)   # the info bar band of the menu panel
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


def read_menu_table(project_dir: str) -> Optional[List[int]]:
    """The g_MenuStr string offsets of the source DRA.BIN (menu_strings.read_table), or None."""
    source, _translation = _project_folders(project_dir)
    if source is None or not (source / "DRA.BIN").is_file():
        return None
    return menu_strings.read_table((source / "DRA.BIN").read_bytes())


def read_bios() -> Optional[bytes]:
    """The PlayStation BIOS bytes of the console key ``psx_bios``, or None while it is not set."""
    path = console_keys.path_for("psx_bios")
    return Path(path).read_bytes() if path else None


def menu_line_image(bios: bytes, text: bytes) -> Tuple[Image.Image, int]:
    """The first line on the info bar of a menu panel, at the game's place (menu_screens), cropped to the bar.

    Returns the picture and the count of characters outside the BIOS table (drawn blank).
    """
    panel = menu_screens.panel()
    missing = menu_screens.paint_info_bar(panel, text, lambda code: menu_text.glyph_at(bios, code))
    return panel.crop(_INFO_BAR_CROP), missing


class FontLoader(WorkerThread):
    """Reads the font sheet and the BIOS file in a worker. ``loaded`` carries ``(project folder, sheet, BIOS)``."""

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
        try:
            bios = read_bios()
        except OSError as error:
            log_debug(f"castlevania_sotn preview: the BIOS file cannot be read: {error}")
            bios = None
        try:
            table = read_menu_table(self._project_dir)
        except OSError as error:
            log_debug(f"castlevania_sotn preview: no DRA.BIN menu table: {error}")
            table = None
        if not self._stop.is_set():
            self.loaded.emit((self._project_dir, sheet, bios, table))


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
        self._bios: Optional[bytes] = None
        self._table: Optional[List[int]] = None
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
        project_dir, sheet, bios, table = payload
        if project_dir != self._source:
            return
        self._bios = bios
        self._table = table
        self._sheet = sheet
        if sheet is None:
            self._note = tr("The dialogue font is not in this project's unpacked game.")
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

    def _is_menu_line(self) -> bool:
        """True when the selected line uses the console's 12 x 16 font (Shift-JIS lines). Reads only."""
        rules = self._mw.current_game_rules
        data = self._mw.data_store
        attributes = rules.get_message_attributes(data.physical_block_idx, data.current_string_idx)
        return bool(attributes) and attributes.get("font") == "bios"

    def _is_caption_line(self) -> bool:
        """True when the selected line is a line of the prologue caption. Reads only."""
        rules = self._mw.current_game_rules
        data = self._mw.data_store
        attributes = rules.get_message_attributes(data.physical_block_idx, data.current_string_idx)
        return bool(attributes) and attributes.get("kind") == "caption"

    def _render_caption(self) -> None:
        """The prologue caption page on the 512-wide panel, the selected line as typed (scroll.py). Needs the BIOS."""
        if self._bios is None:
            self._image = None
            self._note = tr("Set the PlayStation BIOS file in the Settings, Console keys tab to draw this caption.")
            self.update()
            return
        rules = self._mw.current_game_rules
        data = self._mw.data_store
        found = rules.get_caption_page(data.physical_block_idx, data.current_string_idx)
        if found is None:
            self._image = None
            self._note = ""
            self.update()
            return
        page, index = found
        try:
            raw, _brk = scroll.from_editor(self._text, last=False)
        except scroll.ScrollError as error:
            self._image = None
            self._note = str(error)
            self.update()
            return
        page = [(x, raw if row == index else text) for row, (x, text) in enumerate(page)]
        self._image = _to_qimage(scroll.render_page(self._bios, page))
        self._note = ""
        self.update()

    def _render_menu_line(self) -> None:
        """The first line in the menu font, as the menus draw it (menu_text.py). The BIOS file is needed."""
        if self._bios is None:
            self._image = None
            self._note = tr("Set the PlayStation BIOS file in the Settings, Console keys tab to draw this line.")
            self.update()
            return
        first, _sep, rest = self._text.partition("\n")
        page, missing = menu_line_image(self._bios, codec.encode_sj(first))
        self._image = _to_qimage(text_window.scale_nearest(page, ZOOM))
        notes = []
        if rest.strip():
            notes.append(tr("Only the first line is drawn."))
        if missing:
            notes.append(tr("Some characters are outside the drawn range; they are blank."))
        self._note = " ".join(notes)
        self.update()

    def _menu_slot(self) -> Optional[int]:
        """The g_MenuStr slot of the selected line (a DRA string in the pointer table), or None. Reads only."""
        if self._table is None:
            return None
        rules = self._mw.current_game_rules
        data = self._mw.data_store
        at = rules.get_menu_source_offset(data.physical_block_idx, data.current_string_idx)
        return None if at is None else menu_strings.slot_for_offset(self._table, at)

    def _render_menu_word(self, slot: int) -> None:
        """The selected 8x8 menu word at its traced place on its menu panel (menu_screens / menu_strings)."""
        place = menu_strings.placement(slot)
        if place is None or self._sheet is None:
            self._image = None
            self._note = tr("This menu word has no traced place yet.") if place is None else ""
            self.update()
            return
        screen, x, y = place
        panel = menu_screens.panel()
        if screen == "command":
            menu_screens.command_frame(panel, menu_strings.COMMAND_ORIGIN, slot - 92)
        elif screen == "popup":
            menu_screens.popup_frame(panel, menu_strings.POPUP_ORIGIN, slot == 34)
        glyphs = menu_screens.Glyphs(mask_of=self._cell_mask, cell_of=codec.encode_cells)
        first = TAG_RE.sub("", self._text).split("\n")[0]
        menu_screens.draw_cells(panel, glyphs, list(codec.encode_cells(first)), x, y)
        self._image = _to_qimage(text_window.scale_nearest(panel, ZOOM))
        self._note = ""
        self.update()

    def _cell_mask(self, cell: int) -> Image.Image:
        """The 8x8 alpha mask of a font cell (255 where the cell has ink)."""
        alpha = text_window.cell_sheet_crop(self._sheet, cell).getchannel("A")
        return alpha.point(lambda v: 255 if v else 0)

    def _render(self) -> None:
        slot = self._menu_slot()
        if slot is not None:
            self._render_menu_word(slot)
            return
        if self._is_caption_line():
            self._render_caption()
            return
        if self._is_menu_line():
            self._render_menu_line()
            return
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
