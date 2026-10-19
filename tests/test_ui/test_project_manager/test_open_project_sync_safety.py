"""Deterministic tests for open-project persistence safety, staleness protection,
cancellation commit points, execution context, and glossary loading.
"""
from __future__ import annotations

import json
from pathlib import Path
import threading
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication, QWidget

from core.glossary.series import GROUP_METADATA_KEY
from core.project_manager import ProjectManager
from core.project_models import Block, Project
from ui.project_manager.group_glossary import (
    GroupGlossaryFileJob,
    InspectGlossaryJob,
    OpenProjectSyncJob,
    update_project_group_glossary,
)
from ui.project_manager.window import ProjectManagerDialog


def _make_project(folder: Path, name: str, blocks: list | None = None, metadata: dict | None = None) -> Path:
    picoripi = folder / name / "picoripi"
    picoripi.mkdir(parents=True, exist_ok=True)
    p_file = picoripi / "project.uiproj"
    p_file.write_text(
        json.dumps({
            "id": name,
            "name": name,
            "plugin_name": "plain_text",
            "metadata": metadata or {},
            "blocks": blocks or [],
        }),
        encoding="utf-8",
    )
    return p_file


def _make_glossary(path: Path, entries: list | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries or [{"original": "Test", "translation": "Тест"}]), encoding="utf-8")
    return path


def test_intervening_save_is_not_overwritten_by_sync_job(tmp_path: Path) -> None:
    p_file = _make_project(tmp_path, "Game", blocks=[{"id": "b1", "text": "initial"}])
    glossary = _make_glossary(tmp_path / "glossary.json")

    job = OpenProjectSyncJob(p_file, str(glossary), [glossary])

    # An intervening save writes newer blocks and settings before job.run() executes
    intervening_data = {
        "id": "Game",
        "name": "Game",
        "plugin_name": "plain_text",
        "metadata": {"user_setting": 42},
        "blocks": [{"id": "b1", "text": "initial"}, {"id": "b2", "text": "newer save"}],
    }
    p_file.write_text(json.dumps(intervening_data), encoding="utf-8")

    job.run()

    # The group glossary was persisted to disk
    result = json.loads(p_file.read_text(encoding="utf-8"))
    assert result["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())
    # Crucial: the newer blocks and user setting were preserved, not clobbered!
    assert result["metadata"]["user_setting"] == 42
    assert len(result["blocks"]) == 2
    assert result["blocks"][1]["text"] == "newer save"


def test_rapid_consecutive_group_changes_supersede_earlier_jobs(qtbot, tmp_path: Path) -> None:
    gloss_a = _make_glossary(tmp_path / "gloss_a.json", [{"original": "A", "translation": "А"}])
    gloss_b = _make_glossary(tmp_path / "gloss_b.json", [{"original": "B", "translation": "Б"}])
    p_file = _make_project(tmp_path / "proj", "ActiveProj")

    parent_widget = QWidget()
    fake_pm = MagicMock()
    fake_project = Project(name="ActiveProj")
    fake_pm.project = fake_project
    fake_pm.project_file_path = str(p_file)
    parent_widget.project_manager = fake_pm

    glossary_handler = MagicMock()
    glossary_handler.series_glossary_managers = []
    parent_widget.translation_handler = MagicMock()
    parent_widget.translation_handler.glossary_handler = glossary_handler

    dialog = ProjectManagerDialog(
        parent_widget,
        str(tmp_path),
        lambda p: None,
        lambda: None,
        lambda p, u: None,
        lambda n, v: None,
    )
    qtbot.addWidget(parent_widget)
    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)

    # Trigger change to Group A
    dialog._document["folders"] = [
        {"id": "fid_a", "name": "Folder A", "glossary_path": str(gloss_a)},
        {"id": "fid_b", "name": "Folder B", "glossary_path": str(gloss_b)},
    ]
    dialog._document["projects"] = [{"path": str(p_file), "folder_id": "fid_a"}]
    dialog._sync_open_project_if_needed()

    # Immediately trigger rapid change to Group B before A settles
    dialog._document["projects"] = [{"path": str(p_file), "folder_id": "fid_b"}]
    dialog._sync_open_project_if_needed()

    qtbot.waitUntil(lambda: len(dialog._jobs) == 0, timeout=5000)

    # In-memory and disk state match the latest request (Group B)
    assert fake_project.metadata[GROUP_METADATA_KEY] == str(gloss_b.resolve())
    disk_data = json.loads(p_file.read_text(encoding="utf-8"))
    assert disk_data["metadata"][GROUP_METADATA_KEY] == str(gloss_b.resolve())

    # Live glossary managers match Group B
    assert len(glossary_handler.series_glossary_managers) == 1
    assert glossary_handler.series_glossary_managers[0].glossary_path == gloss_b.resolve()


