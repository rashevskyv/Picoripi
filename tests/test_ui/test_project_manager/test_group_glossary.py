"""Tests for Project Manager virtual group shared glossary management:
persistence, effective series chain, moves, unlinking, deletion, open project protection,
worker jobs, and UI header integration.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from core.glossary.series import (
    GROUP_METADATA_KEY,
    METADATA_KEY,
    group_series_paths,
    series_chain,
    set_group_series_link,
    set_series_links,
)
from core.project_library import registry, series_facts
from core.project_models import Project
from ui.project_manager.group_glossary import (
    GroupGlossaryFileJob,
    apply_folder_glossary_mutation,
)
from ui.project_manager.window import (
    ProjectManagerDialog,
    _op_delete_folder,
    _op_import,
    _op_move,
    _op_remove,
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
            "metadata": metadata or {},
            "blocks": [],
        }),
        encoding="utf-8",
    )
    return p_file


def _make_glossary_file(path: Path, terms: list[dict] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = terms if terms is not None else [{"original": "Test", "translation": "Тест"}]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def test_registry_folder_glossary_crud_and_persistence(tmp_path: Path) -> None:
    glossary_a = _make_glossary_file(tmp_path / "shared" / "alpha.json")
    glossary_b = _make_glossary_file(tmp_path / "shared" / "beta.json")

    reg = registry.Registry(registry.read(tmp_path))
    fid = reg.create_folder("RPGs", glossary_path=str(glossary_a))
    assert reg.folder_glossary(fid) == str(glossary_a.resolve())

    folders = reg.folders()
    assert len(folders) == 1
    assert folders[0]["id"] == fid
    assert folders[0]["glossary_path"] == str(glossary_a.resolve())

    # Mutate through registry.mutate and reload from disk
    registry.mutate(
        tmp_path,
        lambda r: r.create_folder("RPGs", glossary_path=str(glossary_a)),
    )
    reloaded_folders = registry.Registry(registry.read(tmp_path)).folders()
    created_fid = reloaded_folders[0]["id"]

    registry.mutate(
        tmp_path,
        lambda r: r.set_folder_glossary(created_fid, str(glossary_b)),
    )
    reloaded = registry.Registry(registry.read(tmp_path))
    assert reloaded.folder_glossary(created_fid) == str(glossary_b.resolve())

    # Unlink glossary
    registry.mutate(tmp_path, lambda r: r.set_folder_glossary(created_fid, None))
    reloaded_unlinked = registry.Registry(registry.read(tmp_path))
    assert reloaded_unlinked.folder_glossary(created_fid) is None


def test_effective_series_chain_precedence_and_deduplication(tmp_path: Path) -> None:
    group_glossary = _make_glossary_file(tmp_path / "group" / "glossary.json")
    personal_glossary = _make_glossary_file(tmp_path / "personal" / "glossary.json")
    ancestor_glossary = _make_glossary_file(tmp_path / "Series" / "_glossary" / "glossary.json")

    proj_dir = tmp_path / "Series" / "GameA" / "picoripi"
    proj_dir.mkdir(parents=True, exist_ok=True)
    project = Project(name="GameA")

    # Group glossary only
    set_group_series_link(project, group_glossary)
    assert group_series_paths(project) == [group_glossary.resolve()]
    chain = series_chain(project, proj_dir)
    assert chain == [group_glossary.resolve(), ancestor_glossary.resolve()]

    # Personal explicit link takes precedence over group glossary
    set_series_links(project, [personal_glossary])
    chain = series_chain(project, proj_dir)
    assert chain == [personal_glossary.resolve(), group_glossary.resolve(), ancestor_glossary.resolve()]

    # If personal link points to the same file as group glossary, no duplication
    set_series_links(project, [group_glossary])
    chain = series_chain(project, proj_dir)
    assert chain == [group_glossary.resolve(), ancestor_glossary.resolve()]

    # Path normalization regression test:
    # An explicit path with ../ and the group's absolute path to the same file must be deduplicated
    relative_same = tmp_path / "group" / "subdir" / ".." / "glossary.json"
    set_series_links(project, [relative_same])
    set_group_series_link(project, group_glossary.resolve())
    chain_normalized = series_chain(project, proj_dir)
    assert len([p for p in chain_normalized if p.resolve() == group_glossary.resolve()]) == 1
    # Personal link storage preserves the user's path string representation
    assert str(relative_same) in str(project.metadata[METADATA_KEY])

    # Facts link label
    p_file = _make_project_file(
        tmp_path / "Series",
        "GameA",
        metadata={GROUP_METADATA_KEY: str(group_glossary.resolve())},
    )
    facts_group = series_facts.series_facts(str(p_file))
    assert facts_group["link"] == "group"

    # When personal link is added, link label becomes 'linked'
    p_file.write_text(
        json.dumps({
            "id": "GameA",
            "name": "GameA",
            "plugin_name": "plain_text",
            "metadata": {
                GROUP_METADATA_KEY: str(group_glossary.resolve()),
                METADATA_KEY: str(personal_glossary.resolve()),
            },
        }),
        encoding="utf-8",
    )
    facts_personal = series_facts.series_facts(str(p_file))
    assert facts_personal["link"] == "linked"


def test_project_move_updates_group_glossary_and_preserves_personal_links(tmp_path: Path) -> None:
    glossary_a = _make_glossary_file(tmp_path / "glossaries" / "a.json")
    glossary_b = _make_glossary_file(tmp_path / "glossaries" / "b.json")
    personal = _make_glossary_file(tmp_path / "glossaries" / "personal.json")

    p1_file = _make_project_file(
        tmp_path / "projects",
        "Game1",
        metadata={METADATA_KEY: str(personal.resolve())},
    )

    reg = registry.Registry(registry.read(tmp_path))
    reg.add(str(p1_file))
    fid_a = reg.create_folder("Folder A", glossary_path=str(glossary_a))
    fid_b = reg.create_folder("Folder B", glossary_path=str(glossary_b))

    # Move into Folder A
    _op_move(reg, str(p1_file), fid_a)
    data = json.loads(p1_file.read_text(encoding="utf-8"))
    assert data["metadata"][GROUP_METADATA_KEY] == str(glossary_a.resolve())
    assert data["metadata"][METADATA_KEY] == str(personal.resolve())

    # Move to Folder B
    _op_move(reg, str(p1_file), fid_b)
    data = json.loads(p1_file.read_text(encoding="utf-8"))
    assert data["metadata"][GROUP_METADATA_KEY] == str(glossary_b.resolve())
    assert data["metadata"][METADATA_KEY] == str(personal.resolve())

    # Move to root (no folder)
    _op_move(reg, str(p1_file), None)
    data = json.loads(p1_file.read_text(encoding="utf-8"))
    assert GROUP_METADATA_KEY not in data["metadata"]
    assert data["metadata"][METADATA_KEY] == str(personal.resolve())


def test_folder_unlinking_and_deletion_updates_projects_and_preserves_files(tmp_path: Path) -> None:
    glossary = _make_glossary_file(tmp_path / "glossaries" / "shared.json")
    p1_file = _make_project_file(tmp_path / "projects", "Game1")
    p2_file = _make_project_file(tmp_path / "projects", "Game2")

    reg = registry.Registry(registry.read(tmp_path))
    reg.add(str(p1_file))
    reg.add(str(p2_file))
    fid = reg.create_folder("Series Folder", glossary_path=str(glossary))
    _op_move(reg, str(p1_file), fid)
    _op_move(reg, str(p2_file), fid)

    assert json.loads(p1_file.read_text(encoding="utf-8"))["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())
    assert json.loads(p2_file.read_text(encoding="utf-8"))["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())

    # Unlink glossary from folder
    _op_set_folder_glossary(reg, fid, None)
    assert reg.folder_glossary(fid) is None
    assert GROUP_METADATA_KEY not in json.loads(p1_file.read_text(encoding="utf-8"))["metadata"]
    assert GROUP_METADATA_KEY not in json.loads(p2_file.read_text(encoding="utf-8"))["metadata"]
    assert glossary.exists()

    # Re-link and then delete folder
    _op_set_folder_glossary(reg, fid, str(glossary))
    assert json.loads(p1_file.read_text(encoding="utf-8"))["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())

    _op_delete_folder(reg, fid)
    assert any(f["id"] == fid for f in reg.folders()) is False
    assert GROUP_METADATA_KEY not in json.loads(p1_file.read_text(encoding="utf-8"))["metadata"]
    assert GROUP_METADATA_KEY not in json.loads(p2_file.read_text(encoding="utf-8"))["metadata"]
    assert glossary.exists()


def test_open_project_protection_against_stale_disk_overwrite(tmp_path: Path) -> None:
    glossary = _make_glossary_file(tmp_path / "glossaries" / "shared.json")
    p_open = _make_project_file(tmp_path / "projects", "OpenGame")
    p_closed = _make_project_file(tmp_path / "projects", "ClosedGame")

    reg = registry.Registry(registry.read(tmp_path))
    reg.add(str(p_open))
    reg.add(str(p_closed))
    fid = reg.create_folder("Active", glossary_path=None)
    reg.update_fields(str(p_open), folder_id=fid)
    reg.update_fields(str(p_closed), folder_id=fid)

    # Simulate unsaved edits in memory
    unsaved_p_open_text = p_open.read_text(encoding="utf-8")
    updated = apply_folder_glossary_mutation(reg, fid, str(glossary), open_project_file=str(p_open))

    # Closed project was updated on disk; open project was skipped
    assert str(p_closed) in updated
    assert str(p_open) not in updated
    assert p_open.read_text(encoding="utf-8") == unsaved_p_open_text
    assert json.loads(p_closed.read_text(encoding="utf-8"))["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())


def test_open_project_sync_in_project_manager_window(qtbot, tmp_path: Path) -> None:
    glossary = _make_glossary_file(tmp_path / "glossaries" / "shared.json")
    p_open = _make_project_file(tmp_path / "projects", "OpenGame", metadata={"unsaved_key": "keep_me"})

    def _setup(reg):
        fid = reg.create_folder("Active", glossary_path=str(glossary))
        reg.add(str(p_open), folder_id=fid)
        return fid

    registry.mutate(tmp_path, _setup)

    from PyQt6.QtWidgets import QWidget

    parent_widget = QWidget()
    fake_pm = MagicMock()
    fake_project = Project(name="OpenGame")
    fake_project.metadata["unsaved_key"] = "keep_me"
    fake_pm.project = fake_project
    fake_pm.project_file_path = str(p_open)
    parent_widget.project_manager = fake_pm

    glossary_handler = MagicMock()
    glossary_handler.series_glossary_managers = []
    parent_widget.translation_handler = MagicMock()
    parent_widget.translation_handler.glossary_handler = glossary_handler

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

    # Trigger open project sync
    dialog._sync_open_project_if_needed()
    qtbot.waitUntil(lambda: len(dialog._jobs) == 0, timeout=5000)

    # In-memory state updated and unsaved changes preserved
    assert fake_project.metadata[GROUP_METADATA_KEY] == str(glossary.resolve())
    assert fake_project.metadata["unsaved_key"] == "keep_me"

    # Disk file was atomically persisted by the worker
    saved_data = json.loads(p_open.read_text(encoding="utf-8"))
    assert saved_data["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())
    assert saved_data["metadata"]["unsaved_key"] == "keep_me"

    # Series glossary managers were populated on the handler
    assert len(glossary_handler.series_glossary_managers) == 1
    assert glossary_handler.series_glossary_managers[0].glossary_path == glossary.resolve()


def test_group_glossary_file_job_create(qtbot, tmp_path: Path) -> None:
    target = tmp_path / "new_glossary" / "terms.json"
    job = GroupGlossaryFileJob("create", target)

    results = []
    job.done.connect(results.append)
    with qtbot.waitSignal(job.done, timeout=5000):
        job.start()

    assert len(results) == 1
    assert Path(results[0]).resolve() == target.resolve()
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8")) == []


def test_group_glossary_file_job_link_and_conversion(qtbot, tmp_path: Path) -> None:
    # 1. Plain list glossary
    plain = _make_glossary_file(tmp_path / "plain.json", [{"original": "Sword", "translation": "Меч"}])
    job_plain = GroupGlossaryFileJob("link", plain)
    results_plain = []
    job_plain.done.connect(results_plain.append)
    with qtbot.waitSignal(job_plain.done, timeout=5000):
        job_plain.start()
    assert results_plain[0] == str(plain.resolve())

    # 2. Series document format: {"terms": [...]}
    series_doc = {
        "generated": "2026-10-19",
        "sources": {"G1": "Game 1"},
        "terms": [{
            "term": "Shield",
            "category": "Item",
            "renderings": [{"source": "G1", "uk": "Щит", "forms": ["Щит"]}],
            "recommended": "Щит",
            "status": "agreed",
        }],
    }
    series_file = tmp_path / "series_src.json"
    series_file.write_text(json.dumps(series_doc), encoding="utf-8")

    target_dir = tmp_path / "converted_series"
    job_series = GroupGlossaryFileJob("link", series_file, target_dir=target_dir)
    results_series = []
    job_series.done.connect(results_series.append)
    with qtbot.waitSignal(job_series.done, timeout=5000):
        job_series.start()

    converted = Path(results_series[0])
    assert converted.is_file()
    assert converted.parent == target_dir.resolve()
    assert "Shield" in converted.read_text(encoding="utf-8")


def test_group_glossary_file_job_failure_modes(qtbot, tmp_path: Path) -> None:
    # Missing file
    job_missing = GroupGlossaryFileJob("link", tmp_path / "non_existent.json")
    failures = []
    job_missing.failed.connect(failures.append)
    with qtbot.waitSignal(job_missing.failed, timeout=5000):
        job_missing.start()
    assert len(failures) == 1
    assert "non_existent.json" in failures[0]

    # Corrupted / invalid JSON content
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{invalid json", encoding="utf-8")
    job_corrupt = GroupGlossaryFileJob("link", corrupt)
    failures_corrupt = []
    job_corrupt.failed.connect(failures_corrupt.append)
    with qtbot.waitSignal(job_corrupt.failed, timeout=5000):
        job_corrupt.start()
    assert len(failures_corrupt) == 1

    # Invalid glossary schema (e.g. integer)
    invalid_schema = tmp_path / "schema.json"
    invalid_schema.write_text("12345", encoding="utf-8")
    job_schema = GroupGlossaryFileJob("link", invalid_schema)
    failures_schema = []
    job_schema.failed.connect(failures_schema.append)
    with qtbot.waitSignal(job_schema.failed, timeout=5000):
        job_schema.start()
    assert len(failures_schema) == 1


def test_project_manager_ui_group_header_and_tooltip(qtbot, tmp_path: Path) -> None:
    glossary = _make_glossary_file(tmp_path / "glossaries" / "zelda.json")
    p1_file = _make_project_file(tmp_path / "projects", "Zelda1")

    folder_id_box = []

    def _setup(reg):
        fid = reg.create_folder("Zelda Series", glossary_path=str(glossary))
        folder_id_box.append(fid)
        reg.add(str(p1_file), folder_id=fid)

    registry.mutate(tmp_path, _setup)
    fid = folder_id_box[0]

    dialog = ProjectManagerDialog(
        None,
        str(tmp_path),
        lambda path: None,
        lambda: None,
        lambda p, u: None,
        lambda n, v: None,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: len(dialog._headers) >= 1, timeout=5000)

    header = dialog._headers.get(("folder", fid))
    assert header is not None
    label_text = header.text(0)
    assert "Zelda Series" in label_text
    assert "Glossary: zelda" in label_text
    assert str(glossary.resolve()) in header.toolTip(0)


def test_move_and_delete_folder_skip_a_missing_project_file(tmp_path: Path) -> None:
    glossary = _make_glossary_file(tmp_path / "glossaries" / "shared.json")
    present = _make_project_file(tmp_path / "projects", "Present")
    missing = tmp_path / "projects" / "Gone" / "picoripi" / "project.uiproj"

    reg = registry.Registry(registry.read(tmp_path))
    reg.add(str(present))
    reg.add(str(missing))
    plain = reg.create_folder("Plain")
    shared = reg.create_folder("Shared", glossary_path=str(glossary))

    _op_move(reg, str(missing), plain)
    _op_move(reg, str(missing), shared)
    _op_move(reg, str(present), shared)
    assert {p["path"]: p["folder_id"] for p in reg.document["projects"]} == {str(present): shared, str(missing): shared}
    assert not missing.exists()

    _op_delete_folder(reg, shared)
    assert all(p.get("folder_id") is None for p in reg.document["projects"])
    assert GROUP_METADATA_KEY not in json.loads(present.read_text(encoding="utf-8"))["metadata"]

    reg.remove(str(missing))
    reg.create_folder("Imported", glossary_path=str(glossary))
    _op_import(reg, [{"project_file": str(missing), "series": "Imported"}])
    assert any(p["path"] == str(missing) for p in reg.document["projects"])


def test_remove_clears_the_group_glossary_and_rolls_back(tmp_path: Path) -> None:
    glossary = _make_glossary_file(tmp_path / "glossaries" / "shared.json")
    personal = _make_glossary_file(tmp_path / "glossaries" / "personal.json")
    p_file = _make_project_file(
        tmp_path / "projects", "Game",
        metadata={GROUP_METADATA_KEY: str(glossary.resolve()), METADATA_KEY: str(personal.resolve())},
    )
    reg = registry.Registry(registry.read(tmp_path))
    fid = reg.create_folder("Shared", glossary_path=str(glossary))
    reg.add(str(p_file), folder_id=fid)

    rollback = _op_remove(reg, str(p_file))
    metadata = json.loads(p_file.read_text(encoding="utf-8"))["metadata"]
    assert reg.document["projects"] == []
    assert GROUP_METADATA_KEY not in metadata
    assert metadata[METADATA_KEY] == str(personal.resolve())
    assert series_chain(Project(name="Game", metadata=metadata), None) == [personal.resolve()]

    rollback()
    assert json.loads(p_file.read_text(encoding="utf-8"))["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())


def test_remove_leaves_the_open_project_file_to_the_sync_job(tmp_path: Path) -> None:
    glossary = _make_glossary_file(tmp_path / "glossaries" / "shared.json")
    p_file = _make_project_file(tmp_path / "projects", "Game", metadata={GROUP_METADATA_KEY: str(glossary.resolve())})
    reg = registry.Registry(registry.read(tmp_path))
    reg.add(str(p_file))

    _op_remove(reg, str(p_file), open_file=str(p_file))
    assert json.loads(p_file.read_text(encoding="utf-8"))["metadata"][GROUP_METADATA_KEY] == str(glossary.resolve())
