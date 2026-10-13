"""Host round trip of the 3DS manual plugin: a real MainWindow, a folder project built in temp copies.

One string is edited through the editor's own update call and saved through the host's save; the file must then
differ from the original in that entry only. The edit is reverted the same way and the saved file must be the original
bytes again. Reads the owner's manual source only (env PICORIPI_ROMHACKING); writes only under pytest's tmp_path.
"""
import difflib
import json
import sys
import time

import pytest
from PyQt6.QtWidgets import QMessageBox

import romhacking_root
from main import MainWindow

PLUGIN = "manual_3ds"
MANUAL_DIR = ("_shared", "3ds_sysfont_ua", "repo_manual", "src", "manuals")
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
    sys.modules.update(saved)


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

    # Modal message boxes would block the offscreen run: each one answers at once.
    for name in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "exec", lambda self, *a, **k: 0)

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
