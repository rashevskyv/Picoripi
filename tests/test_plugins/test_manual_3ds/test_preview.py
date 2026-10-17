"""3DS electronic manual preview: the page key mapping, the overflow test, the no-folder message and a real render.

Only the last test reads the owner's repo_manual folder (PICORIPI_ROMHACKING); the others need no game files.
"""
import json
import threading

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QPainter

import romhacking_root
from core import formats
from plugins.manual_3ds import console_render as cr
from plugins.manual_3ds import preview_panel
from plugins.manual_3ds import rules as m3d

PAGE_KEY = "small/Page_003_small_0#1"
_REPO_MANUAL = ("_shared", "3ds_sysfont_ua", "repo_manual")


class _Store:
    """The part of the main window the panel reads: the selected string and the text of each string.

    ``texts`` are the strings of block 0; ``blocks`` ({block: strings}) replaces them for a project of many files."""

    def __init__(self, texts, blocks=None, block_names=None):
        self.current_string_idx = 1
        self.current_block_idx = 0
        self.physical_block_idx = 0
        self.blocks = blocks or {0: texts}
        self.block_names = block_names or {}
        self.data_store = self
        self.data_processor = self

    def get_current_string_text(self, block, index):
        return self.blocks[block][index], "test"


def _document(keys):
    entries = {key: {"lines": 1, "width": 300.0, "en": "Text", "ru": "Text", "ua": "Text"} for key in keys}
    return json.dumps(entries, ensure_ascii=False)


def test_page_name_and_group_keys():
    assert preview_panel.page_name_of(PAGE_KEY) == "Page_003"
    assert preview_panel.page_name_of("index/Index#2") is None
    assert m3d.group_key_of(PAGE_KEY) == "small/Page_003_small"
    assert m3d.group_key_of("large/Page_012_large_4#0") == "large/Page_012_large"
    assert m3d.group_key_of("index/Index#2") is None


def test_panel_without_folder_shows_the_message(qtbot, monkeypatch):
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document([PAGE_KEY]))
    store = _Store(["Text"])
    store.current_string_idx = 0
    panel = preview_panel.ManualPreviewPanel(store, rules)
    qtbot.addWidget(panel)
    panel._start_render()
    qtbot.waitUntil(lambda: bool(panel._message), timeout=10000)
    panel.shutdown()
    assert panel._result is None
    assert panel._message == "Set the repo_manual folder to draw the page."


def test_panel_reports_a_string_outside_a_page(qtbot, monkeypatch):
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document(["index/Index#0", PAGE_KEY]))
    store = _Store(["Index entry", "Text"])
    store.current_string_idx = 0
    panel = preview_panel.ManualPreviewPanel(store, rules)
    qtbot.addWidget(panel)
    panel._start_render()
    assert panel._workers == []
    assert panel._message == "The index is not drawn here. Select a string of a page."


KEY_A = "large/Page_003_large_0#0"
KEY_B = "large/Page_003_large_0#1"
KEY_NO_TEXT = "large/Page_003_large_0#2"


def _run(pane, top):
    """One drawn line 50 px wide at page x 10, 20 px high, its top at page y ``top`` (down is negative)."""
    return cr.TextRun(pane=pane, text="Line", x=10.0, top=top, width=50.0, wrapped=False, ink_right=60.0, height=20.0,
                      order=0, ink_left=10.0)


def _page(runs, owners):
    """A PagePreview of a 2400-row column with blank images, the given lines and the pane owners."""
    column = QImage(cr.COLUMN_WIDTH, 2400, QImage.Format.Format_RGBA8888)
    overlay = QImage(400, 480, QImage.Format.Format_RGBA8888)
    return preview_panel.PagePreview(column, overlay, 2400, 3, "Title", runs=runs, owners=owners)


def _large_panel(qtbot, monkeypatch, texts=("Text", "Text")):
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    panel = preview_panel.ManualPreviewPanel(_Store(list(texts)), m3d.GameRules())
    qtbot.addWidget(panel)
    panel._large = True
    return panel


