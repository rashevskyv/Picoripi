"""WP5 review queue items checked in a real MainWindow:

- "AI translate actions are now in the Tools menu of every game (5.2)": Ctrl+Alt+T/L/B exist for every
  game, are labelled without "(UA)" and clash with no other shortcut of the window in Twilight Princess.
- "Opening a file needs a plugin that claims its extension (5.5)".
- "A plugin that fails while opening a file shows 'could not parse the file' (5.6)".
- "Switching plugins reloads all of the plugin's modules (5.6)": zelda_bmg -> zelda_mc -> zelda_bmg keeps
  the preview and the speaker data working.
"""
import json
import sys

import pytest
from PyQt6.QtGui import QAction, QShortcut
from PyQt6.QtWidgets import QMenu, QMessageBox

from . import _rq_wp5_helpers as h

AI_SHORTCUTS = {"Ctrl+Alt+T": "AI Translate Current String", "Ctrl+Alt+L": "AI Translate Selected Lines",
                "Ctrl+Alt+B": "AI Translate Entire Block"}


@pytest.fixture
def keep_plugin_modules():
    """A plugin switch drops the game's modules; give the other tests theirs back. Platform modules
    (plugins.base_game_rules, plugins.common...) are never dropped by a switch and stay as they are."""
    def is_game(name):
        return any(name == f"plugins.{game}" or name.startswith(f"plugins.{game}.") for game in h.PLUGINS)

    before = {name: module for name, module in sys.modules.items() if is_game(name)}
    yield
    for name in [name for name in sys.modules if is_game(name)]:
        del sys.modules[name]
    sys.modules.update(before)


@pytest.fixture
def message_boxes(monkeypatch):
    shown = []
    for kind in ("critical", "warning", "information"):
        monkeypatch.setattr(QMessageBox, kind,
                            lambda *args, _kind=kind, **kwargs: shown.append((_kind, args[1], args[2])))
    return shown


@pytest.fixture
def start_window(qtbot, tmp_path, monkeypatch, keep_plugin_modules, message_boxes):
    """MainWindow started with the given plugin active (a fresh settings file in tmp_path)."""
    import core.settings_manager as settings_manager
    import utils.constants as constants

    windows = []

    def start(plugin):
        settings_file = tmp_path / f"settings_{plugin}.json"
        settings_file.write_text(json.dumps({"active_game_plugin": plugin}), encoding="utf-8")
        monkeypatch.setattr(constants, "SETTINGS_FILE_PATH", str(settings_file))
        monkeypatch.setattr(settings_manager, "SETTINGS_FILE_PATH", str(settings_file))
        import main
        monkeypatch.setattr(main, "SETTINGS_FILE_PATH", str(settings_file), raising=False)
        window = main.MainWindow()
        window.is_testing = True
        qtbot.addWidget(window)
        windows.append(window)
        assert message_boxes == [], message_boxes          # the plugin loaded without an error dialog
        assert window.active_game_plugin == plugin
        return window

    yield start
    # Close while the user folders are still redirected, then make sure nothing saves later: a window
    # closed again after the test (cleanup, garbage collection) would write to the real ~/.picoripi.
    for window in windows:
        window.close()
        window.settings_manager.save_settings = lambda *args, **kwargs: None
        window.settings_manager.plugin_settings.save = lambda *args, **kwargs: None


def _shortcut_owners(window):
    """Every key sequence bound in the window: QAction shortcuts and QShortcut objects."""
    owners = {}
    for action in window.findChildren(QAction):
        for sequence in action.shortcuts():
            owners.setdefault(sequence.toString(), []).append(action.text())
    for shortcut in window.findChildren(QShortcut):
        if not shortcut.key().isEmpty():
            owners.setdefault(shortcut.key().toString(), []).append(f"QShortcut on {shortcut.parent()!r}")
    return owners


