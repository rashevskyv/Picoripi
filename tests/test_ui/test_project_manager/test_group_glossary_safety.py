"""Safety, collision protection, rollback, and async persistence tests for Project Manager group shared glossaries."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QWidget

from core.glossary.series import GROUP_METADATA_KEY
from core.project_library import registry
from core.project_models import Project
from ui.project_manager.group_glossary import (
    GroupGlossaryFileJob,
    apply_folder_glossary_mutation,
    update_project_group_glossary,
)
from ui.project_manager.window import (
    ProjectManagerDialog,
    _op_import,
    _op_set_folder_glossary,
)


def _make_project_file(folder: Path, name: str, metadata: dict | None = None) -> Path:
    picoripi = folder / name / "picoripi"
    picoripi.mkdir(parents=True, exist_ok=True)
    p_file = picoripi / "project.uiproj"
    p_file.write_text(
        json.dumps({
            "id": name,
            "name": name,
            "plugin_name": "plain_text",
            "metadata": metadata if metadata is not None else {},
            "blocks": [],
        }),
        encoding="utf-8",
    )
    return p_file


def _make_series_doc(path: Path) -> Path:
    doc = {
        "generated": "2026-10-19",
        "sources": {"G1": "Game 1"},
        "terms": [{
            "term": "Master Sword",
            "category": "Weapon",
            "renderings": [{"source": "G1", "uk": "Вищий меч", "forms": ["Вищий меч"]}],
            "recommended": "Вищий меч",
            "status": "agreed",
        }],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_link_collision_fails_without_overwrite_and_preserves_bytes(qtbot, tmp_path: Path) -> None:
    target_dir = tmp_path / "glossaries"
    target_dir.mkdir(parents=True, exist_ok=True)
    existing_target = target_dir / "zelda.json"
    existing_target.write_text('[{"original": "Old", "translation": "Старе"}]', encoding="utf-8")

    source_series = _make_series_doc(tmp_path / "incoming" / "zelda.json")

    job = GroupGlossaryFileJob("link", source_series, target_dir=target_dir, overwrite=False, collision_free=False)
    failures = []
    job.failed.connect(failures.append)
    with qtbot.waitSignal(job.failed, timeout=5000):
        job.start()

    assert len(failures) == 1
    assert "already exists" in failures[0]
    # Existing target bytes preserved
    assert json.loads(existing_target.read_text(encoding="utf-8")) == [{"original": "Old", "translation": "Старе"}]


def test_link_collision_succeeds_with_collision_free(qtbot, tmp_path: Path) -> None:
    target_dir = tmp_path / "glossaries"
    target_dir.mkdir(parents=True, exist_ok=True)
    existing_target = target_dir / "zelda.json"
    existing_target.write_text('[{"original": "Old", "translation": "Старе"}]', encoding="utf-8")

    source_series = _make_series_doc(tmp_path / "incoming" / "zelda.json")

    job = GroupGlossaryFileJob("link", source_series, target_dir=target_dir, collision_free=True)
    results = []
    job.done.connect(results.append)
    with qtbot.waitSignal(job.done, timeout=5000):
        job.start()

    assert len(results) == 1
    assert Path(results[0]).name == "zelda_1.json"
    assert "Master Sword" in Path(results[0]).read_text(encoding="utf-8")
    # Original target unchanged
    assert json.loads(existing_target.read_text(encoding="utf-8")) == [{"original": "Old", "translation": "Старе"}]


def test_link_source_equals_destination_protects_source(qtbot, tmp_path: Path) -> None:
    target_dir = tmp_path / "glossaries"
    target_dir.mkdir(parents=True, exist_ok=True)
    source_in_target = _make_series_doc(target_dir / "pokemon.json")

    # Without collision_free, fails with FileExistsError protecting the source file
    job_safe = GroupGlossaryFileJob("link", source_in_target, target_dir=target_dir, collision_free=False)
    failures = []
    job_safe.failed.connect(failures.append)
    with qtbot.waitSignal(job_safe.failed, timeout=5000):
        job_safe.start()

    assert len(failures) == 1
    assert "source file itself" in failures[0]
    # Source file is intact as series format
    assert "sources" in json.loads(source_in_target.read_text(encoding="utf-8"))

    # With collision_free, writes to pokemon_1.json without touching pokemon.json
    job_cf = GroupGlossaryFileJob("link", source_in_target, target_dir=target_dir, collision_free=True)
    results = []
    job_cf.done.connect(results.append)
    with qtbot.waitSignal(job_cf.done, timeout=5000):
        job_cf.start()

    assert Path(results[0]).name == "pokemon_1.json"
    assert "sources" in json.loads(source_in_target.read_text(encoding="utf-8"))


def test_group_glossary_file_job_cancellation_preserves_bytes(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "cancelled" / "terms.json"
    job = GroupGlossaryFileJob("create", target)

    cancelled_signals = []
    job.cancelled.connect(lambda: cancelled_signals.append(True))

    monkeypatch.setattr(job, "isInterruptionRequested", lambda: True)
    job.run()

    assert len(cancelled_signals) == 1
    assert not target.exists()


def test_update_project_group_glossary_semantics_and_validation(tmp_path: Path) -> None:
    glossary = tmp_path / "gloss.json"
    glossary.write_text("[]", encoding="utf-8")

    p_file = _make_project_file(tmp_path, "Game1")

    # 1. Update from none to glossary -> True (changed)
    assert update_project_group_glossary(p_file, glossary) is True
    assert json.loads(p_file.read_text(encoding="utf-8"))["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())

    # 2. Update with same path -> False (unchanged)
    assert update_project_group_glossary(p_file, glossary) is False

    # 3. Unlink -> True (changed)
    assert update_project_group_glossary(p_file, None) is True
    assert GROUP_METADATA_KEY not in json.loads(p_file.read_text(encoding="utf-8"))["metadata"]

    # 4. Unlink when already none -> False (unchanged)
    assert update_project_group_glossary(p_file, None) is False

    # 5. Non-existent file raises FileNotFoundError
    import pytest
    with pytest.raises(FileNotFoundError):
        update_project_group_glossary(tmp_path / "missing.uiproj", glossary)

    # 6. Malformed metadata (e.g. metadata is a string or list) raises ValueError
    bad_p_file = tmp_path / "bad.uiproj"
    bad_p_file.write_text(json.dumps({"id": "bad", "metadata": "not_a_dict"}), encoding="utf-8")
    with pytest.raises(ValueError, match="metadata is not a JSON object"):
        update_project_group_glossary(bad_p_file, glossary)


def test_partial_operation_failure_and_rollback(tmp_path: Path) -> None:
    glossary = tmp_path / "gloss.json"
    glossary.write_text("[]", encoding="utf-8")

    p1 = _make_project_file(tmp_path / "p1", "G1")
    p2 = tmp_path / "p2" / "G2" / "picoripi" / "project.uiproj"
    # p2 does not exist, so writing to it will fail

    reg = registry.Registry(registry.read(tmp_path))
    fid = reg.create_folder("RPGs")
    reg.add(str(p1), folder_id=fid)
    reg.add(str(p2), folder_id=fid)

    import pytest
    with pytest.raises(OSError, match=r"Failed to apply group glossary mutation on .*project\.uiproj"):
        apply_folder_glossary_mutation(reg, fid, str(glossary))

    # Rollback: p1 had no group glossary initially and must still have none
    data1 = json.loads(p1.read_text(encoding="utf-8"))
    assert GROUP_METADATA_KEY not in data1["metadata"]


def test_registry_write_failure_rolls_back_projects_on_disk(tmp_path: Path, monkeypatch) -> None:
    glossary = tmp_path / "gloss.json"
    glossary.write_text("[]", encoding="utf-8")

    p1 = _make_project_file(tmp_path / "p1", "G1")

    # Persist setup through registry.mutate
    created_folder = []

    def _setup(r):
        fid = r.create_folder("RPGs")
        r.add(str(p1), folder_id=fid)
        created_folder.append(fid)

    registry.mutate(tmp_path, _setup)
    assert len(created_folder) == 1
    fid = created_folder[0]

    # Verify setup persisted
    doc_after_setup = registry.read(tmp_path)
    assert any(f["id"] == fid for f in doc_after_setup["folders"])
    assert any(p["path"] == str(p1) and p["folder_id"] == fid for p in doc_after_setup["projects"])

    # Mock atomic_write_json to verify mutation occurred before inducing write failure
    orig_write = registry.atomic_write_json
    mutation_occurred_before_fail = []

    def fail_registry_write(path, doc, **kwargs):
        if Path(path).name == registry.REGISTRY_FILE_NAME:
            data_during = json.loads(p1.read_text(encoding="utf-8"))
            if data_during.get("metadata", {}).get(GROUP_METADATA_KEY) == str(glossary.resolve()):
                mutation_occurred_before_fail.append(True)
            raise OSError("Simulated disk write failure on registry")
        return orig_write(path, doc, **kwargs)

    monkeypatch.setattr(registry, "atomic_write_json", fail_registry_write)

    import pytest
    with pytest.raises(OSError, match="Simulated disk write failure"):
        registry.mutate(tmp_path, lambda r: _op_set_folder_glossary(r, fid, str(glossary)))

    # Assert that the project mutation occurred before inducing registry-write failure
    assert len(mutation_occurred_before_fail) == 1

    # Rollback handler executed: p1 does not have the group glossary on disk
    data = json.loads(p1.read_text(encoding="utf-8"))
    assert GROUP_METADATA_KEY not in data["metadata"]


def test_duplicate_import_does_not_change_existing_project_association(tmp_path: Path) -> None:
    glossary_a = tmp_path / "gloss_a.json"
    glossary_b = tmp_path / "gloss_b.json"
    glossary_a.write_text("[]", encoding="utf-8")
    glossary_b.write_text("[]", encoding="utf-8")

    p1 = _make_project_file(tmp_path / "p1", "G1", metadata={GROUP_METADATA_KEY: str(glossary_a.resolve())})

    reg = registry.Registry(registry.read(tmp_path))
    fid_a = reg.create_folder("Series A", glossary_path=str(glossary_a))
    reg.create_folder("Series B", glossary_path=str(glossary_b))
    reg.add(str(p1), folder_id=fid_a)

    # Attempt to import p1 again under Series B
    import_items = [{"project_file": str(p1), "project_id": "G1", "platform": "GBA", "series": "Series B"}]
    _op_import(reg, import_items)

    # Project on disk must still point to Glossary A!
    data = json.loads(p1.read_text(encoding="utf-8"))
    assert data["metadata"][GROUP_METADATA_KEY] == str(glossary_a.resolve())


def test_open_project_sync_job_failure_reverts_in_memory_state(qtbot, tmp_path: Path, monkeypatch) -> None:
    def mock_fail(*args, **kwargs):
        raise OSError("Disk write failed")

    monkeypatch.setattr("ui.project_manager.group_glossary.atomic_write_json", mock_fail)

    glossary = tmp_path / "gloss.json"
    glossary.write_text("[]", encoding="utf-8")

    unwritable_file = tmp_path / "project.uiproj"
    fake_project = Project(name="TestProj")
    fake_project.metadata[GROUP_METADATA_KEY] = "old_glossary.json"

    # Set up mock MainWindow
    parent_widget = QWidget()
    fake_pm = MagicMock()
    fake_pm.project = fake_project
    fake_pm.project_file_path = str(unwritable_file)
    parent_widget.project_manager = fake_pm
    parent_widget.translation_handler = MagicMock()
    parent_widget.translation_handler.glossary_handler = MagicMock()
    parent_widget.translation_handler.glossary_handler.series_glossary_managers = []

    dialog = ProjectManagerDialog(
        parent_widget,
        str(tmp_path),
        lambda path: None,
        lambda: None,
        lambda p, u: None,
        lambda n, v: None,
    )
    qtbot.addWidget(parent_widget)
    qtbot.waitUntil(lambda: dialog._loaded, timeout=5000)

    # Set document to expect new glossary for this project
    dialog._document["folders"] = [{"id": "fid_test", "name": "F", "glossary_path": str(glossary)}]
    dialog._document["projects"] = [{"path": str(unwritable_file), "folder_id": "fid_test"}]

    dialog._sync_open_project_if_needed()
    qtbot.waitUntil(lambda: len(dialog._jobs) == 0, timeout=5000)

    # In-memory metadata was reverted to previous value on failure!
    assert fake_project.metadata[GROUP_METADATA_KEY] == "old_glossary.json"
    assert "Failed to save project" in dialog._status.text()
