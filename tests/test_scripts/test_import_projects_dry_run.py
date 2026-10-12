"""The import script's dry run writes nothing, not even by moving an unreadable registry aside."""
from core.project_library import registry
from scripts import import_projects_to_data_folder as script


def test_a_dry_run_does_not_move_a_corrupt_registry(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PICORIPI_HOME", str(tmp_path / "home"))
    root = tmp_path / "games"
    root.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    path = registry.registry_path(data)
    path.write_text("{ corrupt", encoding="utf-8")

    assert script.main(["--root", str(root), "--data-dir", str(data)]) == 0

    assert path.read_text(encoding="utf-8") == "{ corrupt"
    assert not path.with_name(path.name + ".unreadable").exists()
    assert "Dry run: nothing written" in capsys.readouterr().out
