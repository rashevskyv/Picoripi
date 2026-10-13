"""3DS electronic manual preview: the page key mapping, the overflow test, the no-folder message and a real render.

Only the last test reads the owner's repo_manual folder (PICORIPI_ROMHACKING); the others need no game files.
"""
import json

import pytest

import romhacking_root
from plugins.manual_3ds import page_render, preview_panel
from plugins.manual_3ds import rules as m3d

PAGE_KEY = "small/Page_003_small_0#1"


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
    assert page_render.group_key_of(PAGE_KEY) == "small/Page_003_small"
    assert page_render.group_key_of("large/Page_012_large_4#0") == "large/Page_012_large"
    assert page_render.group_key_of("index/Index#2") is None


def test_piece_over_its_limit_is_flagged():
    assert page_render.is_over(x_end=101.0, margin=0.0, cap=100.0)
    assert not page_render.is_over(x_end=100.0, margin=0.0, cap=100.0)
    assert not page_render.is_over(x_end=50.0, margin=20.0, cap=40.0)


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


@pytest.mark.skipif(romhacking_root.missing("work") is not None, reason=romhacking_root.missing("work") or "")
def test_real_page_renders_and_flags_an_overflowing_paragraph(qtbot, monkeypatch):
    monkeypatch.setattr(preview_panel, "load_folder", lambda: str(romhacking_root.root()))
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
    assert panel._result is not None, panel._message
    assert "small/Page_002_small_0#2" in panel._result.overflow_keys
    image = panel._result.image
    red = sum(
        1
        for x in range(0, image.width(), 2)
        for y in range(0, min(600, image.height()), 2)
        if image.pixelColor(x, y).red() > 150 and image.pixelColor(x, y).green() < 90
    )
    assert red > 0


def _real_keys():
    """The key list of home_menu_manual, from the plugin's geometry table (the keys, not the text)."""
    import pathlib

    geometry = json.loads((pathlib.Path(m3d.__file__).parent / "geometry.json").read_text(encoding="utf-8"))
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


_REPO_MANUAL = ("_shared", "3ds_sysfont_ua", "repo_manual")


@pytest.mark.skipif(romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") is not None,
                    reason=romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") or "")
def test_picture_panes_name_their_bclim_textures_and_the_textures_decode():
    from plugins.manual_3ds import pictures, repo_tools
    tools = repo_tools.load_tools(str(romhacking_root.path(*_REPO_MANUAL)))
    archive = tools.bcma.load(repo_tools.manual_path(tools, "home_menu_manual"))
    data = archive.read(f"{tools.manual.BASE_SLOT}_small")["Page_002_small_0.bclyt"]
    assert pictures.picture_textures(data)[:2] == ["cap_menu-screen_ue_6.bclim", "cap_menu-screen_shita_6.bclim"]
    image = pictures.TextureBank(archive, f"{tools.manual.BASE_SLOT}_texture").image("cap_menu-screen_ue_6.bclim")
    assert image is not None and (image.width(), image.height()) == (160, 96)
