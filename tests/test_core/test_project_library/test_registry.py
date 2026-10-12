"""The registry file: add, open, folders, view choices, and what happens to a file it cannot read."""
import json

from core.project_library import registry


def _project_file(tmp_path, name, project_id="id-1"):
    folder = tmp_path / "games" / name / "picoripi"
    folder.mkdir(parents=True)
    project_file = folder / "project.uiproj"
    project_file.write_text(json.dumps({"id": project_id, "name": name, "blocks": []}), encoding="utf-8")
    return str(project_file)


def test_missing_file_reads_as_an_empty_registry(tmp_path):
    document = registry.read(tmp_path)

    assert document["projects"] == [] and document["folders"] == []
    assert document["view"] == registry.DEFAULT_VIEW


def test_added_project_and_folder_survive_a_reload(tmp_path):
    project = _project_file(tmp_path, "Aria")

    def operation(reg):
        folder_id = reg.create_folder("Castlevania")
        reg.add(project, project_id="id-1", platform="DS", folder_id=folder_id)

    registry.mutate(tmp_path, operation)
    document = registry.read(tmp_path)

    assert len(document["projects"]) == 1
    entry = document["projects"][0]
    assert entry["platform"] == "DS" and entry["project_id"] == "id-1"
    assert document["folders"][0]["name"] == "Castlevania"
    assert entry["folder_id"] == document["folders"][0]["id"]


def test_adding_the_same_project_twice_keeps_one_entry(tmp_path):
    project = _project_file(tmp_path, "Aria")

    registry.mutate(tmp_path, lambda reg: reg.add(project))
    registry.mutate(tmp_path, lambda reg: reg.add(project))

    assert len(registry.read(tmp_path)["projects"]) == 1


def test_opening_a_project_sets_last_opened_and_adds_it_when_new(tmp_path):
    project = _project_file(tmp_path, "Aria")

    registry.mutate(tmp_path, lambda reg: reg.touch_opened(project, project_id="id-1"))

    entry = registry.read(tmp_path)["projects"][0]
    assert entry["last_opened"]
    assert entry["added"]


def test_deleting_a_folder_moves_its_projects_to_the_root(tmp_path):
    project = _project_file(tmp_path, "Aria")
    created = {}

    def create_and_move(reg):
        created["folder"] = reg.create_folder("Pokemon")
        reg.add(project, folder_id=created["folder"])

    registry.mutate(tmp_path, create_and_move)
    registry.mutate(tmp_path, lambda reg: reg.delete_folder(created["folder"]))

    document = registry.read(tmp_path)
    assert document["folders"] == []
    assert document["projects"][0]["folder_id"] is None
    assert document["projects"][0]["path"] == project


def test_update_refuses_an_unknown_folder_and_unknown_fields(tmp_path):
    project = _project_file(tmp_path, "Aria")
    registry.mutate(tmp_path, lambda reg: reg.add(project))

    results = {}

    def attempt(reg):
        results["folder"] = reg.update_fields(project, folder_id="no-such-folder")
        results["field"] = reg.update_fields(project, project_id="other")

    registry.mutate(tmp_path, attempt)

    assert results == {"folder": False, "field": False}


def test_unknown_keys_written_by_a_newer_build_are_kept(tmp_path):
    path = registry.registry_path(tmp_path)
    path.write_text(json.dumps({"version": 1, "future_section": {"a": 1}, "projects": [], "folders": []}),
                    encoding="utf-8")

    registry.mutate(tmp_path, lambda reg: reg.create_folder("Kept"))

    assert json.loads(path.read_text(encoding="utf-8"))["future_section"] == {"a": 1}


def test_corrupt_file_is_set_aside_not_overwritten(tmp_path):
    path = registry.registry_path(tmp_path)
    path.write_text("{ not json", encoding="utf-8")

    document = registry.read(tmp_path)

    assert document["projects"] == []
    assert path.with_name(path.name + ".unreadable").read_text(encoding="utf-8") == "{ not json"


def test_newer_schema_is_set_aside(tmp_path):
    path = registry.registry_path(tmp_path)
    path.write_text(json.dumps({"version": registry.SCHEMA_VERSION + 1, "projects": []}), encoding="utf-8")

    registry.read(tmp_path)

    assert not path.exists()
    assert path.with_name(path.name + ".unreadable").exists()