def test_ai_shortcuts_do_not_clash_in_twilight_princess(start_window):
    window = start_window("zelda_bmg")
    owners = _shortcut_owners(window)

    for sequence, text in AI_SHORTCUTS.items():
        assert owners.get(sequence) == [text], (sequence, owners.get(sequence))
    # No shortcut of the window is bound twice.
    assert {s: o for s, o in owners.items() if len(o) > 1} == {}
    # The Windows-level hotkeys are Alt+Shift+arrows, never Ctrl+Alt+letter.
    from utils import hotkey_manager
    assert set(hotkey_manager.ID_TO_VK.values()) <= {hotkey_manager.VK_UP, hotkey_manager.VK_DOWN,
                                                     hotkey_manager.VK_LEFT, hotkey_manager.VK_RIGHT}
    # The plugin itself binds none of these keys.
    plugin_keys = {a.get("shortcut") for a in window.current_game_rules.get_plugin_actions()}
    assert not plugin_keys & set(AI_SHORTCUTS)


def _write_inputs(tmp_path):
    bmg = tmp_path / "zel_rq.bmg"
    bmg.write_bytes(h.synthetic_bmg_bytes())
    data = tmp_path / "strings.json"
    data.write_text(json.dumps([["Hello there!", "Second line"]]), encoding="utf-8")
    text = tmp_path / "strings.txt"
    text.write_text("Hello there!\nSecond line\n", encoding="utf-8")
    return bmg, data, text


@pytest.mark.parametrize("plugin", h.PLUGINS)
def test_every_game_ai_menu_and_file_opening(start_window, tmp_path, message_boxes, plugin):
    """One window per game (a window costs ~3 s):
    - the Tools menu has the AI actions with their shortcuts, without "(UA)";
    - a .bmg opens only with Twilight Princess; any other game says so and keeps nothing loaded;
    - .json arrives parsed and .txt as text, as the old extension switch did."""
    window = start_window(plugin)

    menus = [m for m in window.menuBar().findChildren(QMenu) if m.title() == "&Tools"]
    assert len(menus) == 1
    actions = menus[0].actions()
    in_tools = {a.shortcut().toString(): a.text() for a in actions if not a.shortcut().isEmpty()}
    for sequence, text in AI_SHORTCUTS.items():
        assert in_tools.get(sequence) == text
    labels = [a.text() for a in actions]
    assert "AI Reset Translation Session" in labels
    assert not [label for label in labels if "(UA)" in label]

    bmg, data, text = _write_inputs(tmp_path)
    window.app_action_handler.load_all_data_for_path(str(bmg))
    if plugin == "zelda_bmg":
        assert message_boxes == []
        assert window.data_store.json_path == str(bmg) and len(window.data_store.data[0]) == 6
    else:
        assert window.data_store.json_path is None and window.data_store.data == []
        assert [kind for kind, _title, _text in message_boxes] == ["critical"]

    rules = window.current_game_rules
    for path, content in ((data, json.loads(data.read_text(encoding="utf-8"))),
                          (text, text.read_text(encoding="utf-8"))):
        expected, _names = rules.load_data_from_json_obj(content)
        message_boxes.clear()
        window.app_action_handler.load_all_data_for_path(str(path))
        if expected:
            assert window.data_store.data == expected, (plugin, path.name)
            assert window.data_store.json_path == str(path)
        else:   # the plugin cannot read this shape at all: reported, as before
            assert [kind for kind, _t, _m in message_boxes] == ["critical"]


def test_a_failing_plugin_hook_says_could_not_parse(start_window, tmp_path, message_boxes, monkeypatch):
    from core import plugin_call

    window = start_window("zelda_mc")
    _bmg, data, _text = _write_inputs(tmp_path)
    logged = []
    monkeypatch.setattr(plugin_call, "log_error", lambda message, *a, **k: logged.append(message))

    def broken(_content):
        raise ValueError("unexpected header")

    monkeypatch.setattr(window.current_game_rules, "load_data_from_json_obj", broken)
    window.app_action_handler.load_all_data_for_path(str(data))     # must not raise

    assert [kind for kind, _t, _m in message_boxes] == ["critical"]
    assert "could not parse the file" in message_boxes[0][2]
    assert any("load_data_from_json_obj() failed" in m and "unexpected header" in m for m in logged)
    assert window.data_store.json_path is None and window.data_store.data == []


