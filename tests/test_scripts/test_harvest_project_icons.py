"""The icon harvester writes the Project Manager's icon.png: one writer, native size, no temporary file left."""
import json
from pathlib import Path

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


def test_a_folder_that_cannot_be_written_is_reported_and_the_batch_goes_on(tmp_path, monkeypatch, capsys):
    registry = tmp_path / "project_manager.json"
    projects = []
    for name in ("Locked", "Open"):
        uiproj = tmp_path / name / "picoripi" / "project.uiproj"
        uiproj.parent.mkdir(parents=True)
        uiproj.write_text("{}", encoding="utf-8")
        projects.append({"path": str(uiproj)})
    registry.write_text(json.dumps({"projects": projects}), encoding="utf-8")
    written = []

    def fake_write(icon, target):
        if Path(target).parent.parent.name == "Locked":
            raise OSError("read-only folder")
        written.append(target)

    picture = Image.new("RGBA", (48, 48), (0, 0, 255, 255))
    monkeypatch.setattr(harvest, "harvest_one",
                        lambda folder: (Icon("3ds-smdh", picture, "icon.bin"), "icon.bin", "3ds-smdh", []))
    monkeypatch.setattr(harvest, "write_icon", fake_write)

    assert harvest.main(["--registry", str(registry), "--apply"]) == 0

    assert "error: read-only folder" in capsys.readouterr().out
    assert len(written) == 1 and Path(written[0]).parent.parent.name == "Open"


def test_registry_entry_maps_to_the_icon_beside_project_uiproj(tmp_path):
    uiproj = tmp_path / "Game" / "picoripi" / "project.uiproj"
    registry = tmp_path / "project_manager.json"
    registry.write_text(json.dumps({"projects": [{"path": str(uiproj)}]}), encoding="utf-8")

    pairs = harvest.load_projects(str(registry), None)

    assert pairs == [(str(tmp_path / "Game"), str(uiproj.parent / "icon.png"))]
