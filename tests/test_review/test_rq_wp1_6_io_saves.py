"""REVIEW_QUEUE WP6 6.1: every save goes through a temporary file and writes the bytes the old code wrote.

The scenario and the goldens live in tests/fixtures/review_queue/wp1_6/make_golden.py; the goldens were
written by the baseline worktree (691699c0). This test runs the same scenario on the current code.
"""
import importlib.util
import json
import os
import tempfile
from pathlib import Path

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from test_review._rq_wp1_6_helpers import main_window, make_plain_project, open_project  # noqa: F401

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "review_queue" / "wp1_6"


def _scenario():
    spec = importlib.util.spec_from_file_location("rq_wp1_6_make_golden", GOLDEN_DIR / "make_golden.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _golden(name: str) -> bytes:
    """A golden written on Windows; elsewhere the old code wrote the platform's own line ending."""
    data = (GOLDEN_DIR / name).read_bytes()
    return data if os.linesep == "\r\n" else data.replace(b"\r\n", os.linesep.encode())


def _leftovers(*folders) -> list:
    return [str(p) for folder in folders if Path(folder).exists() for p in Path(folder).rglob("*.tmp")]


def test_translation_archive_glossary_settings_and_session_are_written_as_before(qtbot, tmp_path):
    scenario = _scenario()
    root = tmp_path / "work"
    out = scenario.run_scenarios(root, lambda predicate: qtbot.waitUntil(predicate, timeout=20000))

    # Line endings included: the LF file and the CRLF file are both written with the platform's ending, as before.
    assert out["translation_lf"] == _golden("save_translation_lf.bin")
    assert out["translation_crlf"] == _golden("save_translation_crlf.bin")
    # The BMG inside the .arc is rebuilt and the archive repacked to exactly the old bytes.
    assert out["translation_archive"] == (GOLDEN_DIR / "save_translation_archive.bin").read_bytes()
    # WP3 3.6 added a stable "id" to every entry on purpose (REVIEW_QUEUE WP3); the rest is byte for byte as before.
    from core.glossary.models import legacy_entry_id
    expected_glossary = _golden("save_glossary.bin")
    newline = os.linesep.encode()
    for entry in scenario.GLOSSARY_IN:
        flag = b'"profiled": ' + json.dumps(entry["profiled"]).encode()
        expected_glossary = expected_glossary.replace(
            flag + newline,
            flag + b"," + newline + b'    "id": "' + legacy_entry_id(entry["original"]).encode() + b'"' + newline,
            1,
        )
    assert out["glossary"] == expected_glossary

    # Settings: the run's folders are placeholders. The only change is the AI defaults added on purpose by the
    # audit (WP1 provider "profile"; WP4 fold_duplicates / fixed_output_sections; review_enabled).
    settings = scenario.normalize_settings(out["settings"], root)
    old_bytes = _golden("save_settings.json.bin")

    def dump(data):  # the old writer's format, proven by the first assert below
        return json.dumps(data, indent=4, ensure_ascii=False).replace("\n", os.linesep).encode("utf-8")

    old, new = json.loads(old_bytes), json.loads(settings)
    assert dump(old) == old_bytes
    added = set(new["translation_config"]) - set(old["translation_config"])
    assert added == {"review_enabled", "fold_duplicates", "fixed_output_sections"}
    assert set(new["translation_config"]["providers"]["openai"]) - set(old["translation_config"]["providers"]["openai"]) == {"profile"}
    assert settings == dump({**old, "translation_config": new["translation_config"]})

    session = scenario.normalize_session(out["session"], root)
    assert session == json.loads((GOLDEN_DIR / "save_session.json").read_text(encoding="utf-8"))

    # No name.ext.<random>.tmp is left next to any saved file, nor in the archive extraction folder.
    assert _leftovers(root, Path(tempfile.gettempdir()) / "picoripi") == []


@pytest.mark.skipif(os.name != "nt", reason="a file held open blocks a rename only on Windows")
def test_a_locked_translation_file_is_reported_and_left_whole(main_window, qtbot, tmp_path, monkeypatch):  # noqa: F811
    """An open handle (an antivirus, a sync client) blocks the rename: three tries, then an error box."""
    import utils.atomic_io as atomic_io

    project = make_plain_project(tmp_path, {"a": ["Hello", "World"]})
    open_project(main_window, project, monkeypatch, qtbot)
    target = tmp_path / "translation" / "a.txt"
    before = target.read_bytes()

    attempts = []
    real_replace = atomic_io.os.replace

    def counting_replace(source, destination):
        attempts.append(destination)
        return real_replace(source, destination)

    monkeypatch.setattr(atomic_io.os, "replace", counting_replace)

    boxes = []

    def answer_boxes():
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                boxes.append((widget.windowTitle(), widget.text()))
                widget.done(0)

    timer = QTimer()
    timer.timeout.connect(answer_boxes)
    timer.start(20)
    saved = []
    try:
        main_window.data_processor.update_edited_data(0, 1, "Світ")
        with open(target, "rb"):  # held open by "another process" for the whole save
            main_window.data_processor.save_current_edits(ask_confirmation=False, on_finished_callback=saved.append)
            qtbot.waitUntil(lambda: bool(saved), timeout=10000)
    finally:
        timer.stop()

    assert saved == [False]
    assert len([a for a in attempts if Path(a) == target]) == 3
    assert any("Save Error" in title for title, _ in boxes), boxes
    assert target.read_bytes() == before                     # the old file, whole
    assert _leftovers(target.parent) == []
    assert main_window.data_store.unsaved_changes            # the edit is still there to save again
