"""Coverage for custom script settings and their toolbar actions."""
from unittest.mock import MagicMock
from types import SimpleNamespace

from PyQt6.QtGui import QAction
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QToolBar, QWidget

from ui.builders.toolbar_builder import ToolBarBuilder
from ui.main_window.actions.settings_mixin import MainWindowSettingsActionsMixin
from ui.settings.script_launch_worker import ScriptLaunchController, ScriptLaunchWorker
from ui.settings.script_tools_mixin import SettingsScriptToolsMixin, ToolBadgeDialog, tool_badge_icon
from utils.thread_utils import safe_shutdown_thread


class ScriptToolsDialog(QDialog, SettingsScriptToolsMixin):
    def __init__(self, tools):
        super().__init__()
        self.tools_tab = QWidget(self)
        self.setup_tools_tab()
        self.load_external_tools(tools)


def test_tool_rows_edit_badge_and_cancel_keeps_main_window_values(qapp, qtbot):
    original = [{"name": "Old", "path": "old.py", "icon": "B"}]
    dialog = ScriptToolsDialog(original)
    qtbot.addWidget(dialog)
    assert len(dialog.tool_rows) == 1
    dialog.add_tool_button.click()
    assert len(dialog.tool_rows) == 2
    row, icon_button, name_edit, path_edit, badge = dialog.tool_rows[0]
    name_edit.setText("New")
    path_edit.setText("new.py")

    def edit_badge_dialog():
        badge_dialog = next(widget for widget in QApplication.topLevelWidgets() if widget.windowTitle() == "Edit Tool Icon")
        badge_dialog.badge_edit.setText("🧪")
        badge_dialog.accept()

    QTimer.singleShot(0, edit_badge_dialog)
    dialog._edit_tool_badge(icon_button, badge)
    assert badge[0] == "🧪"
    QTimer.singleShot(0, lambda: next(
        widget for widget in QApplication.topLevelWidgets()
        if widget.windowTitle() == "Edit Tool Icon"
    ).reject())
    dialog._edit_tool_badge(icon_button, badge)
    assert badge[0] == "🧪"
    assert dialog.get_external_tools() == [{"name": "New", "path": "new.py", "icon": "🧪"}]
    dialog._remove_tool_row(dialog.tool_rows[1][0])
    assert len(dialog.tool_rows) == 1
    saved = dialog.get_external_tools()
    reopened = ScriptToolsDialog(saved)
    qtbot.addWidget(reopened)
    assert reopened.get_external_tools() == saved
    dialog.reject()
    assert original == [{"name": "Old", "path": "old.py", "icon": "B"}]


def test_tool_badge_limit_preserves_complete_unicode_characters(qapp, qtbot):
    family = "👨‍👩‍👧‍👦"
    dialog = ToolBadgeDialog(family)
    qtbot.addWidget(dialog)
    assert dialog.badge_edit.text() == family
    assert dialog.badge_edit.validator().validate(family, len(family))[0].name == "Acceptable"

    boundary = "1234567🔧"
    boundary_dialog = ToolBadgeDialog(boundary)
    qtbot.addWidget(boundary_dialog)
    assert boundary_dialog.badge_edit.text() == boundary
    assert boundary_dialog.badge_edit.validator().validate(boundary, len(boundary))[0].name == "Acceptable"
    over_limit = "12345678🔧"
    boundary_dialog.badge_edit.setText(over_limit)
    assert boundary_dialog.badge_edit.text() == over_limit
    assert boundary_dialog.badge_edit.validator().validate(over_limit, len(over_limit))[0].name == "Invalid"
    boundary_dialog.accept()
    assert boundary_dialog.result() != QDialog.DialogCode.Accepted

    editor = ScriptToolsDialog([{"name": "Wide", "path": "wide.py", "icon": "B"}])
    editor.tool_rows[0][4][0] = over_limit
    assert editor.get_external_tools()[0]["icon"] == "B"


def test_tool_name_preserves_emoji_at_storage_length_boundary(qapp, qtbot):
    name = "B" * 79 + "🔧"
    dialog = ScriptToolsDialog([{"name": name, "path": "build.py", "icon": "B"}])
    qtbot.addWidget(dialog)

    saved_name = dialog.get_external_tools()[0]["name"]

    assert saved_name == name
    assert saved_name.encode("utf-8").decode("utf-8") == name
    name_edit = dialog.tool_rows[0][2]
    assert name_edit.hasAcceptableInput()
    name_edit.setText("B" * 80 + "🔧")
    assert not name_edit.hasAcceptableInput()


