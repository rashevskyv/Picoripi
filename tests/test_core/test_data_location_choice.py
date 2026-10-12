"""Chooser model: options, checks and the copy of an old data folder (never overwrites, never deletes)."""
import pytest

from core.data_location_choice import (
    OPTION_CUSTOM, OPTION_LEGACY, OPTION_PORTABLE, PROBLEM_EMPTY, PROBLEM_INSIDE_SOURCE,
    PROBLEM_NOT_WRITABLE, DataLocationModel, copy_missing,
)


def _tree(root, files):
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_legacy_option_appears_only_when_the_old_folder_exists(tmp_path):
    assert DataLocationModel(tmp_path).options() == [OPTION_PORTABLE, OPTION_CUSTOM]
    legacy = tmp_path / "old"
    legacy.mkdir()
    assert DataLocationModel(tmp_path, legacy).options() == [OPTION_PORTABLE, OPTION_CUSTOM, OPTION_LEGACY]


def test_portable_option_points_next_to_the_program(tmp_path):
    model = DataLocationModel(tmp_path)
    assert model.path_for(OPTION_PORTABLE) == tmp_path / "data"
    assert model.path_for(OPTION_CUSTOM, tmp_path / "mine") == tmp_path / "mine"
    with pytest.raises(ValueError):
        model.path_for("nonsense")


def test_empty_and_unwritable_targets_are_refused(tmp_path):
    model = DataLocationModel(tmp_path)
    assert model.problems(None) == [PROBLEM_EMPTY]
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    assert model.problems(blocker / "data") == [PROBLEM_NOT_WRITABLE]
    assert model.problems(tmp_path / "fine") == []


def test_folder_inside_the_old_profile_is_refused_but_the_old_folder_itself_may_be_kept(tmp_path):
    legacy = tmp_path / "old"
    legacy.mkdir()
    model = DataLocationModel(tmp_path, legacy)
    assert PROBLEM_INSIDE_SOURCE in model.problems(legacy / "sub")
    assert PROBLEM_INSIDE_SOURCE in model.problems(legacy)
    assert model.problems(legacy, same_ok=True) == []
    assert PROBLEM_INSIDE_SOURCE in model.problems(legacy / "sub", same_ok=True)


def test_build_choice_copies_only_into_a_new_folder(tmp_path):
    legacy = tmp_path / "old"
    legacy.mkdir()
    model = DataLocationModel(tmp_path, legacy)
    copy = model.build_choice(OPTION_PORTABLE, None, copy_legacy=True)
    assert copy.target == tmp_path / "data" and copy.copy_from == legacy
    no_copy = model.build_choice(OPTION_PORTABLE, None, copy_legacy=False)
    assert no_copy.copy_from is None
    keep = model.build_choice(OPTION_LEGACY, None, copy_legacy=True)
    assert keep.target == legacy and keep.copy_from is None


def test_free_space_is_reported_for_a_folder_that_does_not_exist_yet(tmp_path):
    assert DataLocationModel(tmp_path).free_bytes(tmp_path / "new" / "deeper") > 0


def test_copy_places_every_file_and_leaves_the_source_alone(tmp_path):
    source = _tree(tmp_path / "old", {"settings.json": "{}", "plugins/zelda/a.json": "1", "projects/p/x.txt": "x"})
    destination = tmp_path / "new"
    result = copy_missing(source, destination)
    assert sorted(result.copied) == ["plugins/zelda/a.json", "projects/p/x.txt", "settings.json"]
    assert (destination / "plugins" / "zelda" / "a.json").read_text(encoding="utf-8") == "1"
    assert (source / "settings.json").read_text(encoding="utf-8") == "{}"   # source untouched
    assert not any(name.endswith(".part") for name in (p.name for p in destination.rglob("*")))


def test_copy_is_idempotent_and_never_overwrites(tmp_path):
    source = _tree(tmp_path / "old", {"settings.json": "old"})
    destination = _tree(tmp_path / "new", {"settings.json": "chosen before"})
    result = copy_missing(source, destination)
    assert result.copied == []
    assert result.skipped == ["settings.json"]
    assert (destination / "settings.json").read_text(encoding="utf-8") == "chosen before"
    again = copy_missing(source, tmp_path / "new2")
    assert len(again.copied) == 1
    assert copy_missing(source, tmp_path / "new2").copied == []


def test_copy_can_be_cancelled_between_files(tmp_path):
    source = _tree(tmp_path / "old", {"a.txt": "a", "b.txt": "b", "c.txt": "c"})
    calls = {"n": 0}

    def stop_after_one():
        calls["n"] += 1
        return calls["n"] > 1

    result = copy_missing(source, tmp_path / "new", should_stop=stop_after_one)
    assert result.stopped
    assert len(result.copied) == 1
    assert len(list((tmp_path / "new").iterdir())) == 1   # no partial file was left behind


def test_copy_refuses_a_destination_inside_the_source(tmp_path):
    source = _tree(tmp_path / "old", {"a.txt": "a"})
    with pytest.raises(ValueError):
        copy_missing(source, source / "inside")
