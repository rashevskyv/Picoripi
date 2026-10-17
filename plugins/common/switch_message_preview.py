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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QComboBox, QWidget

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
_BAR = 30                           # the height of the box switch above the drawn box
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
    em_y: Optional[float] = None  # glyph height in px when it differs from the pane's X size (stretched in X)
    marker: Optional[str] = None  # a folder that only this game has (Arceus: bin/archive/appli); None for no check
    offset: Tuple[float, float] = (0.0, 0.0)            # the outer layout's parts placement (x right, y up)
    panes: Optional[Tuple[str, ...]] = None            # the message pane names; None picks them by string buffer
    fonts: Optional[Tuple[str, ...]] = None            # the font chain; None uses MESSAGE_FONTS
    shift_y: float = 0.0          # canvas px the game draws the box above its layout position (measured)
    font_px: Optional[float] = None  # glyph px the game draws when it differs from the layout's fontSize (measured)
    speech: Optional[Dict[str, Any]] = None  # measured facts of a box with no layout archive (speech_layout); None: archive
    label: str = ""               # the name the preview's box switch shows (an English source string, tr'd)


# The text is drawn at each pane's own fontSize (the layout's value), unless the spec sets em_y. The font is UDKakugo;
# that is an override, see MESSAGE_FONTS.
# Sword / Shield: msg_00.bflyt, one frame with two text panes (1080 px). MEASURED on the Eden frame (2026-10-17,
# field speech bubble, line "Now I've got to run! See you at mine later!"): the glyph height is 42 px and the X size
# is the layout's 54 (UDKakugo bold). Frame ink box (414, 898)-(1334, 947); render (414, 899)-(1336, 947); centroid
# within 1.2 px. The baseline follows UDKakugo's ascender at 42 px. The bubble picture is not drawn (flat box).
SWORD_SHIELD_BOX = BoxSpec("bin/appli/msg/bin/msg_00.arc", "blyt/msg_00.bflyt", "fcpx/system54_jpn.bfcpx", "bin/font",
                           em_y=42.0)
# Scarlet / Violet: msg_sub_00.bflyt from the sub-window archive (appli/data/msg_sub), two 840 px text panes, no frame.
# MEASURED on the Eden frame (2026-10-17, field: "It's a Skwovet plush made with care using nice, / soft material.",
# shown by an object in the bedroom): the box sits 85 px above the layout (the out animation holds a -85 keyframe;
# the link is not parsed yet) and the glyphs are 41.6 px. Ink-box fit: every edge within 2.2 px (left and top
# within 0.7 px; right of line 1 within 0.2 px; right of line 2 within 2.2 px).
SCARLET_VIOLET_SUB_BOX = BoxSpec("appli/data/msg_sub/msg_sub_body_00.arc", "blyt/msg_sub_00.bflyt",
                                 "fcpx/system32_jpn.bfcpx", "appli/font/bin", background=(38, 42, 52, 255),
                                 shift_y=-85.0, font_px=41.6)
# Legends: Arceus field dialogue: msg_00.bflyt (the same archive as Sword / Shield; the wizard writes it for Arceus). Window
# (405, 790)-(1515, 1016), two panes at x 540, layout size 42 x 52. MEASURED on Eden frames (2026-10-17, field, name
# Laventon, lines "Yes, Pokémon suc" and "My name is Laven" while typing): UDKakugo, X 42 (fit 40.5 to 41.5), glyph
# height about 36. Ink-box error 3 to 5 px over the grid. The marker folder tells Arceus from Sword (Sword has no archive).
ARCEUS_FIELD_BOX = BoxSpec("bin/appli/msg/bin/msg_00.arc", "blyt/msg_00.bflyt", "fcpx/system32_jpn.bfcpx", "bin/font",
                           background=(246, 240, 222, 255), em_y=36.0, marker="bin/archive/appli")
# Legends: Arceus: the battle message box (msg_sys_00_s, in the battle_menu pack, decoded by the wizard). Two 960 px
# panes, no text from the field dialogue yet. Its cliff is weak: 303 battle lines, none above 1.02 of the pane.
ARCEUS_BATTLE_BOX = BoxSpec("bin/archive/appli/battle_menu_eng.gfpak.d/11_msg_sys_00_s.arc", "blyt/msg_sys_00_s.bflyt",
                            "fcpx/system32_jpn.bfcpx", "bin/font", background=(38, 42, 52, 255))