def test_the_selected_paragraph_is_outlined_and_the_page_scrolls_to_it(qtbot, monkeypatch):
    panel = _large_panel(qtbot, monkeypatch)
    result = _page([_run("pane_a", -300.0), _run("pane_b", -900.0)], {"pane_a": KEY_A, "pane_b": KEY_B})
    panel._current_key = KEY_A
    panel._show_result(result)
    assert panel._highlight == QRectF(10.0, 300.0, 50.0, 20.0)
    assert panel._scroll == 0.0, "a paragraph already in view does not move the page"
    panel._current_key = KEY_B
    panel._show_result(result)
    assert panel._highlight == QRectF(10.0, 900.0, 50.0, 20.0)
    assert panel._scroll == 840.0, "the selected paragraph's top sits 60 rows below the top of the page"
    panel._current_key = KEY_A
    panel._show_result(result)
    assert panel._scroll == 240.0, "a paragraph above the view scrolls back to it"


def test_a_visible_paragraph_does_not_move_the_page(qtbot, monkeypatch):
    panel = _large_panel(qtbot, monkeypatch)
    panel._current_key = KEY_A
    panel._scroll = 100.0
    panel._show_result(_page([_run("pane_a", -300.0)], {"pane_a": KEY_A}))
    assert panel._scroll == 100.0


def test_the_highlight_is_painted_over_the_column(qtbot, monkeypatch):
    panel = _large_panel(qtbot, monkeypatch)
    panel._current_key = KEY_A
    panel._show_result(_page([_run("pane_a", -300.0)], {"pane_a": KEY_A}))
    image = QImage(400, 480, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    try:
        panel.paint_screens(painter)
    finally:
        painter.end()
    assert image.pixelColor(55, 345) != QColor(255, 255, 255), "inside the selected lines"
    assert image.pixelColor(300, 100) == QColor(255, 255, 255), "outside them the page is as it was"


def test_a_string_that_draws_no_text_says_so_and_a_string_of_the_other_size_is_not_judged(qtbot, monkeypatch):
    panel = _large_panel(qtbot, monkeypatch)
    result = _page([_run("pane_a", -300.0)], {"pane_a": KEY_A})
    panel._current_key = KEY_NO_TEXT
    panel._show_result(result)
    assert panel._highlight is None
    assert "This string draws no text on the page." in panel._status.text()
    panel._large = False   # the large string is not drawn in small text: nothing to outline, nothing to say
    panel._show_result(result)
    assert panel._highlight is None
    assert "This string draws no text on the page." not in panel._status.text()


def test_selecting_another_string_of_the_page_moves_the_highlight_without_a_render(qtbot, monkeypatch):
    """The second string is on the same page with the same texts: the cache answers, no worker starts."""
    started = []

    class _Signal:
        def connect(self, slot):
            pass

    class _Worker:
        def __init__(self, generation, request, parent):
            self.request = request
            self.rendered = _Signal()
            started.append(self)

        def start(self):
            pass

        def isRunning(self):  # noqa: N802 - Qt name
            return False

        def cancel(self):
            pass

    monkeypatch.setattr(preview_panel, "PageRenderWorker", _Worker)
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document([KEY_A, KEY_B]))
    store = _Store(["Text", "Text"])
    panel = preview_panel.ManualPreviewPanel(store, rules)
    qtbot.addWidget(panel)
    store.current_string_idx = 0
    panel._start_render()
    assert len(started) == 1
    page = _page([_run("pane_a", -300.0), _run("pane_b", -500.0)], {"pane_a": KEY_A, "pane_b": KEY_B})
    panel._on_rendered(panel._generation, started[0].request.key, page)
    assert panel._highlight == QRectF(10.0, 300.0, 50.0, 20.0)
    store.current_string_idx = 1
    panel._start_render()
    assert len(started) == 1, "the same page is in the cache: no new render"
    assert panel._current_key == KEY_B
    assert panel._highlight == QRectF(10.0, 500.0, 50.0, 20.0)


def _two_manuals_loaded_as_a_project():
    """Two manual files whose string 1 differ in kind: block 0 has a page paragraph there, block 1 an index entry.
    Loaded as the project loader does: the sources, then the translations between an export and a restore."""
    first, second = _document(["index/Index#0", PAGE_KEY]), _document([PAGE_KEY, "index/Index#0"])
    rules = m3d.GameRules()
    rules.reset_runtime_state()
    for text in (first, second):
        rules.load_data_from_json_obj(text)
    state = rules.export_runtime_state()
    for text in (first, second):
        rules.load_data_from_json_obj(text)
    rules.restore_runtime_state(state)
    return rules, state


