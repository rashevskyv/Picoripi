"""3DS electronic manual preview: the page key mapping, the overflow test, the no-folder message and a real render.

Only the last test reads the owner's repo_manual folder (PICORIPI_ROMHACKING); the others need no game files.
"""
import json

import pytest

import romhacking_root
from plugins.manual_3ds import preview_panel
from plugins.manual_3ds import rules as m3d

PAGE_KEY = "small/Page_003_small_0#1"
_REPO_MANUAL = ("_shared", "3ds_sysfont_ua", "repo_manual")


class _Store:
    """The part of the main window the panel reads: the selected string and the text of each string."""

    def __init__(self, texts):
        self.current_string_idx = 1
        self.current_block_idx = 0
        self.physical_block_idx = 0
        self.texts = texts
        self.data_store = self
        self.data_processor = self

    def get_current_string_text(self, block, index):
        return self.texts[index], "test"


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
    indices = rules.strings_of_group("small/Page_002_small")
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
    assert rules.index_string_of_page(2) == 2
    assert rules.index_string_of_page(0) == 0
    assert rules.index_string_of_page(9) is None