# Legends: Z-A field dialogue: msg_00.bflyt inside ui/data/msg/msg_body_00.arc (the wizard writes it; view_msg_body_00.truiv
# names it). Two 840 px text panes (T_00, T_01), 42 x 52 font, centre-set, colour (54, 54, 76): the same class as the
# Arceus field box. The outer layout msg_body_00.bflyt places it with a parts pane (prt1 L_msg_00: translate (0, -370),
# magnify 1, 1). Window frame: the first wnd1 holding both panes (W_shadow_00). NOT MEASURED: the glyph height is drawn
# at the layout size (no em_y); check against a frame before trusting the wrap or the box position.
ZA_FIELD_BOX = BoxSpec("ui/data/msg/msg_body_00.arc", "blyt/msg_00.bflyt", "fcpx/system42_jpn.bfcpx", "ui/font/bin",
                       offset=(0.0, -370.0), panes=("T_00", "T_01"), fonts=("or_font.otf", "FOT-RodinNTLGPro-DB.otf"),
                       label="Field dialogue box")


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
    return any((root / spec.arc).is_file() and (spec.marker is None or (root / spec.marker).is_dir())
               for root in (folder.parent / "source", folder / "unpacked" / "source"))


def _font_file(font_dir: Path, name: str) -> Optional[Path]:
    """The scrambled font file of an ``.otf`` name in the game's font folder (BFOTF, any case)."""
    stem = name.rsplit(".", 1)[0].lower()
    for path in font_dir.iterdir():
        if path.suffix.lower() in (".bfotf", ".bfttf") and path.stem.lower() == stem:
            return path
    return None


def placed(layout: fm.MessageLayout, spec: BoxSpec) -> fm.MessageLayout:
    """The layout moved by the spec's measured shift, with the spec's glyph size on its message panes."""
    if not spec.shift_y and spec.font_px is None:
        return layout

    def move(rect: fm.Rect) -> fm.Rect:
        return (rect[0], rect[1] + spec.shift_y, rect[2], rect[3] + spec.shift_y)

    panes = [replace(pane, rect=move(pane.rect), size=(spec.font_px or pane.size[0], pane.size[1]))
             for pane in layout.panes]
    window = move(layout.window) if layout.window else None
    return replace(layout, panes=panes, window=window)


def speech_layout(facts: Dict[str, Any], chain: fm.FontChain) -> fm.MessageLayout:
    """A speech bubble as a message layout, from its measured facts (the plugin config's ``speech_bubble``).

    Each line is one text pane at its measured pen x and baseline (canvas px). The glyphs are ``em_y`` high and
    ``x_size`` wide (drawn by ``render_window(em_y=...)``). The pane width is the wrap width. The box is the window.
    """
    em_y = float(facts["em_y"])
    ascent = chain.faces[0].ascent(em_y) if chain.faces else 0.0
    colour = (*(int(v) for v in facts["colour"]), 255)
    wrap = float(facts["wrap_width"])
    panes = []
    for index, line in enumerate(facts["lines"]):
        left = float(line["pen_x"])
        top = float(line["baseline_y"]) - ascent
        panes.append(fm.TextPane(f"speech_{index}", (left, top, left + wrap, top + em_y), 0, 0,
                                 (float(facts["x_size"]), em_y), 0.0, 0.0, 0, 0, colour))
    canvas = tuple(float(v) for v in facts["canvas"])
    return fm.MessageLayout(canvas, tuple(float(v) for v in facts["box"]), panes, list(facts.get("fonts", [])))


def speech_spec(facts: Dict[str, Any], label: str = "Speech bubble") -> BoxSpec:
    """The BoxSpec of a box given by measured or layout-derived facts: its font folder and chain, glyph height, background."""
    return BoxSpec(arc="", member="", fcpx="", font_dir=facts["font_dir"], background=tuple(facts["background"]),
                   em_y=float(facts["em_y"]), fonts=tuple(facts["fonts"]), speech=facts, label=label)


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
            faces = [fm.Face.from_bfotf(path.read_bytes())
                     for path in font_files(root / self._spec.font_dir, self._spec.fonts or MESSAGE_FONTS)]
            chain = fm.FontChain(faces)
            if self._spec.speech is not None:
                layout = speech_layout(self._spec.speech, chain)
            else:
                arc = Sarc((root / self._spec.arc).read_bytes())
                layout = placed(fm.read_layout(arc.files[self._spec.member], arc.files[self._spec.fcpx],
                                               self._spec.offset, self._spec.panes), self._spec)
            result = (layout, chain)
        except (OSError, ValueError, KeyError, IndexError, FileNotFoundError) as exc:
            log_debug(f"switch message preview: no dialogue layout for {self._source_dir}: {exc}")
        if not self._stop.is_set():
            self.loaded.emit((self._project_dir, result, self._spec))


