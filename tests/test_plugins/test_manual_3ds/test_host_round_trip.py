"""Host round trip of the 3DS manual plugin: a real MainWindow, a folder project built in temp copies.

One string is edited through the editor's own update call and saved through the host's save; the file must then
differ from the original in that entry only. The edit is reverted the same way and the saved file must be the original
bytes again. The startup tests restart the app on a project with a session, as run.bat does, and check the manual
preview. Reads the owner's manual source only (env PICORIPI_ROMHACKING); writes only under pytest's tmp_path.
"""
import difflib
import json
import pickle
import sys
import time
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox

import romhacking_root
from main import MainWindow

PLUGIN = "manual_3ds"
REPO_MANUAL = ("_shared", "3ds_sysfont_ua", "repo_manual")
MANUAL_DIR = (*REPO_MANUAL, "src", "manuals")
MANUAL_FILE = "activity_log.json"


@pytest.fixture
def restore_plugin_modules():
    """The host drops and re-imports a plugin's modules when it loads it. Put the old module objects back afterwards,
    so the other tests of this plugin keep the classes they imported."""
    prefix = f"plugins.{PLUGIN}"
    saved = {name: module for name, module in sys.modules.items() if name == prefix or name.startswith(prefix + ".")}
    yield
    for name in [n for n in sys.modules if n == prefix or n.startswith(prefix + ".")]:
        del sys.modules[name]
    sys.modules.update(saved)  # deslop: ignore[module-mocking] restores the snapshot taken above


def _pump(qapp, seconds, until):
    end = time.time() + seconds
    while time.time() < end and not until():
        qapp.processEvents()
        time.sleep(0.02)


def _save(mw, qapp):
    result = {}
    mw.data_processor.save_current_edits(ask_confirmation=False,
                                         on_finished_callback=lambda ok: result.setdefault("ok", ok))
    _pump(qapp, 30, lambda: "ok" in result)
    return result.get("ok") is True


def _answer_message_boxes(monkeypatch):
    """Modal message boxes would block the offscreen run: each one answers at once."""
    for name in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "exec", lambda self, *a, **k: 0)


@pytest.mark.skipif(romhacking_root.missing(*MANUAL_DIR) is not None,
                    reason=romhacking_root.missing(*MANUAL_DIR) or "")
