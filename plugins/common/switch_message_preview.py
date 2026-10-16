"""The dialogue box of a Switch Pokémon game drawn with the game's own layout and font.

The source folder comes from the project file (``metadata.source_path``, as the build reads it). The layout and the
fonts are read on a worker thread (AGENTS rule 5). The widget draws the page on the UI thread: a few lines of text.
Each text pane of the layout takes one line of the page. A line wider than its pane, or a page with more lines than
the box has panes, is reported under the preview.

``BoxSpec`` holds the facts of one box: its layout archive, the font setting, the font files and the em size. The
em size is measured per box (see the comments at each spec); the Trinity plugin (Scarlet / Violet) uses its own spec
from ``plugins/pokemon_trinity``.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
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
from utils.thread_utils import WorkerThread, safe_shutdown_thread

# The text font chain, in fallback order. OVERRIDE, unverified: the layout's fcpx names Rodin first, and the game's own
# binding (bin/font/font_data.prmb) is not read yet. UDKakugo is chosen because its widths give the same wrap cliff as
# the game's lines at the layout size; Rodin at 0.82 x the size gives the same widths, so the widths alone do not pick it.
MESSAGE_FONTS = ("FOT-UDKakugoC80Pro-DB.otf", "FOT-RodinNTLGPro-DB.otf", "or_font.otf")
_MARGIN = 10
WORKER_STOP_MS = 2000               # the bounded wait for the layout read when the widget is closed


@dataclass(frozen=True)
class BoxSpec:
    """One dialogue box: where its layout is, the font setting and font folder, and the flat colour that stands in
    for the box picture (the picture is not read yet)."""
    arc: str                      # the layout archive, relative to the source folder
    member: str                   # the layout member inside it
    fcpx: str                     # the font setting member
    font_dir: str                 # the folder of the scrambled font files, relative to the source folder
    background: Tuple[int, int, int, int] = (238, 240, 242, 255)


# The text is drawn at each pane's own fontSize (the layout's value). Check: the game's hand-broken lines pile up
# against the pane edge at that size (Sword 54 px, 1080 px pane: 1.00-1.02 of the pane, then almost none above 1.04;
# Scarlet / Violet 42 px, 840 px pane: the same shape). The font is UDKakugo; that is an override, see MESSAGE_FONTS.
# Sword / Shield: msg_00.bflyt, one frame with two text panes (1080 px).
SWORD_SHIELD_BOX = BoxSpec("bin/appli/msg/bin/msg_00.arc", "blyt/msg_00.bflyt", "fcpx/system54_jpn.bfcpx", "bin/font")
# Scarlet / Violet: msg_sub_00.bflyt from the sub-window archive (appli/data/msg_sub), two 840 px text panes, no frame.
# Not yet checked that this is the field dialogue (msg_btl_00 is the battle box, also two panes).
SCARLET_VIOLET_SUB_BOX = BoxSpec("appli/data/msg_sub/msg_sub_body_00.arc", "blyt/msg_sub_00.bflyt",
                                 "fcpx/system32_jpn.bfcpx", "appli/font/bin", background=(38, 42, 52, 255))
# Legends: Arceus: the battle message box (msg_sys_00_s, in the battle_menu pack, decoded by the wizard). Two 960 px
# panes, no text from the field dialogue yet. Its cliff is weak: 303 battle lines, none above 1.02 of the pane.
ARCEUS_BATTLE_BOX = BoxSpec("bin/archive/appli/battle_menu_eng.gfpak.d/11_msg_sys_00_s.arc", "blyt/msg_sys_00_s.bflyt",
                            "fcpx/system32_jpn.bfcpx", "bin/font", background=(38, 42, 52, 255))


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


def font_files(font_dir: Path, names: Tuple[str, ...] | List[str]) -> List[Path]:
    """The scrambled font files of a font name list, in fallback order. Raises if one is missing."""
    out = []
    for name in names:
        path = _font_file(font_dir, name)
        if path is None:
            raise FileNotFoundError(f"font {name} is not in {font_dir}")
        out.append(path)
    return out


def sibling_layout_exists(project_dir: str, spec: BoxSpec) -> bool:
    """A cheap check for the host hook (UI thread): the box's archive is in the project's source folder. Two places:
    the owner's ``source`` next to the project folder, or the wizard's ``unpacked/source`` inside the project folder."""
    folder = Path(project_dir)
    return any((root / spec.arc).is_file() for root in (folder.parent / "source", folder / "unpacked" / "source"))


def _font_file(font_dir: Path, name: str) -> Optional[Path]:
    """The scrambled font file of an ``.otf`` name in the game's font folder (BFOTF, any case)."""
    stem = name.rsplit(".", 1)[0].lower()
    for path in font_dir.iterdir():
        if path.suffix.lower() in (".bfotf", ".bfttf") and path.stem.lower() == stem:
            return path
    return None