class SwitchMessagePreview(QWidget):
    """The dialogue box of the project (see GameRules.get_custom_preview_widget)."""

    def __init__(self, main_window: Any, spec: BoxSpec, parent: Optional[QWidget] = None,
                 alternatives: Sequence[BoxSpec] = ()):
        super().__init__(parent)
        self._mw = main_window
        self._specs: List[BoxSpec] = [spec] + [other for other in alternatives if other != spec]
        self._spec = spec
        self._text = ""
        self._note = ""
        self._loaded: Optional[Tuple[fm.MessageLayout, fm.FontChain]] = None
        self._loader: Optional[LayoutLoader] = None
        self._source = ""
        self._image: Optional[QImage] = None
        self._choice = QComboBox(self)
        for other in self._specs:
            self._choice.addItem(tr(other.label) if other.label else other.arc)
        self._choice.setVisible(len(self._specs) > 1)
        self._choice.currentIndexChanged.connect(self._on_choice)
        self.setMinimumHeight(140 + _BAR)
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

    def _on_choice(self, index: int) -> None:
        """The box switch: stop the read of the old box and read the chosen one (a stale result is dropped)."""
        if index < 0 or index >= len(self._specs) or self._specs[index] == self._spec:
            return
        if self._loader is not None:
            self._loader.cancel()
            safe_shutdown_thread(self._loader, self._loader, WORKER_STOP_MS)
            self._loader = None
        self._spec = self._specs[index]
        self._loaded = None
        self._image = None
        self._start_load()
        self.update()

    def _on_loaded(self, payload: object) -> None:
        project_dir, result, spec = payload
        if project_dir != self._source or spec != self._spec:
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
        em_y = self._spec.em_y
        # With em_y the glyphs are stretched from em_y to the pane's X size: wrap at the unstretched width.
        stretch = layout.panes[0].size[0] / em_y if em_y else 1.0
        size = em_y or layout.panes[0].size[0]
        page = (split_pages(self._text) or [[]])[0]
        shown: List[str] = []
        too_long = False
        for line, _colour in page:
            parts, long_word = fm.wrap_text(line, width / stretch, chain, size, layout.panes[0].char_space)
            shown += parts
            too_long = too_long or long_word
        lines = [[shown[i]] if i < len(shown) else [] for i in range(len(layout.panes))]
        image = fm.render_window(layout, chain, lines, background=self._spec.background, em_y=em_y)
        self._image = _to_qimage(image)
        notes = []
        if too_long:
            notes.append(tr("A word is wider than the box."))
        if len(shown) > len(layout.panes):
            notes.append(tr("Too many lines for the box: %1 (box holds %2)")
                         % (len(shown), len(layout.panes)))
        self._note = " ".join(notes)
        self.update()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt name
        self._choice.setGeometry(_MARGIN, 4, min(260, max(60, self.width() - 2 * _MARGIN)), _BAR - 8)
        super().resizeEvent(event)

    def paintEvent(self, event: Any) -> None:  # noqa: N802 - Qt name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        if self._image is not None:
            painter.drawImage(_MARGIN, _MARGIN + _BAR, self._image)
        if self._note:
            painter.setPen(QColor(230, 230, 230))
            painter.drawText(_MARGIN, self.height() - 12, self._note)
        painter.end()


def _to_qimage(image: Any) -> QImage:
    rgba = image.convert("RGBA")
    raw = rgba.tobytes("raw", "RGBA")
    return QImage(raw, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888).copy()


__all__ = ["ARCEUS_BATTLE_BOX", "ARCEUS_FIELD_BOX", "BoxSpec", "LayoutLoader", "SCARLET_VIOLET_SUB_BOX", "ZA_FIELD_BOX",
           "SWORD_SHIELD_BOX", "SwitchMessagePreview", "font_files", "sibling_layout_exists", "source_folder",
           "speech_layout", "speech_spec"]