def test_each_block_of_a_project_keeps_its_own_manual():
    """Regression: the plugin kept only the file parsed last, so a page paragraph of the first manual was looked up
    in the last one (an index entry there) and the preview said "The index is not drawn here"."""
    rules, state = _two_manuals_loaded_as_a_project()
    assert [rules.string_key(0, 1), rules.string_key(1, 1)] == [PAGE_KEY, "index/Index#0"]
    assert rules.strings_of_group(0, "small/Page_003_small") == {PAGE_KEY: 1}
    assert rules.strings_of_group(1, "small/Page_003_small") == {PAGE_KEY: 0}
    assert rules.string_key(2, 0) is None
    # A restored session parses no file: the manuals come back from the exported state alone.
    restored = m3d.GameRules()
    restored.restore_runtime_state(json.loads(json.dumps(state)))
    assert [restored.string_key(0, 1), restored.string_key(1, 1)] == [PAGE_KEY, "index/Index#0"]
    assert "ua" not in state["manuals"][0][PAGE_KEY], "the translation lives in the editor, not in the session state"


def test_a_session_without_plugin_state_reads_the_manuals_on_a_worker_and_keeps_the_edits(qtbot, tmp_path):
    """A session written before the plugin kept its manuals restores none: the host reads the project files once
    for the plugin state only, then rescans the issues and redraws the preview. The restored edits stay."""
    from types import MethodType, SimpleNamespace

    from core.data_processor.session_manager import SessionManager
    from handlers.project_action.session_mixin import SessionMixin

    files = {"one": ["index/Index#0", PAGE_KEY], "two": [PAGE_KEY, "index/Index#0"]}
    for name, keys in files.items():
        (tmp_path / f"{name}.json").write_text(_document(keys), encoding="utf-8")
    blocks = [SimpleNamespace(name=name, source_file=f"{name}.json", translation_file=f"{name}.json",
                              internal_key=None, metadata={}) for name in files]
    project_manager = SimpleNamespace(project=SimpleNamespace(blocks=blocks), clear_archive_cache=lambda: None,
                                      get_absolute_path=lambda relative, is_translation=False: str(tmp_path / relative))
    parsed = []

    class CountingRules(m3d.GameRules):
        def load_data_from_json_obj(self, json_obj):
            parsed.append(json_obj)
            return super().load_data_from_json_obj(json_obj)

    rules = CountingRules()
    scans, redraws = [], []
    edits = {(0, 1): "an unsaved edit"}
    window = SimpleNamespace(
        current_game_rules=rules, project_manager=project_manager, data_store=SimpleNamespace(edited_data=edits),
        issue_scan_handler=SimpleNamespace(_perform_initial_silent_scan_all_issues=lambda force=False: scans.append(force)),
        custom_preview_widget=SimpleNamespace(refresh=lambda: redraws.append(True)))
    sessions = SessionManager(SimpleNamespace(mw=window))
    sessions._restore_runtime_session_state({"data": []})  # a session of the old plugin: no plugin state
    owner = SimpleNamespace(mw=window, data_processor=SimpleNamespace(
        session_had_plugin_state=lambda: sessions.restored_plugin_state), _active_load_worker=None)
    owner._load_reference = MethodType(SessionMixin._load_reference, owner)

    SessionMixin._read_missing_plugin_state(owner)

    assert [rules.string_key(0, 1), rules.string_key(1, 1)] == [PAGE_KEY, "index/Index#0"]
    assert len(parsed) == 2, "the state-only pass reads the two source files, not the translation files"
    assert (scans, redraws) == ([True], [True])
    assert window.data_store.edited_data == {(0, 1): "an unsaved edit"}
    # A session written by this plugin carries the state, so the files are not read again.
    sessions._restore_runtime_session_state({"plugin_runtime_state": rules.export_runtime_state()})
    SessionMixin._read_missing_plugin_state(owner)
    assert scans == [True]