def test_project_switching_guards_callbacks(qtbot, tmp_path: Path) -> None:
    gloss = _make_glossary(tmp_path / "gloss.json")
    p_a = _make_project(tmp_path / "proj_a", "ProjA")
    p_b = _make_project(tmp_path / "proj_b", "ProjB")

    parent_widget = QWidget()
    fake_pm = MagicMock()
    fake_proj_a = Project(name="ProjA")
    fake_pm.project = fake_proj_a
    fake_pm.project_file_path = str(p_a)
    parent_widget.project_manager = fake_pm

    glossary_handler = MagicMock()
    glossary_handler.series_glossary_managers = []
    parent_widget.translation_handler = MagicMock()
    parent_widget.translation_handler.glossary_handler = glossary_handler

    dialog = ProjectManagerDialog(
        parent_widget,
        str(tmp_path),
        lambda p: None,
        lambda: None,
        lambda p, u: None,
        lambda n, v: None,
    )
    qtbot.addWidget(parent_widget)
    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)

    dialog._document["folders"] = [{"id": "fid_a", "name": "FA", "glossary_path": str(gloss)}]
    dialog._document["projects"] = [{"path": str(p_a), "folder_id": "fid_a"}]

    # Start sync for ProjA
    dialog._sync_open_project_if_needed()

    # User switches project to ProjB while sync is in flight
    fake_proj_b = Project(name="ProjB")
    fake_pm.project = fake_proj_b
    fake_pm.project_file_path = str(p_b)

    qtbot.waitUntil(lambda: len(dialog._jobs) == 0, timeout=5000)

    # ProjB's in-memory metadata was NOT polluted by ProjA's sync callback
    assert GROUP_METADATA_KEY not in fake_proj_b.metadata


def test_sync_job_cancellation_before_commit_reverts_memory(tmp_path: Path, monkeypatch) -> None:
    glossary = _make_glossary(tmp_path / "gloss.json")
    p_file = _make_project(tmp_path, "Game", metadata={GROUP_METADATA_KEY: "prior.json"})

    job = OpenProjectSyncJob(p_file, str(glossary), [glossary])
    monkeypatch.setattr(job, "isInterruptionRequested", lambda: True)

    cancelled = []
    job.cancelled.connect(lambda: cancelled.append(True))
    job.run()

    assert len(cancelled) == 1
    assert not job.committed
    # Disk remains untouched at prior state
    disk_data = json.loads(p_file.read_text(encoding="utf-8"))
    assert disk_data["metadata"][GROUP_METADATA_KEY] == "prior.json"