# --- plugin switch -----------------------------------------------------------------------------------------

def _switch(window, plugin):
    """What opening a project of another game does (ProjectActionHandler.open_project_action)."""
    window.active_game_plugin = plugin
    window.load_game_plugin()


def _tp_snapshot(window, count):
    rules = window.current_game_rules
    window.data_store.current_block_idx = 0
    out = []
    for idx in range(count):
        style = rules.get_preview_window_style(block_idx=0, string_idx=idx)
        out.append({
            "attrs": rules.get_message_attributes(0, idx),
            "kind": style.get("kind_name"), "lines": style.get("lines_per_page"),
            "layout": rules.get_string_layout(0, idx),
            "speaker": rules.get_speaker_for_string(0, idx),
            "flow": rules.get_ai_flow_context_for_string(0, idx),
            "scene": rules.get_scene_context_for_string(0, idx),
        })
    return out


def _window_preview_pixels(window, count):
    """The window's own game-like preview, painted for each message (a synthetic font, no dump)."""
    from plugins.zelda_bmg import window_frame_loader as loader

    loader._LAYOUT_ROOT = None   # under pytest the dump is found only when a test names it (app_mode.headless)
    loader._CACHE.clear()
    widget = window.bfn_preview_widget
    window.all_bfn_fonts = {"rq.bfn": h.synthetic_bfn()}
    window.default_font_file = None
    widget.resize(*h.PREVIEW_SIZE)
    widget.show()
    digests = []
    for idx in range(count):
        window.data_store.current_string_idx = idx
        widget.update_preview_text(window.data_store.data[0][idx])
        digests.append(h.pixel_digest(h._paint(widget)))
    return digests


def _open_bmg(window, path, message_boxes):
    window.app_action_handler.load_all_data_for_path(str(path))
    assert message_boxes == [] and window.data_store.data


def test_switching_away_and_back_keeps_the_preview_data(start_window, tmp_path, message_boxes):
    window = start_window("zelda_bmg")
    path = tmp_path / "zel_preview.bmg"
    path.write_bytes(h.preview_bmg().save())
    _open_bmg(window, path, message_boxes)
    before = _tp_snapshot(window, len(h.PREVIEW_MESSAGES))
    pixels_before = _window_preview_pixels(window, len(h.PREVIEW_MESSAGES))
    first_rules = window.current_game_rules

    _switch(window, "zelda_mc")
    assert window.current_game_rules.__class__.__module__ == "plugins.zelda_mc.rules"
    _switch(window, "zelda_bmg")
    assert window.current_game_rules is not first_rules
    assert type(window.current_game_rules) is not type(first_rules)       # fresh modules
    _open_bmg(window, path, message_boxes)

    after = _tp_snapshot(window, len(h.PREVIEW_MESSAGES))
    assert after == before
    assert _window_preview_pixels(window, len(h.PREVIEW_MESSAGES)) == pixels_before
    assert len(set(pixels_before)) == len(pixels_before)          # every window kind paints differently
    assert [s["kind"] for s in after][:3] == ["Dialogue", "Wooden sign", "Stone sign"]


@pytest.mark.skipif(not (h.TP_DUMP_MSG / h.REAL_ARC).exists(), reason="retail Twilight Princess dump not on this machine")
def test_switching_away_and_back_keeps_the_speaker_data(start_window, tmp_path, message_boxes):
    from core.containers import ContainerManager

    path = tmp_path / h.REAL_MEMBER
    path.write_bytes(ContainerManager.open((h.TP_DUMP_MSG / h.REAL_ARC).read_bytes()).read_file(h.REAL_MEMBER))
    window = start_window("zelda_bmg")
    _open_bmg(window, path, message_boxes)
    count = len(window.data_store.data[0])
    before = _tp_snapshot(window, count)
    assert sum(1 for s in before if s["speaker"]) > count // 2
    assert sum(1 for s in before if s["flow"]) > 0

    _switch(window, "pokemon_fr")
    _switch(window, "zelda_bmg")
    _open_bmg(window, path, message_boxes)

    assert _tp_snapshot(window, count) == before