def test_a_block_whose_manual_is_not_read_yet_says_so(qtbot, monkeypatch):
    rules = m3d.GameRules()
    panel = preview_panel.ManualPreviewPanel(_Store(["Text", "Text"]), rules)
    qtbot.addWidget(panel)
    panel._start_render()
    assert panel._workers == []
    assert panel._message == "This manual is not read yet. The page is drawn when it is."


def test_a_worker_that_outlives_the_shutdown_is_not_destroyed_with_the_panel(qtbot, monkeypatch):
    """Regression: a worker still loading the manual's files was a child of the panel, and deleting the panel
    destroyed the running thread (Qt aborts the process). It is parked now and ends by itself."""
    release = threading.Event()

    def slow_draw(request, should_stop):
        release.wait(10)
        raise preview_panel.repo_tools.ToolsError("stopped")

    monkeypatch.setattr(preview_panel, "draw_request", slow_draw)
    monkeypatch.setattr(preview_panel, "WORKER_STOP_MS", 20)
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document(["index/Index#0", PAGE_KEY]))
    panel = preview_panel.ManualPreviewPanel(_Store(["Index entry", "Text"]), rules)
    panel._start_render()
    worker = panel._workers[0]
    panel.shutdown()
    assert worker.isRunning() and worker.parent() is None
    panel.deleteLater()
    qtbot.waitUntil(lambda: sip.isdeleted(panel), timeout=5000)
    release.set()
    assert worker.wait(5000)


def test_a_page_paragraph_of_the_first_manual_goes_to_the_drawing(qtbot, monkeypatch):
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    rules, _ = _two_manuals_loaded_as_a_project()
    store = _Store([], blocks={0: ["Index entry", "Text"], 1: ["Text", "Index entry"]})
    panel = preview_panel.ManualPreviewPanel(store, rules)
    qtbot.addWidget(panel)
    panel._start_render()
    qtbot.waitUntil(lambda: bool(panel._message), timeout=10000)
    panel.shutdown()
    assert panel._message == "Set the repo_manual folder to draw the page."


@pytest.mark.skipif(romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") is not None,
                    reason=romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") or "")
def test_real_page_renders_and_flags_an_overflowing_paragraph(qtbot, monkeypatch):
    """A 200-W paragraph: the owner's pane model refuses it and the column model widens the pane for it, so the
    render shows the line running past the card's edge (an `over_edge` defect on that key); three-word paragraphs on
    one-line panes are refused outright and keep their stored text (failed keys)."""
    monkeypatch.setattr(preview_panel, "load_folder", lambda: str(romhacking_root.path(*_REPO_MANUAL)))
    keys = _real_keys()
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document(keys))
    indices = rules.strings_of_group(0, "small/Page_002_small")
    texts = ["Word word word"] * len(keys)
    flagged = indices["small/Page_002_small_0#2"]
    texts[flagged] = "W" * 200
    store = _Store(texts)
    store.current_string_idx = flagged
    panel = preview_panel.ManualPreviewPanel(store, rules)
    qtbot.addWidget(panel)
    panel.toggle_size()
    panel._start_render()
    qtbot.waitUntil(lambda: panel._result is not None or bool(panel._message), timeout=60000)
    panel.shutdown()
    result = panel._result
    assert result is not None, panel._message
    assert result.column.width() == 320 + preview_panel.cr.OVERRUN and result.overlay.size().width() == 400
    assert result.number == 3
    assert "over_edge" in result.defect_keys.get("small/Page_002_small_0#2", []) or "small/Page_002_small_0#2" in result.failed_keys
    assert result.failed_keys and result.runs, "the page drew no text"