class LayoutLoader(WorkerThread):
    """Reads one box's layout and fonts. ``loaded`` carries ``(project folder, (layout, chain) or None)``."""

    loaded = pyqtSignal(object)

    def __init__(self, project_dir: str, spec: BoxSpec):
        super().__init__()
        self._project_dir = project_dir
        self._spec = spec
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
            arc = Sarc((root / self._spec.arc).read_bytes())
            layout = fm.read_layout(arc.files[self._spec.member], arc.files[self._spec.fcpx])
            faces = [fm.Face.from_bfotf(path.read_bytes())
                     for path in font_files(root / self._spec.font_dir, MESSAGE_FONTS)]
            result = (layout, fm.FontChain(faces))
        except (OSError, ValueError, KeyError, IndexError, FileNotFoundError) as exc:
            log_debug(f"switch message preview: no dialogue layout for {self._source_dir}: {exc}")
        if not self._stop.is_set():
            self.loaded.emit((self._project_dir, result))


class SwitchMessagePreview(QWidget):
    """The dialogue box of the project (see GameRules.get_custom_preview_widget)."""

    def __init__(self, main_window: Any, spec: BoxSpec, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._mw = main_window
        self._spec = spec
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
            safe_shutdown_thread(self._loader, self._loader, WORKER_STOP_MS)
            self._loader = None
        self._loaded = None

    # -- loading --------------------------------------------------------------------------

    def _start_load(self) -> None:
        project_dir = getattr(getattr(self._mw, "project_manager", None), "project_dir", None)
        if not project_dir:
            self._note = tr("No project folder: the dialogue box needs the unpacked game.")
            return
        self._source = str(project_dir)
        self._loader = LayoutLoader(self._source, self._spec)
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
        if not layout.panes:
            self._note = tr("The dialogue layout is not in this project's unpacked game.")
            self.update()
            return
        # A game line longer than its pane flows into the next pane (word wrap), as the game does.
        width = min(pane.rect[2] - pane.rect[0] for pane in layout.panes)
        size = layout.panes[0].size[0]
        page = (split_pages(self._text) or [[]])[0]
        shown: List[str] = []
        too_long = False
        for line, _colour in page:
            parts, long_word = fm.wrap_text(line, width, chain, size, layout.panes[0].char_space)
            shown += parts
            too_long = too_long or long_word
        lines = [[shown[i]] if i < len(shown) else [] for i in range(len(layout.panes))]
        image = fm.render_window(layout, chain, lines, background=self._spec.background)
        self._image = _to_qimage(image)
        notes = []
        if too_long:
            notes.append(tr("A word is wider than the box."))
        if len(shown) > len(layout.panes):
            notes.append(tr("Too many lines for the box: %1 (box holds %2)")
                         % (len(shown), len(layout.panes)))
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


__all__ = ["ARCEUS_BATTLE_BOX", "BoxSpec", "LayoutLoader", "SCARLET_VIOLET_SUB_BOX", "SWORD_SHIELD_BOX",
           "SwitchMessagePreview",
           "font_files", "sibling_layout_exists", "source_folder"]
