"""The icon harvester writes the Project Manager's icon.png: one writer, native size, no temporary file left."""
import json

from PIL import Image

from core.game_icons import Icon
from scripts import harvest_project_icons as harvest


def test_write_icon_keeps_native_size_and_leaves_only_the_png(tmp_path):
    target = tmp_path / "picoripi" / "icon.png"
    target.parent.mkdir()
    picture = Image.new("RGBA", (48, 48), (255, 0, 0, 255))

    harvest.write_icon(Icon("3ds-smdh", picture, "icon.bin"), str(target))

    with Image.open(target) as written:
        assert written.size == (48, 48)
    assert [p.name for p in target.parent.iterdir()] == ["icon.png"]


def test_registry_entry_maps_to_the_icon_beside_project_uiproj(tmp_path):
    uiproj = tmp_path / "Game" / "picoripi" / "project.uiproj"
    registry = tmp_path / "project_manager.json"
    registry.write_text(json.dumps({"projects": [{"path": str(uiproj)}]}), encoding="utf-8")

    pairs = harvest.load_projects(str(registry), None)

    assert pairs == [(str(tmp_path / "Game"), str(uiproj.parent / "icon.png"))]