@pytest.mark.skipif(romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") is not None,
                    reason=romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") or "")
def test_a_page_paragraph_of_activity_log_in_the_whole_project_draws_its_ukrainian_text(qtbot, monkeypatch):
    """The owner's case: every manual of src/manuals loaded as one project; activity_log, string 22 (the editor's
    line 23, "large/Page_001_large_0#10") is drawn with its translation."""
    folder = romhacking_root.path(*_REPO_MANUAL)
    monkeypatch.setattr(preview_panel, "load_folder", lambda: str(folder))
    rules = m3d.GameRules()
    blocks, names = {}, {}
    with formats.translation_parse(rules):  # the store's text is the translation the editor shows
        for block, path in enumerate(sorted((folder / "src" / "manuals").glob("*.json"))):
            blocks[block] = rules.load_data_from_json_obj(path.read_text(encoding="utf-8"))[0][0]
            names[str(block)] = path.stem
    block = next(int(index) for index, name in names.items() if name == "activity_log")
    store = _Store([], blocks=blocks, block_names=names)
    store.current_block_idx = store.physical_block_idx = block
    store.current_string_idx = 22
    assert rules.string_key(block, 22) == "large/Page_001_large_0#10"
    panel = preview_panel.ManualPreviewPanel(store, rules)
    qtbot.addWidget(panel)
    panel._start_render()
    qtbot.waitUntil(lambda: panel._result is not None or bool(panel._message), timeout=60000)
    panel.shutdown()
    assert panel._result is not None, panel._message
    tools = preview_panel.repo_tools.load_tools(str(folder))
    word = tools.manual.apply_homoglyphs("кроків", tools.manual.load_homoglyphs())  # drawn as the build writes it
    assert word in " ".join(run.text for run in panel._result.runs)


@pytest.mark.skipif(romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") is not None,
                    reason=romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") or "")
def test_the_outline_of_a_real_paragraph_lies_on_the_drawn_column(qtbot, monkeypatch):
    """The owner's activity_log paragraph 22 (its own page, large text): its outline is inside the column the render
    drew, so the page x and the content y of the outline are the ones the column uses."""
    folder = romhacking_root.path(*_REPO_MANUAL)
    monkeypatch.setattr(preview_panel, "load_folder", lambda: str(folder))
    rules = m3d.GameRules()
    blocks, names = {}, {}
    with formats.translation_parse(rules):
        for block, path in enumerate(sorted((folder / "src" / "manuals").glob("*.json"))):
            blocks[block] = rules.load_data_from_json_obj(path.read_text(encoding="utf-8"))[0][0]
            names[str(block)] = path.stem
    block = next(int(index) for index, name in names.items() if name == "activity_log")
    store = _Store([], blocks=blocks, block_names=names)
    store.current_block_idx = store.physical_block_idx = block
    store.current_string_idx = 22
    panel = preview_panel.ManualPreviewPanel(store, rules)
    qtbot.addWidget(panel)
    panel._start_render()
    qtbot.waitUntil(lambda: panel._result is not None or bool(panel._message), timeout=60000)
    panel.shutdown()
    result = panel._result
    assert result is not None, panel._message
    rect = panel._highlight
    assert rect is not None, "the paragraph's lines are on the page"
    assert 0 <= rect.left() and rect.right() <= cr.COLUMN_WIDTH + cr.OVERRUN
    assert -cr.TOP_MARGIN_ROWS <= rect.top() and rect.bottom() <= result.column_height - cr.TOP_MARGIN_ROWS


def _real_keys():
    """The key list of home_menu_manual, from the plugin's geometry table (the keys, not the text)."""
    import pathlib

    geometry = json.loads((pathlib.Path(m3d.__file__).parent / "geometry.json").read_text(encoding="utf-8"))["manuals"]
    entry = next(value for value in geometry.values() if value.get("name") == "home_menu_manual")
    return list(entry["entries"].keys())


def test_host_docks_the_panel_in_place_of_the_bfn_preview(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    from ui.main_window.main_window_plugin_handler import MainWindowPluginHandler

    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document([PAGE_KEY]))
    host = _Store(["Text"])
    column = QWidget()
    qtbot.addWidget(column)
    layout = QVBoxLayout(column)
    bfn = QWidget(column)
    bar = QWidget(column)
    layout.addWidget(bfn, 1)
    layout.addWidget(bar)
    host.bfn_preview_column = column
    host.bfn_preview_widget = bfn
    host.bfn_preview_window_bar = bar
    host.current_game_rules = rules
    handler = MainWindowPluginHandler(host)

    handler.attach_custom_preview()
    panel = host.custom_preview_widget
    assert isinstance(panel, preview_panel.ManualPreviewPanel)
    assert layout.indexOf(panel) == 0
    assert bfn.isHidden() and bar.isHidden()

    host.current_game_rules = None
    handler.attach_custom_preview()
    assert host.custom_preview_widget is None
    assert not bfn.isHidden() and not bar.isHidden()


def test_a_second_attach_replaces_the_panel_and_shuts_the_old_one_down(qtbot):
    """setup_plugin_ui docks the panel, a later load_game_plugin docks it again: one panel, the old one shut down."""
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    from ui.main_window.main_window_plugin_handler import MainWindowPluginHandler

    shut = []

    class Panel(QWidget):
        def refresh(self):
            pass

        def shutdown(self):
            shut.append(self)

    class PanelRules(m3d.GameRules):
        def get_custom_preview_widget(self, main_window):
            return Panel()

    host = _Store(["Text"])
    column = QWidget()
    qtbot.addWidget(column)
    layout = QVBoxLayout(column)
    bfn = QWidget(column)
    layout.addWidget(bfn, 1)
    host.bfn_preview_column, host.bfn_preview_widget, host.current_game_rules = column, bfn, PanelRules()
    handler = MainWindowPluginHandler(host)

    handler.attach_custom_preview()
    first = host.custom_preview_widget
    handler.attach_custom_preview()
    second = host.custom_preview_widget
    assert second is not first and shut == [first]
    assert layout.count() == 2 and layout.indexOf(second) == 0 and layout.indexOf(first) == -1
    assert bfn.isHidden()


def test_a_preview_widget_that_fails_is_logged_and_the_bfn_preview_stays(qtbot, monkeypatch):
    """pythonw has no stderr: an error of the plugin's widget must reach the app log, not end the plugin load."""
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    from ui.main_window import main_window_plugin_handler
    from ui.main_window.main_window_plugin_handler import MainWindowPluginHandler

    logged = []
    monkeypatch.setattr(main_window_plugin_handler, "log_error",
                        lambda message, exc_info=False, **kwargs: logged.append((message, exc_info)))

    class BrokenRules(m3d.GameRules):
        def get_custom_preview_widget(self, main_window):
            raise RuntimeError("no panel today")

    host = _Store(["Text"])
    column = QWidget()
    qtbot.addWidget(column)
    bfn = QWidget(column)
    QVBoxLayout(column).addWidget(bfn)
    host.bfn_preview_column, host.bfn_preview_widget, host.current_game_rules = column, bfn, BrokenRules()

    MainWindowPluginHandler(host).attach_custom_preview()

    assert getattr(host, "custom_preview_widget", None) is None and not bfn.isHidden()
    assert logged == [("The preview widget of BrokenRules failed: no panel today", True)]


def test_the_index_entry_of_a_page_is_its_title_string():
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document(["index/Index#0", PAGE_KEY, "index/Index#2"]))
    assert rules.index_string_of_page(0, 2) == 2
    assert rules.index_string_of_page(0, 0) == 0
    assert rules.index_string_of_page(0, 9) is None


def test_the_view_follows_the_size_of_the_selected_string(qtbot, monkeypatch):
    """A small-text string selected while large text is shown switches the view to small text, and back."""
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    small_key = "small/Page_003_small_0#0"
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document([KEY_A, small_key]))
    store = _Store(["Text", "Text"])
    panel = preview_panel.ManualPreviewPanel(store, rules)
    qtbot.addWidget(panel)
    panel._large = True
    store.current_string_idx = 1
    panel._start_render()
    assert panel._large is False
    assert panel._current_key == small_key
    store.current_string_idx = 0
    panel._start_render()
    assert panel._large is True
    panel.shutdown()


def test_the_size_button_keeps_the_other_size_while_the_selection_stays(qtbot, monkeypatch):
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document([KEY_A]))
    store = _Store(["Text"])
    store.current_string_idx = 0
    panel = preview_panel.ManualPreviewPanel(store, rules)
    qtbot.addWidget(panel)
    panel._start_render()
    assert panel._large is True
    panel._large = False   # what toggle_size does before its refresh
    panel._start_render()  # a text edit or the toggle's own refresh: same string
    assert panel._large is False
    panel.shutdown()