def test_wide_badge_is_scaled_without_clipping(qapp):
    image = tool_badge_icon("WWWWWWW").pixmap(32, 32).toImage()
    painted_x = [
        x for x in range(image.width())
        if any(image.pixelColor(x, y).alpha() for y in range(image.height()))
    ]

    assert painted_x
    assert max(painted_x) - min(painted_x) >= 20


def test_toolbar_refresh_replaces_actions_and_dispatches_each_index(qapp):
    mw = QMainWindow()
    mw.main_toolbar = QToolBar(mw)
    mw.addToolBar(mw.main_toolbar)
    mw.build_rom_action = QAction("Build", mw)
    mw.main_toolbar.addAction(mw.build_rom_action)
    mw.external_tools = [
        {"name": "Build A", "path": "a.py", "icon": "A"},
        {"name": "Build B", "path": "b.py", "icon": "B1"},
    ]
    dispatched = []
    mw.actions = SimpleNamespace(
        run_external_script=lambda index: dispatched.append(
            (mw.external_tools[index]["name"], mw.external_tools[index]["path"])
        )
    )
    builder = ToolBarBuilder(mw)
    mw.external_tool_actions = []

    builder.refresh_external_tool_actions()
    first_actions = tuple(mw.external_tool_actions)
    for action in first_actions:
        action.trigger()
    builder.refresh_external_tool_actions()

    assert dispatched == [("Build A", "a.py"), ("Build B", "b.py")]
    assert len(mw.external_tool_actions) == 2
    assert len([a for a in mw.main_toolbar.actions() if a.text() in {"Build A", "Build B"}]) == 2
    assert not any(action in mw.main_toolbar.actions() for action in first_actions)


def test_accepted_tool_settings_refresh_live_toolbar(qapp, monkeypatch):
    from ui.main_window.actions import settings_mixin

    class AcceptedDialog:
        rules_changed_requires_rescan = False
        font_map_changed_requires_rescan = False
        _zelda_window_layouts_document = None
        plugin_changed_requires_restart = False
        theme_changed_requires_restart = False

        def __init__(self, _mw):
            pass

        def exec(self):
            return True

        def get_settings(self):
            return {
                "external_tools": [{"name": "New Tool", "path": "new.py", "icon": "N"}],
                "default_font_file": "",
                "spellchecker_language": "uk",
                "spellchecker_enabled": False,
                "restore_unsaved_on_startup": False,
            }

    monkeypatch.setattr(settings_mixin, "SettingsDialog", AcceptedDialog)
    class SettingsWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self._fallback = MagicMock()

        def __getattr__(self, name):
            return getattr(self._fallback, name)

    mw = SettingsWindow()
    mw.main_toolbar = QToolBar(mw)
    mw.addToolBar(mw.main_toolbar)
    mw.build_rom_action = QAction("Build ROM", mw)
    mw.main_toolbar.addAction(mw.build_rom_action)
    mw.external_tool_actions = []
    mw.actions = MagicMock()
    mw.toolbar_builder = ToolBarBuilder(mw)
    mw.external_tools = []
    mw.game_dialog_max_width_pixels = 208
    mw.line_width_warning_threshold_pixels = 208
    mw.lines_per_page = 4
    mw.detection_enabled = {}
    mw.default_tag_mappings = {}
    mw.use_per_window_layouts = True
    mw.fonts_dir_path = ""
    mw.default_font_file = ""
    mw.active_game_plugin = "zelda_mc"
    mw.theme = "auto"
    mw.restore_unsaved_on_startup = False
    mw.spellchecker_manager.language = "uk"
    mw.spellchecker_manager.enabled = False
    mw.data_store.json_path = None
    mw.data_store.edited_json_path = None
    mw.data_store.unsaved_changes = False
    mw.project_manager.current_project = None
    mw.app_action_handler.rescan_all_tags.reset_mock()

    MainWindowSettingsActionsMixin.open_settings_dialog(SimpleNamespace(mw=mw, helper=mw.helper))

    assert mw.external_tools == [{"name": "New Tool", "path": "new.py", "icon": "N"}]
    assert [action.text() for action in mw.external_tool_actions] == ["New Tool"]
    assert mw.app_action_handler.rescan_all_tags.call_count == 0


