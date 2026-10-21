"""The sample project shared by the Vagrant Story tests: a disc folder written from the synthetic samples."""
import json
from types import SimpleNamespace

import pytest

from plugins.testing import load_rules

from .samples import area_file, event_file, item_names, program_file, room_file


@pytest.fixture
def project(tmp_path):
    files = {"EVENT/0004.EVT": event_file(["Don't move, Sydney!", "Bind your legs\nwith that rope."],
                                          boxes=((13, 3), (14, 4))),
             "MAP/MAP001.MPD": room_file(["Have you found Sydney?"]),
             "MENU/ITEMNAME.BIN": item_names(["Battle Knife", "Dirk"]),
             "SMALL/SCEN001.ARM": area_file([(9, 1, "Entrance to Darkness")]),
             "SLUS_010.40": program_file(["Fireball", "Heal Panel"], ["Check the container?", "Yes", "No"])}
    for rel, data in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(data)
    (tmp_path / "vs_index.json").write_text(json.dumps(
        {"rooms": {"MAP/MAP001.MPD": {"zone": 9, "room_number": 1, "area": "Wine Cellar", "room": "The Gallows"}}}),
        encoding="utf-8")
    rel_paths = list(files)
    block_map = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 4}
    manager = SimpleNamespace(project=SimpleNamespace(blocks=[SimpleNamespace(source_file=f) for f in rel_paths]),
                              project_dir=None,
                              get_absolute_path=lambda rel, is_translation=False: str(tmp_path / rel))
    mw = SimpleNamespace(project_manager=manager, block_to_project_file_map=block_map, font_map={},
                         data_store=SimpleNamespace(data=None))
    rules = load_rules("vagrant_story", mw)
    for rel in rel_paths:
        rules.load_data_from_json_obj(files[rel])
    return rules
