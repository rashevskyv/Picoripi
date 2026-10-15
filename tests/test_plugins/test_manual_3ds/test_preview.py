"""3DS electronic manual preview: the page key mapping, the overflow test, the no-folder message and a real render.

Only the last test reads the owner's repo_manual folder (PICORIPI_ROMHACKING); the others need no game files.
"""
import json
import threading

import pytest
from PyQt6 import sip

import romhacking_root
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
    from types import SimpleNamespace

    from core.data_processor.session_manager import SessionManager
    from handlers.project_action.session_mixin import SessionMixin

    files = {"one": ["index/Index#0", PAGE_KEY], "two": [PAGE_KEY, "index/Index#0"]}
    for name, keys in files.items():
        (tmp_path / f"{name}.json").write_text(_document(keys), encoding="utf-8")
    blocks = [SimpleNamespace(name=name, source_file=f"{name}.json", translation_file=f"{name}.json",
                              internal_key=None, metadata={}) for name in files]
    project_manager = SimpleNamespace(project=SimpleNamespace(blocks=blocks), clear_archive_cache=lambda: None,
                                      get_absolute_path=lambda relative, is_translation=False: str(tmp_path / relative))
    rules = m3d.GameRules()
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

    SessionMixin._read_missing_plugin_state(owner)

    assert [rules.string_key(0, 1), rules.string_key(1, 1)] == [PAGE_KEY, "index/Index#0"]
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


def test_the_index_entry_of_a_page_is_its_title_string():
    rules = m3d.GameRules()
    rules.load_data_from_json_obj(_document(["index/Index#0", PAGE_KEY, "index/Index#2"]))
    assert rules.index_string_of_page(0, 2) == 2
    assert rules.index_string_of_page(0, 0) == 0
    assert rules.index_string_of_page(0, 9) is None