@pytest.mark.usefixtures("restore_plugin_modules")
def test_edit_save_revert_save_gives_back_the_original_file(qtbot, qapp, tmp_path, monkeypatch):
    original = romhacking_root.path(*MANUAL_DIR, MANUAL_FILE).read_bytes()
    document = json.loads(original.decode("utf-8"))
    source, translation, project = tmp_path / "source", tmp_path / "translation", tmp_path / "project"
    for folder in (source, translation, project):
        folder.mkdir()
    stripped = {key: {k: v for k, v in entry.items() if k != "ua"} for key, entry in document.items()}
    (source / MANUAL_FILE).write_text(json.dumps(stripped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    translation_file = translation / MANUAL_FILE
    translation_file.write_bytes(original)

    _answer_message_boxes(monkeypatch)

    mw = MainWindow()
    mw.is_testing = True
    qtbot.addWidget(mw)
    info = {"directory": str(project), "name": "round trip", "plugin": PLUGIN, "description": "",
            "source_path": str(source), "translation_path": str(translation), "is_directory_mode": True,
            "auto_create_translations": False}
    mw.project_action_handler.finish_new_project(info)
    _pump(qapp, 60, lambda: bool(mw.data_store.data and mw.data_store.data[0]))
    assert mw.current_game_rules is not None and mw.current_game_rules.__class__.__module__.endswith("rules")

    index = next(i for i, key in enumerate(document) if i > 2 and document[key].get("ua"))
    key = list(document)[index]
    shown = mw.data_processor.get_current_string_text(0, index)[0]
    assert shown == document[key]["ua"]

    assert mw.data_processor.update_edited_data(0, index, shown + " тест")
    assert _save(mw, qapp)
    edited = translation_file.read_bytes()
    edited_doc = json.loads(edited.decode("utf-8"))
    assert [k for k in document if edited_doc[k].get("ua") != document[k].get("ua")] == [key]
    changed = [line for line in difflib.ndiff(original.decode("utf-8").splitlines(),
                                              edited.decode("utf-8").splitlines()) if line[:1] in "+-"]
    assert len(changed) == 2  # one line out, one line in

    assert mw.data_processor.update_edited_data(0, index, shown)
    assert _save(mw, qapp)
    assert translation_file.read_bytes() == original
    mw.close()


@pytest.mark.skipif(romhacking_root.missing(*MANUAL_DIR) is not None,
                    reason=romhacking_root.missing(*MANUAL_DIR) or "")
@pytest.mark.usefixtures("restore_plugin_modules")
def test_a_project_on_the_owner_files_in_place_shows_english_as_original_and_ukrainian_as_edited(
        qtbot, qapp, tmp_path, monkeypatch):
    """Regression: the owner's project reads repo_manual/src/manuals in place (source = translation folder), and those
    files hold en, ru and ua; the Original (EN) column showed the Ukrainian. Runs on a copy of the owner's file."""
    original = romhacking_root.path(*MANUAL_DIR, MANUAL_FILE).read_bytes()
    document = json.loads(original.decode("utf-8"))
    manuals, project = tmp_path / "manuals", tmp_path / "project"
    for folder in (manuals, project):
        folder.mkdir()
    (manuals / MANUAL_FILE).write_bytes(original)
    _answer_message_boxes(monkeypatch)

    mw = MainWindow()
    mw.is_testing = True
    qtbot.addWidget(mw)
    info = {"directory": str(project), "name": "in place", "plugin": PLUGIN, "description": "",
            "source_path": str(manuals), "translation_path": str(manuals), "is_directory_mode": True,
            "auto_create_translations": False}
    mw.project_action_handler.finish_new_project(info)
    _pump(qapp, 60, lambda: bool(mw.data_store.data and mw.data_store.data[0]))

    entries = list(document.values())
    assert mw.data_store.data[0] == [entry.get("en") or entry.get("ru", "") for entry in entries]
    assert [mw.data_processor.get_current_string_text(0, index)[0] for index in range(len(entries))] == \
        [entry.get("ua", "") for entry in entries]
    assert any(entry.get("en") and entry.get("ua") and entry["en"] != entry["ua"] for entry in entries)
    mw.close()


def _restart_with_session(qtbot, tmp_path, monkeypatch, manuals, *, plugin_state, repo_manual=""):
    """Open a project of ``manuals`` ({file name: text}) once, so it writes its session on close, then start the app
    again as run.bat does: the startup plugin is the project's, the project opens from its session."""
    import core.settings_manager as settings_module
    import utils.constants as constants
    from components.startup_splash import StartupSplash
    from core.project_manager import ProjectManager

    # conftest gives each test its own user data folder (constants.SETTINGS_DIR) and settings file.
    constants.user_plugin_dir(PLUGIN).mkdir(parents=True, exist_ok=True)
    (constants.user_plugin_dir(PLUGIN) / "preview.json").write_text(json.dumps({"repo_manual": repo_manual}),
                                                                   encoding="utf-8")
    _answer_message_boxes(monkeypatch)
    source = tmp_path / "manuals"
    source.mkdir()
    for name, text in manuals.items():
        (source / name).write_text(text, encoding="utf-8")
    project_file = tmp_path / "project" / "project.uiproj"
    assert ProjectManager().create_new_project(
        project_dir=project_file.parent, name="manuals", plugin_name=PLUGIN,
        source_path=str(source), translation_path=str(source), is_directory_mode=True)
    settings_file = Path(settings_module.SETTINGS_FILE_PATH)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps({
        "active_game_plugin": PLUGIN, "last_opened_path": str(project_file),
        "recent_projects": [str(project_file)], "preview_enabled": True}), encoding="utf-8")

    first = MainWindow()  # opens the project from its files
    qtbot.waitUntil(lambda: len(first.data_store.data) == len(manuals) and not first.is_loading_data, timeout=60000)
    _open_first_block(first, qtbot)  # the session keeps the open block, as the owner's did
    first.data_processor._autosave_session(force=True)  # what the app's close does; a test close skips it
    first.close()
    first.deleteLater()
    session = project_file.parent / ".picoripi_session"
    assert session.with_name(session.name + ".clean").exists()
    if not plugin_state:  # a session written before the plugin kept its manuals
        snapshot = pickle.loads(session.read_bytes())
        assert snapshot.pop("plugin_runtime_state", None) is not None
        session.write_bytes(pickle.dumps(snapshot))

    mw = MainWindow(startup_splash=StartupSplash())
    qtbot.addWidget(mw)
    if not mw._startup_loading_pending:
        mw.finish_startup_loading()
    qtbot.waitUntil(lambda: mw._startup_splash is None and len(mw.data_store.data) == len(manuals)
                    and not mw.is_loading_data and mw.data_store.current_block_idx == 0, timeout=60000)
    assert mw.data_processor.session_had_plugin_state() is plugin_state
    return mw


def _manual_preview_shown(mw):
    """The plugin's panel is docked in the preview column, the column is shown and the toggle is on."""
    from ui.components.custom_preview import custom_preview_of

    panel = custom_preview_of(mw)
    assert panel is not None, "the manual preview is not docked"
    # The host re-imports the plugin's modules when it loads it: compare with the class it uses.
    assert type(panel) is sys.modules[f"plugins.{PLUGIN}.preview_panel"].ManualPreviewPanel
    assert mw.bfn_preview_column.isVisible()
    assert mw.toggle_preview_action.isEnabled() and mw.toggle_preview_action.isChecked()
    return panel


def _open_first_block(mw, qtbot):
    """Click the first block in the tree."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QTreeWidgetItemIterator

    iterator = QTreeWidgetItemIterator(mw.block_list_widget)
    while iterator.value() and iterator.value().data(0, Qt.ItemDataRole.UserRole) != 0:
        iterator += 1
    mw.block_list_widget.setCurrentItem(iterator.value())
    qtbot.waitUntil(lambda: mw.data_store.current_block_idx == 0, timeout=5000)


def _select_string(mw, qtbot, string_idx):
    """Click a line of the block the restart opened, in the preview list."""
    mw.list_selection_handler.select_string_by_absolute_index(string_idx)
    qtbot.waitUntil(lambda: mw.data_store.current_string_idx == string_idx, timeout=5000)


def _home_menu_document():
    """A manual with the keys of home_menu_manual (from the plugin's geometry table) and placeholder text."""
    from utils.constants import plugins_root

    geometry = json.loads((plugins_root() / PLUGIN / "geometry.json").read_text(encoding="utf-8"))["manuals"]
    keys = next(value for value in geometry.values() if value.get("name") == "home_menu_manual")["entries"]
    return json.dumps({key: {"lines": 1, "width": 300.0, "en": "Text", "ru": "Text", "ua": "Текст"} for key in keys},
                      ensure_ascii=False)


@pytest.mark.parametrize("plugin_state", [True, False], ids=["session_with_plugin_state", "old_session"])
@pytest.mark.usefixtures("restore_plugin_modules")
def test_a_restart_on_a_manual_project_shows_the_manual_preview(qtbot, tmp_path, monkeypatch, plugin_state):
    """Regression: the startup plugin load runs before the preview column exists, and the project opened at startup
    reuses that plugin, so the manual preview was never docked: no preview column and a disabled toggle."""
    document = _home_menu_document()
    mw = _restart_with_session(qtbot, tmp_path, monkeypatch, {"one.json": document, "two.json": document},
                               plugin_state=plugin_state)
    panel = _manual_preview_shown(mw)
    # The glossary belongs to the project: the startup glossary load ran before the project opened, so the project
    # open that reuses the startup plugin must load it again (highlighting, AI prompts).
    glossary = mw.translation_handler.glossary_handler.glossary_manager.glossary_path
    assert glossary is not None and Path(glossary) == tmp_path / "project" / "glossary.json"
    rules = mw.current_game_rules
    page_name_of = sys.modules[f"plugins.{PLUGIN}.preview_panel"].page_name_of
    paragraph = next(index for index in range(len(mw.data_store.data[0]))
                     if page_name_of(rules.string_key(0, index) or ""))
    _select_string(mw, qtbot, paragraph)
    # No repo_manual folder here: the page paragraph reaches the drawing step, which asks for the folder.
    qtbot.waitUntil(lambda: panel._message == "Set the repo_manual folder to draw the page.", timeout=30000)


@pytest.mark.skipif(romhacking_root.missing(*REPO_MANUAL, "tools", "manual.py") is not None,
                    reason=romhacking_root.missing(*REPO_MANUAL, "tools", "manual.py") or "")
@pytest.mark.parametrize("plugin_state", [True, False], ids=["session_with_plugin_state", "old_session"])
@pytest.mark.usefixtures("restore_plugin_modules")
def test_a_restart_on_the_owner_manuals_draws_the_selected_paragraph(qtbot, tmp_path, monkeypatch, plugin_state):
    """The owner's case: activity_log string 22 ("large/Page_001_large_0#10") is drawn with its Ukrainian text."""
    names = (MANUAL_FILE, "ar_games.json")
    manuals = {name: romhacking_root.path(*MANUAL_DIR, name).read_text(encoding="utf-8") for name in names}
    folder = romhacking_root.path(*REPO_MANUAL)
    mw = _restart_with_session(qtbot, tmp_path, monkeypatch, manuals, plugin_state=plugin_state,
                               repo_manual=str(folder))
    panel = _manual_preview_shown(mw)
    assert mw.project_manager.project.blocks[0].name == "activity_log"
    assert mw.current_game_rules.string_key(0, 22) == "large/Page_001_large_0#10"
    _select_string(mw, qtbot, 22)
    tools = sys.modules[f"plugins.{PLUGIN}.preview_panel"].repo_tools.load_tools(str(folder))
    word = tools.manual.apply_homoglyphs("кроків", tools.manual.load_homoglyphs())  # drawn as the build writes it
    qtbot.waitUntil(lambda: panel._result is not None and word in " ".join(run.text for run in panel._result.runs),
                    timeout=60000)
