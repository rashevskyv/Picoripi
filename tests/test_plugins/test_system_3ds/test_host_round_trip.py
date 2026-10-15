"""Host round trip of the 3DS system plugin: a real MainWindow on a project whose source and translation folders are
the same folder, as in the owner's repo. The original column must show ``en`` and the editor ``ua``; an edit saved
through the host's save changes that ``ua`` only, and saving the reverted text gives back the original bytes.
"""
import json
import sys

import pytest
from PyQt6.QtWidgets import QMessageBox

from main import MainWindow
from test_plugins.test_system_3ds.test_rules import COMPACT, STRINGS

PLUGIN = "system_3ds"


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


def _save(mw, qtbot):
    result = {}
    mw.data_processor.save_current_edits(ask_confirmation=False,
                                         on_finished_callback=lambda ok: result.setdefault("ok", ok))
    qtbot.waitUntil(lambda: "ok" in result, timeout=30000)
    return result["ok"]


@pytest.mark.usefixtures("restore_plugin_modules")
def test_same_folder_project_shows_english_originals_and_saves_ukrainian_in_place(qtbot, tmp_path, monkeypatch):
    src, project = tmp_path / "src", tmp_path / "project"
    (src / "strings" / "home_menu").mkdir(parents=True)
    (src / "strings" / "area").mkdir()
    project.mkdir()
    menu = src / "strings" / "home_menu" / "message__menu.json"
    menu.write_bytes(STRINGS)
    (src / "strings" / "area" / "EU_100.json").write_bytes(COMPACT)
    (src / "strings" / "home_menu" / "_all_langs.json").write_text('{"ru": {}}', encoding="utf-8")

    for name in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "exec", lambda self, *a, **k: 0)

    mw = MainWindow()
    mw.is_testing = True
    qtbot.addWidget(mw)
    info = {"directory": str(project), "name": "round trip", "plugin": PLUGIN, "description": "",
            "source_path": str(src), "translation_path": str(src), "is_directory_mode": True,
            "auto_create_translations": False}
    mw.project_action_handler.finish_new_project(info)
    qtbot.waitUntil(lambda: len(mw.data_store.data) == 2 and all(mw.data_store.data), timeout=60000)

    names = [block.source_file for block in mw.project_manager.project.blocks]
    assert sorted(names) == ["strings/area/EU_100.json", "strings/home_menu/message__menu.json"]
    block = next(i for i, b in enumerate(mw.project_manager.project.blocks) if b.source_file.endswith("menu.json"))
    assert mw.data_store.data[block][0] == "HOME Menu"
    shown = mw.data_processor.get_current_string_text(block, 0)[0]
    assert shown == "Меню HOME"

    original = menu.read_bytes()
    assert mw.data_processor.update_edited_data(block, 0, "Меню «HOME»")
    assert _save(mw, qtbot)
    saved = json.loads(menu.read_bytes())
    assert saved["lau_title_menu"] == {"en": "HOME Menu", "ru": "Меню HOME", "ua": "Меню «HOME»"}
    assert {k: v for k, v in saved.items() if k != "lau_title_menu"} == \
        {k: v for k, v in json.loads(original).items() if k != "lau_title_menu"}

    assert mw.data_processor.update_edited_data(block, 0, shown)
    assert _save(mw, qtbot)
    assert menu.read_bytes() == original
    assert (src / "strings" / "area" / "EU_100.json").read_bytes() == COMPACT
    mw.close()
