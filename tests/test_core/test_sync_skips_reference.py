"""Directory scan: reference files under ``source/reference`` (or ``reference_patch_path``) never become blocks."""
import json

from core.project_manager import ProjectManager
from core.project_models import Project


def _manager(tmp_path, existing=()):
    source = tmp_path / "src"
    (source / "reference").mkdir(parents=True)
    (source / "dialog.json").write_text("{}", encoding="utf-8")
    (source / "reference" / "ua_gb.json").write_text("{}", encoding="utf-8")
    (source / "elsewhere").mkdir()
    (source / "elsewhere" / "ru.json").write_text("{}", encoding="utf-8")
    manager = ProjectManager()
    manager.project_dir = str(tmp_path)
    manager.project_file_path = str(tmp_path / "project.uiproj")
    manager.project = Project(name="Demo", plugin_name="demo")
    manager.project.metadata = {"source_path": str(source), "translation_path": str(tmp_path / "trans"),
                                "is_directory_mode": True}
    for name in existing:
        manager.add_block(name=name, source_file_path=name, translation_file_path=name)
    return manager


def _sources(manager):
    return sorted(block.source_file for block in manager.project.blocks)


def test_reference_folder_is_not_scanned(tmp_path):
    manager = _manager(tmp_path)

    manager.sync_project_files()

    assert _sources(manager) == ["dialog.json", "elsewhere/ru.json"]


def test_reference_patch_path_inside_source_is_not_scanned(tmp_path):
    manager = _manager(tmp_path)
    (tmp_path / "project_settings.json").write_text(
        json.dumps({"reference_patch_path": str(tmp_path / "src" / "elsewhere")}), encoding="utf-8")

    manager.sync_project_files()

    assert _sources(manager) == ["dialog.json"]


def test_project_that_already_has_blocks_in_reference_keeps_scanning_it(tmp_path):
    manager = _manager(tmp_path, existing=["reference/ua_gb.json"])

    manager.sync_project_files()

    assert _sources(manager) == ["dialog.json", "elsewhere/ru.json", "reference/ua_gb.json"]
