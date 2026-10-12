"""The data folder and Git: a self-ignoring .gitignore, and the check whether a repository ignores the folder.

Real git in temporary repositories; no fakes.
"""
import shutil
import subprocess

import pytest

from utils import data_folder_git as dfg

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git on PATH")


@pytest.fixture(autouse=True)
def _search_stops_at_the_temp_folder(tmp_path, monkeypatch):
    """A temp folder can sit inside a git work tree on this machine (the C: root is one): keep the search inside it."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path.resolve()


def test_a_folder_outside_any_repository_has_no_repo(tmp_path):
    state = dfg.data_folder_git_state(tmp_path / "data")
    assert state.state == dfg.GIT_NO_REPO
    assert state.repo is None


def test_a_folder_in_a_repository_that_does_not_ignore_it_is_not_ignored(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    state = dfg.data_folder_git_state(repo / "data")   # the folder does not exist yet: the chooser case
    assert state.state == dfg.GIT_NOT_IGNORED
    assert state.repo == repo


def test_a_repository_pattern_that_ignores_the_folder_is_seen(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text("data/\n", encoding="utf-8")
    state = dfg.data_folder_git_state(repo / "data")
    assert state.state == dfg.GIT_IGNORED


def test_the_nearest_repository_above_a_nested_folder_is_used(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    nested = repo / "games" / "zelda" / "data"
    assert dfg.find_work_tree(nested) == repo
    assert dfg.data_folder_git_state(nested).state == dfg.GIT_NOT_IGNORED


def test_a_git_file_counts_as_a_work_tree_entry(tmp_path):
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    assert dfg.find_work_tree(linked / "data") == linked.resolve()


def test_ensure_self_ignore_creates_the_folder_and_the_file(tmp_path):
    folder = tmp_path / "data"
    assert dfg.ensure_self_ignore(folder) is True
    assert (folder / ".gitignore").read_text(encoding="utf-8").splitlines()[-1] == "*"
    assert dfg.has_self_ignore(folder)


def test_ensure_self_ignore_writes_lf_line_endings_only(tmp_path):
    dfg.ensure_self_ignore(tmp_path)
    assert b"\r" not in (tmp_path / ".gitignore").read_bytes()


def test_ensure_self_ignore_is_idempotent(tmp_path):
    dfg.ensure_self_ignore(tmp_path)
    before = (tmp_path / ".gitignore").read_bytes()
    assert dfg.ensure_self_ignore(tmp_path) is False
    assert (tmp_path / ".gitignore").read_bytes() == before


def test_ensure_self_ignore_keeps_the_lines_already_there(tmp_path):
    (tmp_path / ".gitignore").write_text("keep-me/", encoding="utf-8")   # no trailing newline
    assert dfg.ensure_self_ignore(tmp_path) is True
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert text.startswith("keep-me/\n")
    assert text.splitlines()[-1] == "*"


def test_a_self_ignoring_folder_is_ignored_inside_a_repository(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    dfg.ensure_self_ignore(repo / "data")
    assert dfg.data_folder_git_state(repo / "data").state == dfg.GIT_IGNORED


def test_a_self_ignoring_folder_outside_a_repository_is_still_marked(tmp_path):
    dfg.ensure_self_ignore(tmp_path / "data")
    state = dfg.data_folder_git_state(tmp_path / "data")
    assert state.state == dfg.GIT_NO_REPO
    assert dfg.has_self_ignore(tmp_path / "data")