def test_sync_job_cancellation_after_commit_reconciles_success(tmp_path: Path, monkeypatch) -> None:
    glossary = _make_glossary(tmp_path / "gloss.json")
    p_file = _make_project(tmp_path, "Game")

    job = OpenProjectSyncJob(p_file, str(glossary), [glossary])

    interrupted = False
    monkeypatch.setattr(job, "isInterruptionRequested", lambda: interrupted)

    import ui.project_manager.group_glossary as gg_mod
    orig_write = gg_mod.atomic_write_json
    injection_count = 0

    def trigger_interruption_after_write(*args, **kwargs):
        nonlocal interrupted, injection_count
        res = orig_write(*args, **kwargs)
        interrupted = True
        injection_count += 1
        return res

    monkeypatch.setattr(gg_mod, "atomic_write_json", trigger_interruption_after_write)

    results = []
    job.done.connect(lambda managers, warnings: results.append((managers, warnings)))
    job.run()

    assert injection_count == 1
    assert job.committed
    # Reconciled success: emitted done, not cancelled
    assert len(results) == 1
    managers, _warnings = results[0]
    assert len(managers) == 1
    assert managers[0].glossary_path == glossary.resolve()

    # Disk matches
    disk_data = json.loads(p_file.read_text(encoding="utf-8"))
    assert disk_data["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())


def test_sync_job_missing_and_unreadable_glossaries_reported_in_warnings(tmp_path: Path) -> None:
    p_file = _make_project(tmp_path, "Game")
    missing_gloss = tmp_path / "does_not_exist.json"
    invalid_gloss = tmp_path / "broken.json"
    invalid_gloss.write_text("NOT_JSON", encoding="utf-8")

    job = OpenProjectSyncJob(p_file, None, [missing_gloss, invalid_gloss])

    results = []
    job.done.connect(lambda managers, warnings: results.append((managers, warnings)))
    job.run()

    assert len(results) == 1
    managers, warnings = results[0]
    assert len(managers) == 0
    # Missing and unreadable glossaries were NOT silently ignored
    assert any("does_not_exist" in w for w in warnings)
    assert any("broken" in w for w in warnings)


def test_inspect_glossary_job_runs_off_ui_thread(qtbot, tmp_path: Path) -> None:
    plain = _make_glossary(tmp_path / "plain.json")
    job = InspectGlossaryJob(plain)

    execution_threads = []
    job._source_path = MagicMock()
    job._source_path.resolve.return_value = plain.resolve()
    job._source_path.read_text.side_effect = lambda *a, **kw: (
        execution_threads.append(QThread.currentThread()),
        plain.read_text(*a, **kw),
    )[1]

    results = []
    job.done.connect(results.append)
    with qtbot.waitSignal(job.done, timeout=5000):
        job.start()

    assert len(results) == 1
    assert results[0] is False  # plain list does not need conversion
    assert len(execution_threads) >= 1
    # Worker thread execution context verified
    assert execution_threads[0] != QApplication.instance().thread()


def test_group_glossary_file_job_conversion_cancellation_rolls_back_target(tmp_path: Path, monkeypatch) -> None:
    series_doc = {
        "terms": [{
            "term": "Hero",
            "recommended": "Герой",
            "renderings": [{"uk": "Герой", "source": "G1"}],
        }],
    }
    src = tmp_path / "src.json"
    src.write_text(json.dumps(series_doc), encoding="utf-8")

    target_dir = tmp_path / "out"
    job = GroupGlossaryFileJob("link", src, target_dir=target_dir)

    target_file = target_dir / "src.json"

    interrupted = False
    monkeypatch.setattr(job, "isInterruptionRequested", lambda: interrupted)

    import ui.project_manager.group_glossary as gg_mod
    orig_fn = gg_mod.import_series_glossary

    def interrupt_after_conversion(source, target):
        nonlocal interrupted
        orig_fn(source, target)
        interrupted = True

    monkeypatch.setattr(gg_mod, "import_series_glossary", interrupt_after_conversion)
    cancelled = []
    job.cancelled.connect(lambda: cancelled.append(True))
    job.run()

    assert len(cancelled) == 1
    # Target file created during conversion was cleanly unlinked upon cancellation!
    assert not target_file.exists()


def test_barrier_intervening_save_preserves_newer_fields(qtbot, tmp_path: Path, monkeypatch) -> None:
    p_file = _make_project(
        tmp_path,
        "Game",
        blocks=[{"id": "b1", "text": "initial"}],
        metadata={"removed_setting": "old", "keep": "yes"},
    )
    glossary = _make_glossary(tmp_path / "glossary.json")

    fake_pm = ProjectManager()
    fake_project = Project(name="Game")
    fake_project.metadata = {"removed_setting": "old", "keep": "yes"}
    fake_project.blocks = [Block(id="b1", name="initial")]
    fake_pm.project = fake_project
    fake_pm.project_file_path = str(p_file)

    at_lock_barrier = threading.Event()
    resume_barrier = threading.Event()

    import ui.project_manager.group_glossary as gg_mod
    orig_lock = gg_mod.project_persistence_lock

    def barrier_lock(path):
        at_lock_barrier.set()
        resume_barrier.wait(timeout=5.0)
        return orig_lock(path)

    monkeypatch.setattr(gg_mod, "project_persistence_lock", barrier_lock)

    job = OpenProjectSyncJob(p_file, str(glossary), [glossary], request_seq=1)
    results = []
    job.done.connect(lambda managers, warnings: results.append((managers, warnings)))

    job.start()

    # Wait until job reaches persistence lock barrier
    assert at_lock_barrier.wait(timeout=5.0)

    # Intervening save: delete removed_setting, add new_setting, append block
    fake_project.metadata.pop("removed_setting", None)
    fake_project.metadata["new_setting"] = "fresh"
    fake_project.blocks.append(Block(id="b2", name="saved during pause"))
    assert fake_pm.save() is True

    # Resume the sync job write
    resume_barrier.set()
    qtbot.waitUntil(lambda: len(results) == 1, timeout=5000)

    # Disk check: deletions not resurrected, new setting kept, newer blocks preserved
    disk_data = json.loads(p_file.read_text(encoding="utf-8"))
    assert "removed_setting" not in disk_data["metadata"]
    assert disk_data["metadata"]["keep"] == "yes"
    assert disk_data["metadata"]["new_setting"] == "fresh"
    assert disk_data["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())
    assert len(disk_data["blocks"]) == 2
    assert disk_data["blocks"][1]["name"] == "saved during pause"

    # Memory check
    assert "removed_setting" not in fake_pm.project.metadata
    assert fake_pm.project.metadata["keep"] == "yes"
    assert fake_pm.project.metadata["new_setting"] == "fresh"
    assert len(fake_pm.project.blocks) == 2

    # Live glossary state check
    managers, _warnings = results[0]
    assert len(managers) == 1
    assert managers[0].glossary_path == glossary.resolve()


def test_barrier_superseded_interrupted_job_does_not_overwrite_newer_commit(qtbot, tmp_path: Path, monkeypatch) -> None:
    gloss_a = _make_glossary(tmp_path / "gloss_a.json")
    gloss_b = _make_glossary(tmp_path / "gloss_b.json")
    p_file = _make_project(tmp_path, "Game")

    parent_widget = QWidget()
    fake_pm = MagicMock()
    fake_project = Project(name="Game")
    fake_pm.project = fake_project
    fake_pm.project_file_path = str(p_file)
    parent_widget.project_manager = fake_pm

    glossary_handler = MagicMock()
    glossary_handler.series_glossary_managers = []
    parent_widget.translation_handler = MagicMock()
    parent_widget.translation_handler.glossary_handler = glossary_handler

    dialog = ProjectManagerDialog(
        parent_widget,
        str(tmp_path),
        lambda p: None,
        lambda: None,
        lambda p, u: None,
        lambda n, v: None,
    )
    qtbot.addWidget(parent_widget)
    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)

    dialog._document["folders"] = [
        {"id": "fid_a", "name": "Folder A", "glossary_path": str(gloss_a)},
        {"id": "fid_b", "name": "Folder B", "glossary_path": str(gloss_b)},
    ]
    dialog._document["projects"] = [{"path": str(p_file), "folder_id": "fid_a"}]

    job_a_at_lock = threading.Event()
    resume_job_a = threading.Event()
    job_a_paused = False

    import ui.project_manager.group_glossary as gg_mod
    orig_lock = gg_mod.project_persistence_lock

    def barrier_lock(path):
        nonlocal job_a_paused
        if not job_a_paused:
            job_a_paused = True
            job_a_at_lock.set()
            resume_job_a.wait(timeout=5.0)
        return orig_lock(path)

    monkeypatch.setattr(gg_mod, "project_persistence_lock", barrier_lock)

    # 1. Trigger sync for Group A
    dialog._sync_open_project_if_needed()
    job_a = dialog._open_sync_job
    assert job_a is not None

    # Wait until Job A is paused at its lock acquisition
    assert job_a_at_lock.wait(timeout=5.0)

    # 2. Rapid switch to Group B
    dialog._document["projects"] = [{"path": str(p_file), "folder_id": "fid_b"}]
    dialog._sync_open_project_if_needed()
    job_b = dialog._open_sync_job
    assert job_b is not None
    assert job_b != job_a
    assert job_a.isInterruptionRequested()

    # Let Job B run and finish its commit
    qtbot.waitUntil(lambda: job_b.committed, timeout=5000)

    # 3. Resume Job A
    resume_job_a.set()
    qtbot.waitUntil(lambda: len(dialog._jobs) == 0, timeout=5000)

    # Disk must have Group B, NOT overwritten by superseded Job A!
    disk_data = json.loads(p_file.read_text(encoding="utf-8"))
    assert disk_data["metadata"][GROUP_METADATA_KEY] == str(gloss_b.resolve())

    # In-memory project metadata matches Group B
    assert fake_project.metadata[GROUP_METADATA_KEY] == str(gloss_b.resolve())

    # Live glossary matches Group B
    assert len(glossary_handler.series_glossary_managers) == 1
    assert glossary_handler.series_glossary_managers[0].glossary_path == gloss_b.resolve()


def test_group_glossary_file_job_cancellation_after_replacing_existing_target_restores_bytes(tmp_path: Path, monkeypatch) -> None:
    series_doc = {
        "terms": [{
            "term": "Hero",
            "recommended": "Герой",
            "renderings": [{"uk": "Герой", "source": "G1"}],
        }],
    }
    src = tmp_path / "src.json"
    src.write_text(json.dumps(series_doc), encoding="utf-8")

    target_dir = tmp_path / "out"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "src.json"
    original_content = b'[{"original": "Prior", "translation": "\xd0\x9f\xd0\xbe\xd0\xbf\xd0\xb5\xd1\x80\xd0\xb5\xd0\xb4\xd0\xbd\xd1\x96\xd0\xb9"}]'
    target_file.write_bytes(original_content)

    job = GroupGlossaryFileJob("link", src, target_dir=target_dir, overwrite=True)

    interrupted = False
    monkeypatch.setattr(job, "isInterruptionRequested", lambda: interrupted)

    import ui.project_manager.group_glossary as gg_mod
    orig_fn = gg_mod.import_series_glossary

    def interrupt_after_conversion(source, target):
        nonlocal interrupted
        orig_fn(source, target)
        interrupted = True

    monkeypatch.setattr(gg_mod, "import_series_glossary", interrupt_after_conversion)
    cancelled = []
    job.cancelled.connect(lambda: cancelled.append(True))
    job.run()

    assert len(cancelled) == 1
    # Original bytes are restored atomically upon cancellation
    assert target_file.read_bytes() == original_content


def test_group_glossary_file_job_cancellation_restoration_failure_reports_path(tmp_path: Path, monkeypatch) -> None:
    series_doc = {
        "terms": [{
            "term": "Hero",
            "recommended": "Герой",
            "renderings": [{"uk": "Герой", "source": "G1"}],
        }],
    }
    src = tmp_path / "src.json"
    src.write_text(json.dumps(series_doc), encoding="utf-8")

    target_dir = tmp_path / "out"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "src.json"
    target_file.write_bytes(b"EXISTING_GLOSSARY")

    job = GroupGlossaryFileJob("link", src, target_dir=target_dir, overwrite=True)

    interrupted = False
    monkeypatch.setattr(job, "isInterruptionRequested", lambda: interrupted)

    import ui.project_manager.group_glossary as gg_mod
    orig_fn = gg_mod.import_series_glossary

    def interrupt_after_conversion(source, target):
        nonlocal interrupted
        orig_fn(source, target)
        interrupted = True

    monkeypatch.setattr(gg_mod, "import_series_glossary", interrupt_after_conversion)

    def fail_restore(path, data):
        raise OSError("Simulated disk error during atomic restore")

    monkeypatch.setattr(gg_mod, "atomic_write_bytes", fail_restore)

    failed_messages = []
    job.failed.connect(failed_messages.append)
    job.run()

    # Restoration error is NOT swallowed; reports failure and includes affected path
    assert len(failed_messages) == 1
    assert str(target_file.resolve()) in failed_messages[0] or str(target_file) in failed_messages[0]


def test_update_project_group_glossary_invalid_json_fails_closed(tmp_path: Path) -> None:
    p_file = tmp_path / "broken.uiproj"
    raw_content = "NOT_VALID_JSON{{"
    p_file.write_text(raw_content, encoding="utf-8")

    with pytest.raises(OSError, match="Could not read project file"):
        update_project_group_glossary(p_file, "glossary.json")

    assert p_file.read_text(encoding="utf-8") == raw_content


def test_update_project_group_glossary_invalid_structure_fails_closed(tmp_path: Path) -> None:
    p_file = tmp_path / "list_proj.uiproj"
    p_file.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="not a JSON object"):
        update_project_group_glossary(p_file, "glossary.json")

    p_meta = tmp_path / "bad_meta.uiproj"
    p_meta.write_text('{"metadata": "not_a_dict"}', encoding="utf-8")

    with pytest.raises(ValueError, match="metadata is not a JSON object"):
        update_project_group_glossary(p_meta, "glossary.json")


def test_sync_job_invalid_project_fails_safely(tmp_path: Path) -> None:
    p_file = tmp_path / "broken.uiproj"
    p_file.write_text("INVALID_JSON", encoding="utf-8")

    job = OpenProjectSyncJob(p_file, "glossary.json", [])
    failed_reasons = []
    job.failed.connect(failed_reasons.append)
    job.run()

    assert not job.committed
    assert len(failed_reasons) == 1
    assert "Could not read project file" in failed_reasons[0]
