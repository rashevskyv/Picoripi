"""Asynchronous preview font preparation off the UI thread: worker decoding, responsiveness, stale/closed project rejection."""
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.font_formats.sources import FontSource
from core.settings.font_map_loader import FontMapLoader
from test_ui.test_font_editor_formats import _qbf_two_letters
from utils import app_mode


def test_preview_font_reading_and_decoding_runs_off_ui_thread(qtbot, tmp_path, monkeypatch):
    """Proves font reading, decoding and QImage building run on a worker thread, not the UI thread."""
    monkeypatch.setattr(app_mode, "headless", False)

    font_path = tmp_path / "test.qbf"
    font_path.write_bytes(_qbf_two_letters())

    read_threads = []
    extract_threads = []

    from core import font_formats
    real_extract = font_formats.extract
    real_read = FontSource.read_current

    def recording_extract(fmt, raw_bytes, params):
        extract_threads.append(threading.get_ident())
        return real_extract(fmt, raw_bytes, params)

    def recording_read(self):
        read_threads.append(threading.get_ident())
        return real_read(self)

    monkeypatch.setattr(font_formats, "extract", recording_extract)
    monkeypatch.setattr(FontSource, "read_current", recording_read)

    project = SimpleNamespace(metadata={"source_path": str(tmp_path)})
    pm = SimpleNamespace(project=project, project_dir=str(tmp_path))

    status_messages = []
    status_cleared = []
    status_bar = MagicMock()
    status_bar.showMessage.side_effect = lambda msg, *args: status_messages.append((msg, args))
    status_bar.clearMessage.side_effect = lambda: status_cleared.append(True)

    mw = SimpleNamespace(
        all_font_maps={},
        all_bfn_fonts={},
        project_manager=pm,
        statusBar=lambda: status_bar,
        current_game_rules=SimpleNamespace(
            get_font_sources=lambda: [
                {"label": "Test Font", "format": "qbf", "path": str(font_path), "preview": True}
            ]
        ),
    )

    main_thread_id = threading.get_ident()
    loader = FontMapLoader(mw)

    loader._load_preview_fonts(pm)
    assert loader.preview_scan_running
    # Status bar was shown without a 2000ms timeout
    assert len(status_messages) == 1
    assert status_messages[0][1] == () or status_messages[0][1] == (0,)

    qtbot.waitUntil(lambda: not loader.preview_scan_running, timeout=10000)

    # Both file reading and format extraction ran strictly on background thread
    assert len(read_threads) > 0
    assert main_thread_id not in read_threads
    assert len(extract_threads) > 0
    assert main_thread_id not in extract_threads

    # Status was cleared on completion
    assert len(status_cleared) > 0

    # Prepared font was applied to main window
    assert "test.json" in mw.all_font_maps
    assert "test.json" in mw.all_bfn_fonts
    bfn = mw.all_bfn_fonts["test.json"]
    assert hasattr(bfn, "_qimages_cache")
    assert len(bfn._qimages_cache) > 0


def test_preview_font_stale_generation_and_closed_project_ignored(qtbot, tmp_path, monkeypatch):
    """Proves results from an older generation or a closed project are discarded."""
    monkeypatch.setattr(app_mode, "headless", False)

    font_path = tmp_path / "test.qbf"
    font_path.write_bytes(_qbf_two_letters())

    project = SimpleNamespace(metadata={"source_path": str(tmp_path)})
    pm = SimpleNamespace(project=project, project_dir=str(tmp_path))

    status_bar = MagicMock()
    mw = SimpleNamespace(
        all_font_maps={},
        all_bfn_fonts={},
        project_manager=pm,
        statusBar=lambda: status_bar,
        current_game_rules=SimpleNamespace(
            get_font_sources=lambda: [
                {"label": "Test Font", "format": "qbf", "path": str(font_path), "preview": True}
            ]
        ),
    )

    loader = FontMapLoader(mw)

    # 1. Stale generation test
    loader._preview_generation = 5
    # Simulate a delayed result from generation 4
    loader._preview_scan_done([("stale.json", {}, None)], "", 4)
    assert "stale.json" not in mw.all_font_maps

    # 2. Closed project test
    pm.project = None  # Project closed before worker finishes
    loader._preview_scan_done([("closed.json", {}, None)], "", 5)
    assert "closed.json" not in mw.all_font_maps
