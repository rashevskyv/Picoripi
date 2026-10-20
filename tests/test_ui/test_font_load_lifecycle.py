"""Real asynchronous font loads: nested jobs, stale requests, cancellation and bounded table filling."""
from threading import Event

from PyQt6 import QtCore

from core import font_formats
from core.font_formats.sources import FontSource
from test_ui.test_font_editor_formats import _qbf_two_letters
from tools.bfn_editor.bfn_editor_window import BfnEditorWindow
from utils import app_mode


def test_nested_font_job_keeps_queue_serial_until_callback_finishes(qtbot, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    editor = BfnEditorWindow()
    qtbot.addWidget(editor)
    entered, release = Event(), Event()
    results = []

    def second():
        entered.set()
        assert release.wait(5)
        return "second"

    def first_done(result, error):
        results.append((result, error))
        editor.run_font_job(second, lambda result, error: results.append((result, error)))

    try:
        editor.run_font_job(lambda: "first", first_done)
        qtbot.waitUntil(entered.is_set, timeout=5000)
        assert editor._font_job is not None
        editor.run_font_job(lambda: "third", lambda result, error: results.append((result, error)))
        release.set()
        qtbot.waitUntil(lambda: len(results) == 3, timeout=5000)
        assert results == [("first", ""), ("second", ""), ("third", "")]
    finally:
        release.set()
        qtbot.waitUntil(lambda: editor._font_job is None, timeout=5000)


def test_latest_plugin_font_wins_without_losing_queued_save(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    entered, release = Event(), Event()

    class SlowSource(FontSource):
        def read_current(self):
            entered.set()
            assert release.wait(5)
            return super().read_current()

    first = tmp_path / "first.qbf"
    second = tmp_path / "second.qbf"
    first.write_bytes(_qbf_two_letters())
    second.write_bytes(_qbf_two_letters())
    editor = BfnEditorWindow()
    qtbot.addWidget(editor)
    completed = []
    try:
        editor.load_font_source(SlowSource("First", "qbf", str(first), ""))
        assert not editor._font_progress.isHidden()
        qtbot.waitUntil(entered.is_set, timeout=5000)
        editor.run_font_job(lambda: "saved", lambda result, error: completed.append((result, error)))
        editor.load_font_source(FontSource("Second", "qbf", str(second), ""))
        release.set()
        qtbot.waitUntil(lambda: editor.current_bfn_name == "Second" and not editor._font_loading, timeout=5000)
        assert completed == [("saved", "")]
        assert editor.font_source.label == "Second"
        assert editor.metadata["MAP1"]
        assert editor.table_glyphs.rowCount() > 0
        assert editor.sheet_images[0].pixelColor(0, 0).alpha() > 0
    finally:
        release.set()
        qtbot.waitUntil(lambda: editor._font_job is None, timeout=5000)


def test_close_during_decode_discards_result_but_finishes_queued_write(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    entered, release, finished = Event(), Event(), Event()
    extract = font_formats.extract

    def blocked_extract(*args):
        entered.set()
        assert release.wait(5)
        result = extract(*args)
        finished.set()
        return result

    monkeypatch.setattr(font_formats, "extract", blocked_extract)
    editor = BfnEditorWindow()
    qtbot.addWidget(editor)
    saved = tmp_path / "queued-save.txt"
    callbacks = []
    try:
        editor.load_formatted_bytes(_qbf_two_letters(), "font.qbf", "qbf", {})
        qtbot.waitUntil(entered.is_set, timeout=5000)
        editor.run_font_job(lambda: saved.write_text("Saved", encoding="utf-8"),
                            lambda *_: callbacks.append("must not touch the closed window"))
        editor.close()
        assert editor._font_closed
        assert editor.temp_dir == ""
        release.set()
        qtbot.waitUntil(finished.is_set, timeout=5000)
        qtbot.waitUntil(saved.exists, timeout=5000)
        assert saved.read_text(encoding="utf-8") == "Saved"
        assert callbacks == []
        assert editor.metadata == {}
        assert editor.temp_dir == ""
    finally:
        release.set()


def test_large_glyph_table_yields_and_can_cancel_without_stale_rows(qtbot, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    editor = BfnEditorWindow()
    qtbot.addWidget(editor)
    metadata, sheets = font_formats.extract("qbf", _qbf_two_letters(), {})
    metadata["GLY1"][0]["end_glyph"] = 9999
    metadata["MAP1"] = [{"mapping_type": 2, "first_char": 0x1000, "entries": list(range(10000))}]
    from tools.bfn_editor.io_format_mixin import pil_to_qimage
    editor.metadata = metadata
    editor.sheet_images = [pil_to_qimage(sheets[0])]
    editor.start_glyph, editor.end_glyph = 0, 9999
    editor.rows, editor.cols, editor.cell_w, editor.cell_h = 2, 1, 4, 4
    editor.first_code = 0
    editor.populate_glyph_table()
    assert editor._font_loading
    assert editor.table_glyphs.item(9999, 3) is None
    observed = []
    timer = QtCore.QTimer(editor)
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: observed.append(editor.table_glyphs.item(9999, 3)))
    timer.start(0)
    qtbot.waitUntil(lambda: bool(observed), timeout=5000)
    assert observed == [None]
    editor.cancel_font_load()
    assert not editor._font_loading
    assert editor.table_glyphs.rowCount() == 0
    assert not editor.table_glyphs.isEnabled()
    assert editor.status.currentMessage() == "Font loading cancelled."


def test_mapping_index_preserves_precedence_and_avoids_per_glyph_scans(qtbot, monkeypatch):
    editor = BfnEditorWindow()
    qtbot.addWidget(editor)
    editor.start_glyph, editor.end_glyph = 0, 9999
    maps = [{"mapping_type": 3, "entries": [65, 66, 1, 2]},
            {"mapping_type": 2, "first_char": 0x1000, "entries": list(range(10000))}]

    def no_scan(*_args):
        raise AssertionError("the table must index the map instead of scanning once for every glyph")

    monkeypatch.setattr(editor, "_resolve_char_from_maps", no_scan)
    result = editor._build_glyph_to_char_mapping(maps)
    assert len(result) == 10000
    assert result[1] == ("A", "A")
    assert result[2] == ("B", "B")
    assert result[9999] == (chr(0x1000 + 9999), chr(0x1000 + 9999))


def test_cancel_before_decoding_keeps_the_accepted_font(qtbot, tmp_path, monkeypatch):
    editor = BfnEditorWindow()
    qtbot.addWidget(editor)
    editor.load_formatted_bytes(_qbf_two_letters(), "accepted.qbf", "qbf", {})
    accepted = editor.metadata
    rows = editor.table_glyphs.rowCount()
    monkeypatch.setattr(app_mode, "headless", False)
    entered, release = Event(), Event()

    class SlowSource(FontSource):
        def read_current(self):
            entered.set()
            assert release.wait(5)
            return _qbf_two_letters()

    try:
        editor.load_font_source(SlowSource("Cancelled", "qbf", str(tmp_path / "unused"), ""))
        qtbot.waitUntil(entered.is_set, timeout=5000)
        editor.cancel_font_load()
        release.set()
        qtbot.waitUntil(lambda: editor._font_job is None, timeout=5000)
        assert editor.metadata is accepted
        assert editor.table_glyphs.rowCount() == rows
        assert editor.table_glyphs.isEnabled()
    finally:
        release.set()