def test_script_launch_worker_reports_success_without_running_a_script(qapp, qtbot, monkeypatch, tmp_path):
    from ui.settings import script_launch_worker
    from utils import app_mode

    script = tmp_path / "build.py"
    script.write_text("", encoding="utf-8")
    launched = []
    monkeypatch.setattr(script_launch_worker.subprocess, "Popen", lambda *args, **kwargs: launched.append((args, kwargs)))
    monkeypatch.setattr(app_mode, "headless", False)
    worker = ScriptLaunchWorker("Build", str(script))
    try:
        with qtbot.waitSignal(worker.result, timeout=3000) as signal:
            worker.start()
        assert worker.wait(3000)

        assert signal.args[0] == worker.worker_id
        assert signal.args[1:] == ["Build", "", True]
        command = launched[0][0][0]
        if isinstance(command, str):
            assert command == f'cmd.exe /k ""{script.resolve()}""'
        else:
            assert command[-1] == str(script.resolve())
        assert launched[0][1]["cwd"] == str(tmp_path)
    finally:
        if worker.isRunning():
            safe_shutdown_thread(worker, worker)
        else:
            worker.deleteLater()


def test_script_launch_worker_reports_missing_path(qapp, qtbot, tmp_path):
    worker = ScriptLaunchWorker("Missing", str(tmp_path / "missing.py"))
    try:
        with qtbot.waitSignal(worker.result, timeout=3000) as signal:
            worker.start()
        assert worker.wait(3000)

        assert signal.args[1] == "Run External Script Error"
        assert "does not exist" in signal.args[2]
        assert signal.args[3] is False
    finally:
        if worker.isRunning():
            safe_shutdown_thread(worker, worker)
        else:
            worker.deleteLater()


def test_script_launch_worker_reports_process_start_failure(qapp, qtbot, monkeypatch, tmp_path):
    from ui.settings import script_launch_worker
    from utils import app_mode

    script = tmp_path / "build.py"
    script.write_text("", encoding="utf-8")

    def fail_to_start(*_args, **_kwargs):
        raise OSError("launch denied")

    monkeypatch.setattr(script_launch_worker.subprocess, "Popen", fail_to_start)
    monkeypatch.setattr(app_mode, "headless", False)
    worker = ScriptLaunchWorker("Build", str(script))
    try:
        with qtbot.waitSignal(worker.result, timeout=3000) as signal:
            worker.start()
        assert worker.wait(3000)

        assert "launch denied" in signal.args[2]
        assert signal.args[3] is False
    finally:
        if worker.isRunning():
            safe_shutdown_thread(worker, worker)
        else:
            worker.deleteLater()


def test_script_launch_controller_shutdown_suppresses_late_results(qapp):
    mw = QMainWindow()
    mw.statusBar = MagicMock()
    mw.show_message = MagicMock()
    controller = ScriptLaunchController(mw)
    worker = ScriptLaunchWorker("Build", "unused.py")
    controller._workers[worker.worker_id] = worker

    controller.shutdown()
    controller._on_result(worker.worker_id, "Run External Script Error", "late error", False)
    controller.launch("Later", "unused.py")

    assert controller._closing is True
    assert mw.show_message.call_count == 0
    assert mw.statusBar.showMessage.call_count == 0
    assert controller._workers == {}


def test_toolbar_build_shows_saved_tools_at_startup(qapp):
    mw = QMainWindow()
    for name in ("save", "undo_typing", "redo_typing", "find", "toggle_preview",
                 "bfn_editor", "recalculate_widths", "open_settings", "help_shortcuts"):
        setattr(mw, f"{name}_action", QAction(name, mw))
    mw.external_tools = [{"name": "Saved tool", "path": "x.bat", "icon": "S"}]
    mw.actions = SimpleNamespace(run_external_script=lambda index: None)

    ToolBarBuilder(mw).build()

    texts = [a.text() for a in mw.main_toolbar.actions()]
    assert texts.index("Saved tool") < texts.index(mw.build_rom_action.text())
    assert mw.run_external_script_action is mw.external_tool_actions[0]
