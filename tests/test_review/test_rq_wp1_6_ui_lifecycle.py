"""REVIEW_QUEUE WP6: exit while work runs in the background, and opening a second project while the first loads.

A real MainWindow in interactive mode (``app_mode.headless`` False): workers run on their own threads and the
event loop delivers their results, as in the application.
"""
import time

import pytest

from test_review._rq_wp1_6_helpers import BoxAnswerer, FakeAIServer, make_plain_project, open_project
from utils import app_mode


@pytest.fixture
def interactive(qtbot, tmp_path, monkeypatch):
    """``make()`` -> a real MainWindow in interactive mode, with settings of this test alone.

    Every message box is answered (closed) by a BoxAnswerer, available as ``make.boxes``.
    """
    import sys

    import core.settings_manager as settings_manager
    import utils.constants as constants
    from core.translation.script_speaker_finder import ScriptSpeakerFinder
    from main import MainWindow

    settings_dir = tmp_path / "settings"
    settings_file = str(settings_dir / "settings.json")
    for module in (constants, settings_manager):
        monkeypatch.setattr(module, "SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(module, "SETTINGS_FILE_PATH", settings_file)
    if "main" in sys.modules:
        monkeypatch.setattr(sys.modules["main"], "SETTINGS_FILE_PATH", settings_file, raising=False)
    monkeypatch.setattr(app_mode, "headless", False)
    # No game script of this machine (the working directory is searched too) may feed speakers or chapters.
    monkeypatch.setattr(ScriptSpeakerFinder, "find_script_path", lambda self: None)
    windows = []
    boxes = BoxAnswerer()

    def make():
        mw = MainWindow()
        qtbot.addWidget(mw)
        # Interactive mode keeps a spell cache next to the dictionary in the working tree; not this one.
        mw.spellchecker_manager._cache_file = tmp_path / "spell_cache.json"
        windows.append(mw)
        return mw

    make.boxes = boxes
    yield make
    boxes.stop()
    for mw in windows:
        try:
            mw.is_testing = True
            mw.close()
        except RuntimeError:
            pass


def project(root, blocks):
    """A plain_text project with its own (empty) MemPalace database, so none is looked up next to the cwd."""
    from core.mempalace_client import MemePalaceClient

    project_file = make_plain_project(root, blocks)
    MemePalaceClient(project_dir=str(project_file.parent))
    return project_file


def _running_threads():
    from utils import thread_utils
    return [t for t in list(thread_utils._running) + [t for t, _ in thread_utils._parked] if t.isRunning()]


# ------------------------------------------------------------- exit while busy

MISSPELLED = ["котт", "привітт"]  # the uk dictionary accepts any Latin word


def _spellchecker_ready(mw, qtbot):
    """Turn the spellchecker on and let its background lookup learn the misspelled words of the test text."""
    scm = mw.spellchecker_manager
    scm.set_enabled(True)
    qtbot.waitUntil(lambda: scm.hunspell is not None, timeout=30000)
    for word in MISSPELLED:
        scm.is_misspelled(word)
    qtbot.waitUntil(lambda: all(scm._spell_cache.get(word) for word in MISSPELLED), timeout=10000)


def test_exit_while_search_spellcheck_and_glossary_build_run(interactive, qtbot, tmp_path, monkeypatch):
    """Close at once: every thread is asked to stop and waited for (8 s at most), and no error box appears."""
    from utils.thread_utils import wait_for_threads_at_exit

    held = FakeAIServer(reply=lambda body: (held.release.wait(30), (200, {}, FakeAIServer.completion("[]")))[1])
    try:
        lines = [f"Line {n} of the long journey, {' '.join(MISSPELLED)} again" for n in range(400)]
        mw = interactive()
        open_project(mw, project(tmp_path, {"a": lines, "b": lines[:50]}), monkeypatch, qtbot)
        _spellchecker_ready(mw, qtbot)
        mw.glossary_ai = {"provider": "OpenAI Compatible", "endpoint": held.url, "model": "m", "chunk_size": 1000}

        mw.build_glossary_with_ai(block_idx=0)
        qtbot.waitUntil(lambda: len(held.requests) == 1, timeout=10000)  # a glossary request is in flight
        glossary_thread = mw.glossary_builder_handler._thread
        mw.helper.open_advanced_search("journy", False, False, False, True)
        mw.block_list_widget._open_spellcheck_for_block(0)
        search, spellcheck = mw.active_search_dialog, mw.active_spellcheck_dialog
        # Both dialogs start their worker from a 50 ms timer.
        qtbot.waitUntil(lambda: hasattr(search, "search_worker") and hasattr(spellcheck, "analysis_worker"))
        assert glossary_thread is not None and glossary_thread.isRunning()

        started = time.monotonic()
        mw.close()
        wait_for_threads_at_exit()
        elapsed = time.monotonic() - started

        assert elapsed < 8.5
        assert _running_threads() == []
        assert not glossary_thread.isRunning()
        qtbot.wait(300)  # results queued by the stopped workers are delivered now, while the window still exists
        assert [box for box in interactive.boxes.seen if box["icon"] in ("Critical", "Warning")] == []
    finally:
        held.stop()


def test_closing_during_a_glossary_build_opens_no_message_box(interactive, qtbot, tmp_path, monkeypatch):
    held = FakeAIServer(reply=lambda body: (held.release.wait(30), (200, {}, FakeAIServer.completion("[]")))[1])
    try:
        mw = interactive()
        open_project(mw, project(tmp_path, {"a": ["The hero walks.", "The princess waits."]}), monkeypatch, qtbot)
        mw.glossary_ai = {"provider": "OpenAI Compatible", "endpoint": held.url, "model": "m", "chunk_size": 1000}
        mw.build_glossary_with_ai(block_idx=0)
        qtbot.waitUntil(lambda: len(held.requests) == 1, timeout=10000)
        seen_before = len(interactive.boxes.seen)

        mw.close()
        qtbot.wait(300)

        assert [(box["title"], box["text"]) for box in interactive.boxes.seen[seen_before:]] == []
    finally:
        held.stop()


class _SlowDictionary:
    """A dictionary that takes 5 ms a word, as a large uncached spellcheck does."""

    def lookup(self, word):
        time.sleep(0.005)
        return False


class _Spellchecker:
    custom_words = set()

    def __init__(self):
        self._spell_cache = {}
        self.hunspell = _SlowDictionary()


def test_a_long_spellcheck_stops_when_the_application_quits(qtbot):
    from dialogs.spellcheck_dialog import SpellcheckAnalysisWorker
    from utils.thread_utils import wait_for_threads_at_exit

    words = ["w" + "".join(chr(97 + (n // 26 ** p) % 26) for p in range(3)) for n in range(8000)]  # unique, letters
    text = "\n".join(" ".join(words[n:n + 20]) for n in range(0, len(words), 20))
    worker = SpellcheckAnalysisWorker(text, _Spellchecker())
    worker.start()
    try:
        wait_for_threads_at_exit(timeout_ms=1500)

        assert not worker.isRunning()
    finally:
        worker.cancel()
        worker.wait(10000)


# ---------------------------------------------- second project while loading

def _block_texts(mw):
    return [list(block) for block in mw.data_store.data]


@pytest.mark.parametrize("when", ["while_reading", "after_reading_before_delivery"])
def test_a_second_project_opened_while_the_first_loads_shows_only_its_own_blocks(
        when, interactive, qtbot, tmp_path, monkeypatch):
    import handlers.project_action.lifecycle_mixin as lifecycle

    first = project(tmp_path / "first", {f"first_{n:02d}": [f"first {n} line {k}" for k in range(300)] for n in range(40)})
    second = project(tmp_path / "second", {"second_a": ["second a0", "second a1"], "second_b": ["second b0"]})
    mw = interactive()
    monkeypatch.setattr(lifecycle.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(first), "")))
    mw.project_action_handler.open_project_action()
    worker = mw.project_action_handler._active_load_worker
    assert worker.isRunning()
    if when == "after_reading_before_delivery":
        # The first load has emitted its result; the event loop has not delivered it yet.
        assert worker.wait(20000)

    open_project(mw, second, monkeypatch, qtbot)
    qtbot.wait(300)  # anything the first load still had queued would arrive now

    assert _block_texts(mw) == [["second a0", "second a1"], ["second b0"]]
    assert sorted(mw.data_store.block_names.values()) == ["second_a", "second_b"]
    tree = mw.block_list_widget
    names = [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
    assert not any(name.startswith("first_") for name in names)
    assert {"second_a", "second_b"} <= {name.split(" ")[0] for name in names}


# ------------------------------------- the application with the test switches gone (6.4)

def _visible_progress(mw, title):
    from PyQt6.QtWidgets import QProgressDialog
    return [d for d in mw.findChildren(QProgressDialog) if d.windowTitle() == title and d.isVisible()]


def test_project_open_shows_a_progress_window_until_the_blocks_are_in(interactive, qtbot, tmp_path, monkeypatch):
    import handlers.project_action.lifecycle_mixin as lifecycle
    from PyQt6.QtCore import QEvent, QObject
    from PyQt6.QtWidgets import QApplication, QProgressDialog

    class ShownProgress(QObject):
        titles = []

        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Show and isinstance(obj, QProgressDialog):
                self.titles.append(obj.windowTitle())
            return False

    spy = ShownProgress()
    QApplication.instance().installEventFilter(spy)
    try:
        project_file = project(tmp_path, {f"b{n}": [f"line {k}" for k in range(50)] for n in range(10)})
        mw = interactive()
        mw.show()
        monkeypatch.setattr(lifecycle.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(project_file), "")))
        mw.project_action_handler.open_project_action()

        assert mw.project_action_handler._active_load_worker.isRunning()  # read on its own thread
        qtbot.waitUntil(lambda: len(mw.data_store.data) == 10 and not mw.is_loading_data, timeout=15000)
        qtbot.waitUntil(lambda: not _visible_progress(mw, "Loading Project"), timeout=15000)
        assert "Loading Project" in spy.titles
    finally:
        QApplication.instance().removeEventFilter(spy)


def _select_string(mw, qtbot, block_idx, string_idx):
    """Click the block in the tree, then the line in the preview."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTreeWidgetItemIterator

    tree = mw.block_list_widget
    iterator = QTreeWidgetItemIterator(tree)
    while iterator.value():
        item = iterator.value()
        if item.data(0, Qt.ItemDataRole.UserRole) == block_idx:
            tree.setCurrentItem(item)
            break
        iterator += 1
    qtbot.waitUntil(lambda: mw.data_store.current_block_idx == block_idx, timeout=5000)
    mw.list_selection_handler.string_selected_from_preview(string_idx)
    qtbot.waitUntil(lambda: mw.data_store.current_string_idx == string_idx, timeout=5000)


def test_ctrl_s_shows_a_progress_window_then_saves(interactive, qtbot, tmp_path, monkeypatch):
    from components.toast import ToastNotification

    project_file = project(tmp_path, {"a": ["Hello", "World"]})
    mw = interactive()
    open_project(mw, project_file, monkeypatch, qtbot)
    mw.data_processor.update_edited_data(0, 1, "Світ")
    target = tmp_path / "translation" / "a.txt"

    mw.save_action.trigger()  # Ctrl+S

    assert _visible_progress(mw, "Saving Changes")
    qtbot.waitUntil(lambda: mw.app_action_handler.save_worker is None, timeout=15000)
    assert not _visible_progress(mw, "Saving Changes")
    assert target.read_text(encoding="utf-8").splitlines() == ["Hello", "Світ"]
    assert mw.data_store.unsaved_changes is False
    assert any(t.message == "All project translation files saved successfully." for t in ToastNotification._active_toasts)


def test_search_results_arrive_from_a_worker(interactive, qtbot, tmp_path, monkeypatch):
    mw = interactive()
    open_project(mw, project(tmp_path, {"a": ["The hero", "A villain", "The hero again"]}), monkeypatch, qtbot)

    mw.helper.open_advanced_search("hero", False, False, False, False)
    dialog = mw.active_search_dialog
    assert not getattr(dialog, "matches", None)  # nothing yet: the search has not run

    qtbot.waitUntil(lambda: hasattr(dialog, "search_worker"), timeout=5000)  # only the worker path sets it
    qtbot.waitUntil(lambda: len(getattr(dialog, "matches", None) or []) == 2, timeout=10000)


def test_spellcheck_window_analyses_on_a_worker(interactive, qtbot, tmp_path, monkeypatch):
    mw = interactive()
    open_project(mw, project(tmp_path, {"a": ["Добрий котт", "Ще один привітт", "Все гаразд"]}), monkeypatch, qtbot)
    _spellchecker_ready(mw, qtbot)

    mw.block_list_widget._open_spellcheck_for_block(0)
    dialog = mw.active_spellcheck_dialog
    assert dialog is not None

    qtbot.waitUntil(lambda: hasattr(dialog, "analysis_worker"), timeout=5000)  # only the worker path sets it
    qtbot.waitUntil(lambda: len(getattr(dialog, "items_to_review", None) or []) == 2, timeout=10000)
    assert sorted(item[2] for item in dialog.items_to_review) == ["котт", "привітт"]


def test_the_ai_done_popup_appears_when_an_ai_operation_finishes(interactive, qtbot):
    from components.ai_status_dialog import AIStatusDialog

    mw = interactive()
    dialog = AIStatusDialog(mw)
    dialog.start("AI Translation (Block 1)", is_chunked=False, model_name="m")
    dialog.finish(success=True)

    qtbot.waitUntil(lambda: any(box["title"] == "AI Translation (Block 1)" for box in interactive.boxes.seen), timeout=5000)


_RELOAD_LOOP = (
    "BUG: after an edit the editor re-analyses every 1.5 s for ever and the spell underline never stays: "
    "TextOperationHandler._run_post_edit_analysis calls highlighter.set_typing_mode(False, "
    "trigger_rehighlight=True); QSyntaxHighlighter.rehighlight() makes QPlainTextEdit emit textChanged, which "
    "text_edited takes for typing (typing mode on, async spellcheck ranges dropped, preview_update_timer "
    "restarted) -- handlers/text_operation/preview_mixin.py:339 and :160-197"
)


def _type_misspelled_word(interactive, qtbot, tmp_path, monkeypatch):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QTextCursor
    from PyQt6.QtTest import QTest

    mw = interactive()
    open_project(mw, project(tmp_path, {"a": ["Добрий день", "Ще рядок"]}), monkeypatch, qtbot)
    scm = mw.spellchecker_manager
    scm.set_enabled(True)
    qtbot.waitUntil(lambda: scm.hunspell is not None, timeout=30000)
    _select_string(mw, qtbot, 0, 0)
    editor = mw.edited_text_edit
    qtbot.waitUntil(lambda: editor.toPlainText() == "Добрий день", timeout=5000)
    editor.moveCursor(QTextCursor.MoveOperation.End)
    QTest.keyClick(editor, Qt.Key.Key_Space)
    # The word as an input method commits it: QTest.keyClicks cannot synthesise Cyrillic keys.
    editor.textCursor().insertText("котт")
    return mw, editor


def test_spellcheck_underline_appears_while_typing(interactive, qtbot, tmp_path, monkeypatch):
    from PyQt6.QtGui import QTextCharFormat

    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    mw, editor = _type_misspelled_word(interactive, qtbot, tmp_path, monkeypatch)
    QTest.keyClick(editor, Qt.Key.Key_Space)   # the word being typed is never flagged; the next one starts

    def underlined():
        block = editor.document().firstBlock()
        start = block.text().find("котт")
        return start >= 0 and any(
            r.format.underlineStyle() == QTextCharFormat.UnderlineStyle.SpellCheckUnderline
            and r.start <= start < r.start + r.length
            for r in block.layout().formats()
        )

    qtbot.waitUntil(underlined, timeout=6000)


def test_the_editor_goes_quiet_after_typing_stops(interactive, qtbot, tmp_path, monkeypatch):
    mw, editor = _type_misspelled_word(interactive, qtbot, tmp_path, monkeypatch)
    timer = mw.editor_operation_handler.preview_update_timer

    qtbot.waitUntil(lambda: not timer.isActive(), timeout=6000)  # one analysis 1.5 s after the last key
    qtbot.wait(2000)
    assert not timer.isActive()  # and nothing restarts it while nobody types


# --------------------------------------------------------------- the log (6.5)

def test_a_normal_session_logs_no_swallowed_exception(interactive, qtbot, tmp_path, monkeypatch):
    """Open, browse, edit, save, search, spellcheck, close: no ``module.function: ignored <exception>`` line."""
    import logging

    from utils.logging_utils import logger
    from utils.thread_utils import wait_for_threads_at_exit

    class Collect(logging.Handler):
        lines = []
        seen = []

        def emit(self, record):
            message = record.getMessage()
            self.seen.append(message)
            if ": ignored " in message:
                self.lines.append(message)

    handler = Collect(level=logging.DEBUG)
    logger.addHandler(handler)
    try:
        mw = interactive()
        mw.show()
        blocks = {"a": ["Добрий день", "Ще рядок", "Третій"], "b": ["Інший блок", "котт"]}
        open_project(mw, project(tmp_path, blocks), monkeypatch, qtbot)
        _spellchecker_ready(mw, qtbot)
        _select_string(mw, qtbot, 1, 0)
        _select_string(mw, qtbot, 0, 1)
        mw.data_processor.update_edited_data(0, 1, "Ще один рядок")
        mw.save_action.trigger()
        qtbot.waitUntil(lambda: mw.app_action_handler.save_worker is None, timeout=15000)
        mw.helper.open_advanced_search("рядок", False, False, False, False)
        qtbot.waitUntil(lambda: len(getattr(mw.active_search_dialog, "matches", None) or []) == 1, timeout=10000)
        mw.block_list_widget._open_spellcheck_for_block(1)
        qtbot.waitUntil(lambda: len(getattr(mw.active_spellcheck_dialog, "items_to_review", None) or []) == 1,
                        timeout=10000)
        mw.close()
        wait_for_threads_at_exit()
        qtbot.wait(200)
    finally:
        logger.removeHandler(handler)

    assert any("search finished" in line for line in handler.seen)  # the debug lines do reach this handler
    assert handler.lines == []
