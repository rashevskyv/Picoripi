"""REVIEW_QUEUE WP6 "The block tree (6.5)": the tree populate_blocks builds is the one the pre-audit code built.

The scenario (tests/fixtures/review_queue/wp1_6/tree_scenario.py) opens a project with virtual folders, root
blocks, a MemPalace story (legacy chapters, or a normalized story with items) and manual speakers and notes in a
real MainWindow, interactive mode; tree_golden.json is what the baseline (691699c0) showed for the same steps:
the Story root's loading placeholder then its chapters, Speakers, Items / Notated / Windows / None, the
selection after a rebuild and "Show Unsaved Only".
"""
import importlib.util
import json
from pathlib import Path

import pytest

from utils import app_mode

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "review_queue" / "wp1_6"
_spec = importlib.util.spec_from_file_location("rq_wp1_6_tree_scenario", FIXTURES / "tree_scenario.py")
scenario = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scenario)
GOLDEN = json.loads((FIXTURES / "tree_golden.json").read_text(encoding="utf-8"))


@pytest.fixture
def own_settings(tmp_path, monkeypatch):
    """Settings of this test alone: the window reopens the last project of whatever test ran before."""
    import sys

    import core.settings_manager as settings_manager
    import utils.constants as constants

    settings_dir = tmp_path / "settings"
    settings_file = str(settings_dir / "settings.json")
    for module in (constants, settings_manager):
        monkeypatch.setattr(module, "SETTINGS_DIR", settings_dir)
        monkeypatch.setattr(module, "SETTINGS_FILE_PATH", settings_file)
    if "main" in sys.modules:
        monkeypatch.setattr(sys.modules["main"], "SETTINGS_FILE_PATH", settings_file, raising=False)


def _run(story, qtbot, tmp_path, monkeypatch):
    import handlers.project_action.lifecycle_mixin as lifecycle
    from core.translation.script_speaker_finder import ScriptSpeakerFinder
    from main import MainWindow

    monkeypatch.setattr(app_mode, "headless", False)
    monkeypatch.setattr(ScriptSpeakerFinder, "find_script_path", lambda self: None)
    project_file = scenario.build_project(tmp_path / story, story)
    mw = MainWindow()
    qtbot.addWidget(mw)

    def open_project(path):
        monkeypatch.setattr(lifecycle.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), "")))
        mw.project_action_handler.open_project_action()

    try:
        return scenario.run(mw, project_file, open_project, lambda p: qtbot.waitUntil(p, timeout=20000), story)
    finally:
        mw.is_testing = True  # close without the exit-time autosave and companion push
        mw.close()


@pytest.mark.parametrize("story", ["legacy", "normalized"])
def test_block_tree_is_the_one_the_pre_audit_code_built(story, qtbot, tmp_path, monkeypatch, own_settings):
    result = _run(story, qtbot, tmp_path, monkeypatch)
    golden = GOLDEN[story]

    assert result["story_states"][:2] == [["Loading..."], golden["story_states"][1]]  # placeholder, then chapters
    # The old code lost the scroll position on a rebuild (fixed; see the next test): everything else is as before.
    assert {k: v for k, v in result.items() if k != "scroll_kept"} == {k: v for k, v in golden.items() if k != "scroll_kept"}


def test_block_tree_keeps_its_scroll_position_after_a_rebuild(qtbot, tmp_path, monkeypatch, own_settings):
    result = _run("legacy", qtbot, tmp_path, monkeypatch)

    assert result["after_rebuild_selected"] == GOLDEN["legacy"]["after_rebuild_selected"]
    assert result["scroll_kept"] == [True, True]
