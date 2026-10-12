"""Data folder chooser and Git: a folder in a repository that does not ignore it is asked about; the answer writes the file."""
import shutil
import subprocess

import pytest

from dialogs import data_location_dialog as dld
from utils import data_folder_git as dfg
from utils import data_location as dl

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git on PATH")


@pytest.fixture(autouse=True)
def _search_stops_at_the_temp_folder(tmp_path, monkeypatch):
    """A temp folder can sit inside a git work tree on this machine (the C: root is one): keep the search inside it."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_a_folder_outside_git_gets_the_file_without_a_question(qtbot, tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    dialog = dld.DataLocationDialog(app, first_start=True)
    qtbot.addWidget(dialog)
    dialog._confirm()
    assert dialog.result_folder == app / "data"
    assert dialog._gitignore_yes is None          # no repository, so nothing is asked
    assert dfg.has_self_ignore(app / "data")


def test_a_repository_that_does_not_ignore_the_folder_is_asked_and_the_default_writes_the_file(qtbot, tmp_path):
    repo = _init_repo(tmp_path / "repo")
    dialog = dld.DataLocationDialog(repo, first_start=True)
    qtbot.addWidget(dialog)
    dialog._confirm()
    qtbot.waitUntil(lambda: dialog._gitignore_yes is not None, timeout=10000)
    dialog._gitignore_yes.click()
    qtbot.waitUntil(lambda: dialog.result_folder is not None, timeout=10000)
    assert dfg.has_self_ignore(repo / "data")
    assert dl.read_pointer(repo) == "data"


def test_declining_in_a_repository_saves_the_folder_without_the_file(qtbot, tmp_path):
    repo = _init_repo(tmp_path / "repo")
    dialog = dld.DataLocationDialog(repo, first_start=True)
    qtbot.addWidget(dialog)
    dialog._confirm()
    qtbot.waitUntil(lambda: dialog._gitignore_no is not None, timeout=10000)
    dialog._gitignore_no.click()
    qtbot.waitUntil(lambda: dialog.result_folder is not None, timeout=10000)
    assert not dfg.has_self_ignore(repo / "data")
    assert dl.read_pointer(repo) == "data"
