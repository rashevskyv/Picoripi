"""Resolver of the user data folder: explicit choices only, no writes, no home lookup."""
import json
from pathlib import Path

from utils import data_location as dl


def test_env_variable_is_an_explicit_choice(tmp_path):
    location = dl.resolve_data_location(root=tmp_path / "app", environ={dl.ENV_VAR: str(tmp_path / "chosen")})
    assert location.path == tmp_path / "chosen"
    assert location.source == "env"
    assert not location.needs_choice


def test_blank_env_variable_is_ignored(tmp_path):
    location = dl.resolve_data_location(root=tmp_path / "app", environ={dl.ENV_VAR: "   "})
    assert location.source == "none"


def test_without_any_choice_the_user_must_choose(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    location = dl.resolve_data_location(root=root, environ={})
    assert location.needs_choice
    assert location.path == root / "data"
    assert not (root / "data").exists()   # the resolver never creates the suggested folder


def test_an_existing_data_folder_alone_is_not_a_choice(tmp_path):
    root = tmp_path / "app"
    (root / "data").mkdir(parents=True)
    location = dl.resolve_data_location(root=root, environ={})
    assert location.needs_choice


def test_pointer_file_is_an_explicit_choice(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    target = tmp_path / "elsewhere"
    target.mkdir()
    dl.write_pointer(target, root)
    location = dl.resolve_data_location(root=root, environ={})
    assert location.path == target.resolve()
    assert location.source == "pointer"
    assert not location.needs_choice


def test_pointer_inside_the_program_folder_is_stored_relative(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    dl.write_pointer(root / "data", root)
    stored = json.loads((root / dl.POINTER_NAME).read_text(encoding="utf-8"))
    assert stored == {"data_dir": "data"}
    assert dl.resolve_data_location(root=root, environ={}).path == (root / "data").resolve()


def test_pointer_to_a_missing_unwritable_folder_asks_again(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    blocker = tmp_path / "file_not_folder"
    blocker.write_text("x", encoding="utf-8")
    (root / dl.POINTER_NAME).write_text(json.dumps({"data_dir": str(blocker / "data")}), encoding="utf-8")
    location = dl.resolve_data_location(root=root, environ={})
    assert location.needs_choice
    assert location.problem == dl.PROBLEM_SAVED_UNAVAILABLE


def test_env_variable_beats_the_pointer(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    dl.write_pointer(tmp_path / "pointer_choice", root)
    location = dl.resolve_data_location(root=root, environ={dl.ENV_VAR: str(tmp_path / "env_choice")})
    assert location.source == "env"
    assert location.path == tmp_path / "env_choice"


def test_broken_pointer_file_is_no_choice(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    (root / dl.POINTER_NAME).write_text("{not json", encoding="utf-8")
    assert dl.resolve_data_location(root=root, environ={}).needs_choice


def test_legacy_folder_is_found_only_when_asked(tmp_path):
    home = tmp_path / "home"
    (home / ".picoripi").mkdir(parents=True)
    assert dl.legacy_dir(home) == home / ".picoripi"
    assert dl.legacy_dir(tmp_path / "empty_home") is None


def test_usable_dir_rejects_a_path_below_a_file(tmp_path):
    file_path = tmp_path / "a_file"
    file_path.write_text("x", encoding="utf-8")
    assert not dl.is_usable_dir(file_path / "child")
    assert dl.is_usable_dir(tmp_path / "new" / "deeper")
    assert not (tmp_path / "new").exists()   # checking creates nothing


def test_resolve_target_keeps_absolute_paths_and_joins_relative_ones(tmp_path):
    assert dl.resolve_target(str(tmp_path / "x"), tmp_path / "app") == tmp_path / "x"
    assert dl.resolve_target("data", tmp_path / "app") == Path(tmp_path / "app" / "data")
