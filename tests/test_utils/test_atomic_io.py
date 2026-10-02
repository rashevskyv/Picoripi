"""A file written through utils.atomic_io is the old version or the new one, never a torn one (WP6 6.1)."""
import json
import os

import pytest

from utils import atomic_io
from utils.atomic_io import atomic_write_bytes, atomic_write_json, atomic_write_text


def _leftovers(folder):
    return [path.name for path in folder.iterdir() if path.name.endswith(".tmp")]


def test_text_json_and_bytes_are_written_and_nothing_is_left_behind(tmp_path):
    atomic_write_text(tmp_path / "a.txt", "рядок\r\nдругий\n", newline="")
    atomic_write_json(tmp_path / "a.json", {"ключ": [1, 2]}, ensure_ascii=False, indent=4)
    atomic_write_bytes(tmp_path / "a.bin", b"\x00\xff")

    assert (tmp_path / "a.txt").read_bytes() == "рядок\r\nдругий\n".encode("utf-8")       # endings kept as given
    assert (tmp_path / "a.json").read_text(encoding="utf-8") == json.dumps({"ключ": [1, 2]}, ensure_ascii=False, indent=4)
    assert (tmp_path / "a.bin").read_bytes() == b"\x00\xff"
    assert _leftovers(tmp_path) == []


def test_by_default_line_endings_are_written_the_way_open_w_writes_them(tmp_path):
    """The sites this replaced used open(path, "w"): the files must come out byte for byte the same."""
    with open(tmp_path / "plain.txt", "w", encoding="utf-8") as stream:
        stream.write("one\ntwo\n")

    atomic_write_text(tmp_path / "atomic.txt", "one\ntwo\n")
    atomic_write_json(tmp_path / "atomic.json", {"a": 1}, indent=2)
    with open(tmp_path / "plain.json", "w", encoding="utf-8") as stream:
        json.dump({"a": 1}, stream, indent=2)

    assert (tmp_path / "atomic.txt").read_bytes() == (tmp_path / "plain.txt").read_bytes()
    assert (tmp_path / "atomic.json").read_bytes() == (tmp_path / "plain.json").read_bytes()


def test_the_parent_folder_is_created_and_a_string_path_is_accepted(tmp_path):
    target = tmp_path / "deep" / "er" / "file.json"

    atomic_write_json(str(target), [1])

    assert json.loads(target.read_text(encoding="utf-8")) == [1]


def test_data_that_cannot_be_serialised_leaves_the_old_file_untouched(tmp_path):
    target = tmp_path / "project.json"
    target.write_text('{"kept": true}', encoding="utf-8")

    with pytest.raises(TypeError):
        atomic_write_json(target, {"bad": object()})

    assert target.read_text(encoding="utf-8") == '{"kept": true}' and _leftovers(tmp_path) == []


def test_a_failure_while_writing_leaves_the_old_file_and_no_temporary_file(tmp_path, monkeypatch):
    target = tmp_path / "glossary.json"
    target.write_text("old", encoding="utf-8")

    def full_disk(_descriptor):
        raise OSError("No space left on device")

    monkeypatch.setattr(os, "fsync", full_disk)
    with pytest.raises(OSError):
        atomic_write_text(target, "new and longer")

    assert target.read_text(encoding="utf-8") == "old" and _leftovers(tmp_path) == []


def test_a_target_that_is_briefly_locked_is_retried(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    target.write_text("old", encoding="utf-8")
    real_replace = os.replace
    attempts = []

    def locked_twice(source, destination):
        attempts.append(1)
        if len(attempts) < 3:
            raise PermissionError("the file is in use")
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", locked_twice)
    monkeypatch.setattr(atomic_io.time, "sleep", lambda _seconds: None)

    atomic_write_text(target, "new")

    assert target.read_text(encoding="utf-8") == "new" and len(attempts) == 3 and _leftovers(tmp_path) == []


def test_a_target_that_stays_locked_is_an_error_and_the_old_file_remains(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    target.write_text("old", encoding="utf-8")

    def always_locked(source, destination):
        raise PermissionError("the file is in use")

    monkeypatch.setattr(os, "replace", always_locked)
    monkeypatch.setattr(atomic_io.time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError):
        atomic_write_text(target, "new")

    assert target.read_text(encoding="utf-8") == "old" and _leftovers(tmp_path) == []


USER_DATA_WRITERS = [
    "core/data_manager.py", "core/project/persist_mixin.py", "core/settings/global_settings.py",
    "core/settings/plugin_settings.py", "core/settings/session_state_manager.py", "core/glossary/parse_mixin.py",
    "core/saved_translations_manager.py", "core/reference_manager.py", "core/companion_sync.py",
    "core/data_processor/save_mixin.py", "core/data_processor/session_manager.py", "core/formats.py",
    "core/speaker_alias_merge.py", "handlers/saved_translations_handler.py",
    "handlers/translation/glossary_prompt_manager.py", "ui/script_markup/mixins/project_io_mixin.py",
    "ui/settings/load_save_mixin.py", "ui/main_window/actions/tag_alias_mixin.py",
    "components/glossary/actions_mixin.py",
]


@pytest.mark.parametrize("module", USER_DATA_WRITERS)
def test_the_modules_that_store_user_data_do_not_open_files_for_writing_themselves(module):
    """A plain open(path, "w") in one of these is a way back to torn files."""
    import re
    from pathlib import Path

    plain_write = re.compile(r"""open\([^)\n]*['"]w['"]|\.write_text\(|\.write_bytes\(""")
    # Not overwriting anyone's data: a brand-new empty file, a .bak copy, and
    # a temporary file that the code renames over the target itself.
    harmless = ('path.write_text("[]\\n"', "bak_path.write_bytes(", "backup.write_bytes(", "tmp_path.")
    plain_writes = [
        line.strip() for line in Path(module).read_text(encoding="utf-8").splitlines()
        if plain_write.search(line) and not any(marker in line for marker in harmless)
    ]
    assert plain_writes == []

