"""A wizard-made Yo-kai Watch project opens in a real MainWindow and shows the game text with its speakers.

Unpacks the owner's 3DS image with the wizard's job (``build.run_unpack``), then creates and opens the project with the
info the Project Manager wizard passes. Skips when the image is not on disk; writes only under pytest's tmp_path.
"""
import sys
import time
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox

import romhacking_root
from core.project_library import build
from main import MainWindow
from plugins.testing import load_rules

PLUGIN = "yokai_watch"
IMAGE = ("Yo-kai Watch", "Yo-kai Watch", "3DS", "ISO", "Yo-Kai Watch (USA).3ds")


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


def open_wizard_project(qtbot, qapp, monkeypatch, source: str, project: Path):
    """Create and open the project the wizard would make from the unpacked ``source``; returns the window."""
    for name in ("information", "warning", "critical", "question"):   # a modal box would block the offscreen run
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    mw = MainWindow()
    mw.is_testing = True
    qtbot.addWidget(mw)
    info = {"directory": str(project), "name": "Yo-kai Watch", "plugin": PLUGIN, "description": "",
            "source_path": source, "translation_path": str(project / "translation"), "is_directory_mode": True,
            "auto_create_translations": True, "platform": "", "metadata": {"unpacked": True}}
    mw.project_action_handler.finish_new_project(info)
    _pump(qapp, 120, lambda: bool(mw.data_store.data and any(mw.data_store.data)))
    return mw


@pytest.mark.timeout(600)
@pytest.mark.skipif(romhacking_root.missing(*IMAGE) is not None, reason=romhacking_root.missing(*IMAGE) or "")
@pytest.mark.usefixtures("restore_plugin_modules")
def test_3ds_wizard_project_opens_with_the_game_text_and_speakers(qtbot, qapp, tmp_path, monkeypatch):
    project = tmp_path / "project"
    source = build.run_unpack(load_rules(PLUGIN), {"base": str(romhacking_root.path(*IMAGE))}, str(project),
                              lambda percent, text: None, lambda: False)
    mw = open_wizard_project(qtbot, qapp, monkeypatch, source, project)
    assert mw.current_game_rules.__class__.__module__ == f"plugins.{PLUGIN}.rules"
    blocks = mw.data_store.data
    assert len(blocks) > 2000 and sum(1 for block in blocks for text in block if text) > 40000
    rules = mw.current_game_rules
    files = mw.project_manager.project.blocks
    mapping = mw.block_to_project_file_map or {}
    events = [index for index in range(len(blocks))
              if str(files[mapping.get(index, index)].source_file).replace("\\", "/").startswith("data/txt/ev/")]
    lines = [(index, row) for index in events[:30] for row in range(len(blocks[index]))]
    named = sum(1 for index, row in lines if rules.get_speaker_for_string(index, row))
    # the speaker tables in meta/ beside source/ name who says most event lines
    assert len(lines) > 100 and named > len(lines) // 2, (named, len(lines))
    mw.close()
