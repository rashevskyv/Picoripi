"""The import script reports the Git state of the data folder; --apply writes the self-ignoring .gitignore before anything else."""
import shutil
import subprocess

import pytest

from scripts import import_projects_to_data_folder as script
from utils import data_folder_git as dfg

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git on PATH")


def test_a_dry_run_reports_the_repository_and_writes_no_gitignore(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PICORIPI_HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    root = tmp_path / "games"
    root.mkdir()
    data = repo / "data"

    assert script.main(["--root", str(root), "--data-dir", str(data)]) == 0

    out = capsys.readouterr().out
    assert "NOT ignored" in out
    assert "missing, --apply writes it" in out
    assert not (data / ".gitignore").exists()


def test_apply_writes_the_self_ignoring_gitignore_into_the_data_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PICORIPI_HOME", str(tmp_path / "home"))
    root = tmp_path / "games"
    root.mkdir()
    data = tmp_path / "data"

    assert script.main(["--root", str(root), "--data-dir", str(data), "--apply"]) == 0

    assert dfg.has_self_ignore(data)
    assert "Gitignore   : written" in capsys.readouterr().out


def test_a_second_apply_keeps_the_existing_gitignore(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PICORIPI_HOME", str(tmp_path / "home"))
    root = tmp_path / "games"
    root.mkdir()
    data = tmp_path / "data"
    script.main(["--root", str(root), "--data-dir", str(data), "--apply"])
    before = (data / ".gitignore").read_bytes()

    script.main(["--root", str(root), "--data-dir", str(data), "--apply"])

    assert (data / ".gitignore").read_bytes() == before
    assert "present" in capsys.readouterr().out
