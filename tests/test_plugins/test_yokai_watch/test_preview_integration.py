"""Integration tests for Yo-kai Watch preview geometry, font-driven preview availability,

actual rendered glyph pixels, edit updates, color/page tags, hero context, and asynchronous lifecycle.
"""
import romhacking_root
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from PyQt6 import QtCore
from PyQt6.QtGui import QImage, QPainter

from core.settings.font_map_loader import FontMapLoader
from plugins.testing import load_rules
from ui.components.bfn_preview_widget import BfnPreviewWidget
from utils import app_mode


def _make_synthetic_yokai_font() -> bytes:
    from PIL import Image, ImageDraw
    from test_core.test_level5_formats import make_xf
    atlas = Image.new("RGBA", (128, 128), (0, 0, 0, 255))
    draw = ImageDraw.Draw(atlas)
    chars = []
    for i, c in enumerate(range(32, 127)):
        col = (i % 16) * 8
        row = (i // 16) * 8
        draw.rectangle((col + 1, row + 1, col + 6, row + 7), outline=(255, 255, 255, 255), fill=(255, 255, 255, 255))
        chars.append((c, 8, (0, 1, 6, 7), (col + 1, row + 1, 0)))
    chars.sort(key=lambda item: item[0])
    return make_xf(atlas, chars)


def _get_or_make_yokai_font(tmp_path: Path) -> Path:
    """Provides a real or synthetic Yo-kai Watch XF font in the expected project directory."""
    target = tmp_path / "fnt" / "ft_nrm.xf"
    target.parent.mkdir(parents=True, exist_ok=True)
    real_3ds_font = romhacking_root.under(r"Yo-kai Watch\Yo-kai Watch\3DS\source\fnt\ft_nrm.xf")
    if real_3ds_font.is_file():
        target.write_bytes(real_3ds_font.read_bytes())
    else:
        target.write_bytes(_make_synthetic_yokai_font())
    return target


def _render_widget_bytes(widget: BfnPreviewWidget) -> bytes:
    """Renders the preview widget to an image via _paint_event_impl and returns its pixel buffer bytes."""
    img = QImage(widget.size(), QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    try:
        widget._paint_event_impl(p, None)
    finally:
        p.end()
    return bytes(img.bits().asarray(img.sizeInBytes()))


def test_advertised_line_counts_fit_declared_text_areas():
    """Verify that for every platform (3DS, Switch) and preset, the advertised line count fits within the text area height."""
    rules = load_rules("yokai_watch")

    # 1. 3DS styles (yw1, yw2, yw3)
    rules._game = lambda root=None: "yw1"
    dialogue_3ds = rules.get_preview_window_style()
    assert dialogue_3ds["lines_per_page"] == 2
    geom_d = dialogue_3ds["geometry"]
    metrics_d = geom_d["text_metrics"]
    height_needed_2lines = metrics_d["font_y"] + 1 * metrics_d["line_space"]  # 18 + 22 = 40
    assert height_needed_2lines <= geom_d["text"][3]  # 40 <= 62

    system_3ds = rules.get_window_style_for_preset("system")
    assert system_3ds["lines_per_page"] == 4
    geom_s = system_3ds["geometry"]
    metrics_s = geom_s["text_metrics"]
    height_needed_4lines = metrics_s["font_y"] + 3 * metrics_s["line_space"]  # 18 + 66 = 84
    assert height_needed_4lines <= geom_s["text"][3]  # 84 <= 94

    # 2. Switch styles (ywnx)
    rules._game = lambda root=None: "ywnx"
    dialogue_nx = rules.get_preview_window_style()
    assert dialogue_nx["lines_per_page"] == 2
    geom_nx_d = dialogue_nx["geometry"]
    metrics_nx_d = geom_nx_d["text_metrics"]
    nx_2lines_height = metrics_nx_d["font_y"] + 1 * metrics_nx_d["line_space"]  # 51 + 62 = 113
    assert nx_2lines_height <= geom_nx_d["text"][3]  # 113 <= 190

    system_nx = rules.get_window_style_for_preset("system")
    assert system_nx["lines_per_page"] == 4
    geom_nx_s = system_nx["geometry"]
    metrics_nx_s = geom_nx_s["text_metrics"]
    nx_4lines_height = metrics_nx_s["font_y"] + 3 * metrics_nx_s["line_space"]  # 51 + 3 * 62 = 237
    assert nx_4lines_height <= geom_nx_s["text"][3]  # 237 <= 290

    # 3. YW4 and Academy Y do not enable approximate 3DS preview
    rules._game = lambda root=None: "yw4"
    assert "message_window_preview" not in rules.get_capabilities()
    assert rules.get_preview_window_style() is None
    assert rules.get_window_style_for_preset("dialogue") is None


def test_player_name_placeholders_respect_hero_and_gender_context():
    """Verify {PNAME} resolves to Nate or Katie based on context (_f_ vs _m_) and explicit gender tags."""
    rules = load_rules("yokai_watch")

    # A. Explicit tags
    clean_m, _, _, _ = rules.prepare_preview_glyph_text("Hey, {PNAMEM}!")
    assert clean_m == "Hey, Nate!"
    clean_f, _, _, _ = rules.prepare_preview_glyph_text("Hey, {PNAMEF}!")
    assert clean_f == "Hey, Katie!"
    clean_02, _, _, _ = rules.prepare_preview_glyph_text("Hey, {PNAME02}!")
    assert clean_02 == "Katie" or clean_02 == "Hey, Katie!"
    # A tag that only ends in _F is not a hero tag.
    clean_other, _, _, _ = rules.prepare_preview_glyph_text("Hey, {ITEM_F}!")
    assert clean_other == "Hey, !"

    # B. Row context: _f_ route file -> Katie
    mw_mock = MagicMock()
    ds_mock = MagicMock()
    ds_mock.physical_block_idx = 0
    ds_mock.current_string_idx = 0
    mw_mock.data_store = ds_mock
    rules.mw = mw_mock

    row_mock = SimpleNamespace(kind="TEXT_INFO", param=2)
    rules._row = lambda b, s: ("data/txt/ev/en/ev010_01_f_en.cfg.bin", row_mock, None)

    clean_context_f, _, _, _ = rules.prepare_preview_glyph_text("Hello, {PNAME}!")
    assert clean_context_f == "Hello, Katie!"

    # Mock _row returning a path with _m_ -> Nate
    rules._row = lambda b, s: ("data/txt/ev/en/ev010_01_m_en.cfg.bin", row_mock, None)
    clean_context_m, _, _, _ = rules.prepare_preview_glyph_text("Hello, {PNAME}!")
    assert clean_context_m == "Hello, Nate!"


def test_preview_availability_and_actual_rendered_pixel_output(qtbot, tmp_path):
    """End-to-end integration: preview availability before/after font load, actual glyph pixels,

    translation edit updates, color tags, page breaks, and hero context substitution.
    """
    _get_or_make_yokai_font(tmp_path)

    project = SimpleNamespace(metadata={"source_path": str(tmp_path)})
    pm = SimpleNamespace(project=project, project_dir=str(tmp_path))

    rules = load_rules("yokai_watch")
    rules._game = lambda root=None: "yw1"

    row_mock = SimpleNamespace(kind="TEXT_INFO", param=2, text_id="txt1", number=1, text="")
    rules._row = lambda b, s: ("data/txt/ev/en/ev001_01_m_en.cfg.bin", row_mock, None)

    status_bar = MagicMock()
    mw = SimpleNamespace(
        all_font_maps={},
        all_bfn_fonts={},
        preview_enabled=True,
        project_manager=pm,
        current_game_rules=rules,
        default_font_file="ft_nrm.json",
        data_store=SimpleNamespace(physical_block_idx=0, current_string_idx=0),
        statusBar=lambda: status_bar,
    )
    rules.mw = mw

    widget = BfnPreviewWidget(mw)
    qtbot.addWidget(widget)
    widget.resize(400, 240)

    # 1. Before font is loaded: active font is None
    assert widget.get_active_bfn_font() is None

    # 2. Load preview fonts through FontMapLoader
    loader = FontMapLoader(mw)
    loader._load_preview_fonts(pm)
    if loader.preview_scan_running:
        qtbot.waitUntil(lambda: not loader.preview_scan_running, timeout=10000)

    # Font is loaded into all_bfn_fonts and preview becomes available
    assert "ft_nrm.json" in mw.all_bfn_fonts
    loaded_font = mw.all_bfn_fonts["ft_nrm.json"]
    assert widget.get_active_bfn_font() == loaded_font
    assert len(loaded_font.get_sheets_qimages()) > 0

    # 3. Selected dialogue renders actual glyph pixels
    raw_dialogue = "Look, {CR}fire{/C} and {CG}leaf{/C}!{PAGE}Page two."
    widget.update_preview_text(raw_dialogue)
    img = QImage(widget.size(), QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    try:
        widget._paint_event_impl(p, None)
    finally:
        p.end()
    rendered_colors = set(img.pixelColor(x, y).name() for x in range(img.width()) for y in range(img.height()))
    assert len(rendered_colors) > 2  # Has background plus glyph edge and body colors

    # 4. Editing translation updates the rendered pixels
    bytes_initial = _render_widget_bytes(widget)
    edited_translation = "Edited dialogue text"
    widget.update_preview_text(edited_translation)
    bytes_edited = _render_widget_bytes(widget)
    assert bytes_initial != bytes_edited

    # 5. Color tags produce distinct rendered pixel buffers on the SAME supported text
    widget.update_preview_text("{CR}fire{/C}")
    img_red = QImage(widget.size(), QImage.Format.Format_ARGB32)
    img_red.fill(0)
    p = QPainter(img_red)
    try:
        widget._paint_event_impl(p, None)
    finally:
        p.end()
    bytes_red = bytes(img_red.bits().asarray(img_red.sizeInBytes()))

    widget.update_preview_text("{CG}fire{/C}")
    img_green = QImage(widget.size(), QImage.Format.Format_ARGB32)
    img_green.fill(0)
    p = QPainter(img_green)
    try:
        widget._paint_event_impl(p, None)
    finally:
        p.end()
    bytes_green = bytes(img_green.bits().asarray(img_green.sizeInBytes()))

    assert bytes_red != bytes_green

    # Discriminating pixel assertion: red dominant in img_red, green dominant in img_green at the same coords
    red_glyph_pixels = [
        (x, y)
        for x in range(img_red.width())
        for y in range(img_red.height())
        if img_red.pixelColor(x, y).red() > 180 and img_red.pixelColor(x, y).green() < 100
    ]
    assert len(red_glyph_pixels) > 0
    green_at_same_coords = [
        (x, y)
        for (x, y) in red_glyph_pixels
        if img_green.pixelColor(x, y).green() > 150 and img_green.pixelColor(x, y).red() < 100
    ]
    assert len(green_at_same_coords) > 0

    # 6. Page breaks ({PAGE}) separate dialogue pages
    widget.update_preview_text("First dialogue page{PAGE}Second dialogue page")
    widget._preview_page = 0
    bytes_page0 = _render_widget_bytes(widget)
    widget._preview_page = 1
    bytes_page1 = _render_widget_bytes(widget)
    assert bytes_page0 != bytes_page1
    widget._preview_page = 0

    # 7. Hero context substitution ({PNAME}) changes rendered output and handles row-switch caching
    # Setup row resolution based on string_idx: s=0 is male route (Nate), s=1 is female route (Katie)
    rules._row = lambda b, s: (
        "data/txt/ev/en/ev010_01_m_en.cfg.bin" if s == 0 else "data/txt/ev/en/ev010_01_f_en.cfg.bin",
        row_mock,
        None,
    )

    # A. Select male row (string_idx = 0) and update preview with "Hey, {PNAME}!"
    mw.data_store.current_string_idx = 0
    widget.update_preview_text("Hey, {PNAME}!")
    assert widget._preview_page == 0
    bytes_nate_1 = _render_widget_bytes(widget)

    # B. Select female row (string_idx = 1) and update preview with identical raw text
    # No private cache clearing! Normal preview update must invalidate or distinguish row context.
    mw.data_store.current_string_idx = 1
    widget.update_preview_text("Hey, {PNAME}!")
    assert widget._preview_page == 0
    bytes_katie = _render_widget_bytes(widget)
    assert bytes_nate_1 != bytes_katie

    # C. Reverse transition: select male row again (string_idx = 0)
    mw.data_store.current_string_idx = 0
    widget.update_preview_text("Hey, {PNAME}!")
    assert widget._preview_page == 0
    bytes_nate_2 = _render_widget_bytes(widget)
    assert bytes_nate_2 == bytes_nate_1
    assert bytes_nate_2 != bytes_katie


def test_preview_font_loading_worker_barrier_and_closed_project_discard(qtbot, tmp_path, monkeypatch):
    """Proves the UI event loop processes events (heartbeat) during font decoding,

    and that closing the project in-flight cleanly discards obsolete fonts.
    """
    monkeypatch.setattr(app_mode, "headless", False)
    _get_or_make_yokai_font(tmp_path)

    project = SimpleNamespace(metadata={"source_path": str(tmp_path)})
    pm = SimpleNamespace(project=project, project_dir=str(tmp_path))

    rules = load_rules("yokai_watch")
    rules._game = lambda root=None: "yw1"

    status_bar = MagicMock()
    mw = SimpleNamespace(
        all_font_maps={},
        all_bfn_fonts={},
        project_manager=pm,
        current_game_rules=rules,
        statusBar=lambda: status_bar,
    )

    entered = threading.Event()
    release = threading.Event()

    from core import font_formats
    real_extract = font_formats.extract

    def barrier_extract(fmt, raw_bytes, params):
        entered.set()
        assert release.wait(10)
        return real_extract(fmt, raw_bytes, params)

    monkeypatch.setattr(font_formats, "extract", barrier_extract)

    loader = FontMapLoader(mw)

    # Start font load in background worker
    loader._load_preview_fonts(pm)
    assert loader.preview_scan_running

    # Set up UI-thread heartbeat timer to verify event loop responsiveness during decoding
    heartbeats = []
    timer = QtCore.QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: heartbeats.append(True))
    timer.start()

    # Wait until background worker enters the decoding barrier
    qtbot.waitUntil(entered.is_set, timeout=5000)

    # Verify UI thread is responsive: heartbeat timer fires while worker is blocked
    qtbot.waitUntil(lambda: len(heartbeats) >= 3, timeout=5000)
    timer.stop()

    # Close project while worker is still extracting
    pm.project = None

    # Release worker and wait for worker completion
    release.set()
    qtbot.waitUntil(lambda: not loader.preview_scan_running, timeout=10000)

    # Closed project must not receive the obsolete font
    assert "ft_nrm.json" not in mw.all_font_maps
    assert "ft_nrm.json" not in mw.all_bfn_fonts

    # Now verify normal loading completes when project remains open
    entered2 = threading.Event()
    release2 = threading.Event()

    def barrier_extract2(fmt, raw_bytes, params):
        entered2.set()
        assert release2.wait(10)
        return real_extract(fmt, raw_bytes, params)

    monkeypatch.setattr(font_formats, "extract", barrier_extract2)

    pm.project = project  # Reopen project
    loader._load_preview_fonts(pm)
    assert loader.preview_scan_running

    qtbot.waitUntil(entered2.is_set, timeout=5000)
    release2.set()
    qtbot.waitUntil(lambda: not loader.preview_scan_running, timeout=10000)

    # Prepared font was applied to active project
    assert "ft_nrm.json" in mw.all_font_maps
    assert "ft_nrm.json" in mw.all_bfn_fonts
