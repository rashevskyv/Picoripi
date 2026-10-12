"""The mhp3rd project shape loads through the host project loader and gives every string (synthetic data)."""
import json
import uuid

from core.project_manager import ProjectManager
from core.project_models import Project
from handlers.project_action.load_worker import ProjectLoadWorker
from plugins.mhp3rd.rules import GameRules

SOURCE = {
    "16": {"2:20": "Cancel", "2:21": "Yes", "2:60": "~B03Switch Equipment"},
    "4289": {"0:0": "Hello\nhunter.", "1:0": "Second dialogue"},
}


def _project_dict(source_dir, translation_dir):
    """The shape of picoripi/project.uiproj in the workspace: one block per JSON block, internal_key = name."""
    names = list(SOURCE)
    return {
        "id": str(uuid.uuid4()),
        "name": "MHP3rd test",
        "description": "",
        "plugin_name": "mhp3rd",
        "blocks": [{
            "id": str(uuid.uuid4()),
            "name": name,
            "source_file": "en_source.json",
            "translation_file": "uk.json",
            "internal_key": name,
            "description": "",
            "categories": [],
            "metadata": {},
            "last_selected_string_idx": 0,
        } for name in names],
        "metadata": {
            "source_path": str(source_dir),
            "translation_path": str(translation_dir),
            "is_directory_mode": True,
            "auto_create_translations": False,
            "root_block_ids": [],
        },
        "version": "1.1",
    }


def test_the_real_project_shape_loads_every_block_with_its_strings(tmp_path):
    source_dir = tmp_path / "source"
    translation_dir = tmp_path / "translation"
    source_dir.mkdir()
    translation_dir.mkdir()
    (source_dir / "en_source.json").write_text(json.dumps(SOURCE), encoding="utf-8")
    (translation_dir / "uk.json").write_text(json.dumps(SOURCE), encoding="utf-8")

    manager = ProjectManager()
    manager.project_dir = str(tmp_path)
    manager.project_file_path = str(tmp_path / "project.uiproj")
    manager.project = Project.from_dict(_project_dict(source_dir, translation_dir))

    rules = GameRules()
    results = []
    worker = ProjectLoadWorker(manager, rules)
    worker.finished_with_result.connect(results.append)
    worker.run()

    loaded = results[0]
    counts = [len(block) for block in loaded["data"]]
    assert counts == [3, 2]
    assert [loaded["block_names"][str(i)] for i in range(2)] == ["16", "4289"]
    assert loaded["data"][0][0] == "Cancel"
    assert loaded["data"][1][1] == "Second dialogue"
