"""The owner's build runs on a staged copy: the make command, the streamed log, cancel, and the work link never followed.

No test needs GNU make: a small Python script stands in for the make command (build_mod.make_argv is pointed at it).
"""
import sys
import time
from pathlib import Path

import pytest

from plugins.system_3ds import build_mod


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _repo(root: Path) -> Path:
    """A fake repo folder: the parts build() checks, a work folder with a file that must survive, and src/."""
    repo = root / "repo"
    _write(repo / "Makefile", "all:\n")
    _write(repo / "tools" / "build.py", "")
    _write(repo / "assets" / "a.bin", "a")
    _write(repo / "work" / "0004001000022000" / "keep.txt", "owner data")
    _write(repo / "src" / "marker.txt", "ukrainian text")
    return repo


def test_make_argv_quotes_the_python_path_with_forward_slashes():
    argv = build_mod.make_argv("make", "build-ru", r"C:\Program Files\Python314\python.exe")

    assert argv == ["make", "build-ru", 'PY="C:/Program Files/Python314/python.exe"']


def test_run_process_streams_lines_to_log_and_progress(tmp_path):
    script = _write(tmp_path / "talk.py", "for word in ('one', 'two', 'three'):\n    print(word, flush=True)\n")
    seen = []
    code, tail = build_mod.run_process([sys.executable, str(script)], tmp_path, tmp_path / "log.txt",
                                       lambda pct, text: seen.append((pct, text)), lambda: False)

    assert code == 0
    assert tail == ["one", "two", "three"]
    assert [text for _, text in seen] == ["one", "two", "three"]
    assert (tmp_path / "log.txt").read_text(encoding="utf-8").splitlines() == ["one", "two", "three"]


def test_run_process_cancel_stops_the_child_at_once(tmp_path):
    script = _write(tmp_path / "wait.py", "import time\nprint('started', flush=True)\ntime.sleep(60)\n")
    cancelled = []

    def progress(pct, text):
        cancelled.append(text)

    started = time.monotonic()
    code, _ = build_mod.run_process([sys.executable, str(script)], tmp_path, tmp_path / "log.txt", progress,
                                    lambda: bool(cancelled))

    assert code is None
    assert time.monotonic() - started < 30


def test_build_runs_the_staged_copy_and_keeps_the_owner_work_folder(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    fake = _write(tmp_path / "fake_make.py",
                  "import os\n"
                  "os.makedirs('dist/luma', exist_ok=True)\n"
                  "text = open('src/marker.txt', encoding='utf-8').read()\n"
                  "open('dist/luma/out.txt', 'w', encoding='utf-8').write(text + '|' + str(os.path.isdir('work')))\n")
    monkeypatch.setattr(build_mod, "find_make", lambda: "make")
    monkeypatch.setattr(build_mod, "make_argv", lambda make, target, python: [sys.executable, str(fake)])
    out = tmp_path / "out"
    out.mkdir()

    result = build_mod.build(str(repo / "src"), str(repo / "src"), "build-ru", str(out), lambda p, t: None,
                             lambda: False)

    assert result == out / "dist"
    assert (out / "dist" / "luma" / "out.txt").read_text(encoding="utf-8") == "ukrainian text|True"
    assert not (out / build_mod.STAGE_NAME).exists()
    assert (repo / "work" / "0004001000022000" / "keep.txt").read_text(encoding="utf-8") == "owner data"


def test_failed_build_removes_the_link_and_keeps_the_owner_files(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    fake = _write(tmp_path / "failing_make.py", "import sys\nprint('validate failed')\nsys.exit(2)\n")
    monkeypatch.setattr(build_mod, "find_make", lambda: "make")
    monkeypatch.setattr(build_mod, "make_argv", lambda make, target, python: [sys.executable, str(fake)])
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(ValueError, match="exit code 2"):
        build_mod.build(str(repo / "src"), str(repo / "src"), "build-en", str(out), lambda p, t: None, lambda: False)

    assert not (out / build_mod.STAGE_NAME).exists()
    assert (repo / "work" / "0004001000022000" / "keep.txt").read_text(encoding="utf-8") == "owner data"
    assert (repo / "src" / "marker.txt").read_text(encoding="utf-8") == "ukrainian text"


def test_missing_make_is_a_plain_error(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setattr(build_mod, "find_make", lambda: None)

    with pytest.raises(ValueError, match="GNU make"):
        build_mod.build(str(repo / "src"), str(repo / "src"), "build-ru", str(tmp_path), lambda p, t: None,
                        lambda: False)


def test_unlink_refuses_a_folder_that_is_not_a_link(tmp_path):
    folder = tmp_path / "real"
    _write(folder / "keep.txt", "x")

    with pytest.raises(ValueError):
        build_mod.unlink_dir(folder)

    assert (folder / "keep.txt").read_text(encoding="utf-8") == "x"


def test_unstage_removes_the_link_before_the_folder(tmp_path):
    target = tmp_path / "owner"
    _write(target / "keep.txt", "owner data")
    staging = tmp_path / "stage"
    staging.mkdir()
    build_mod.link_dir(target, staging / "work")
    _write(staging / "junk.txt", "temporary")

    build_mod.unstage(staging)

    assert not staging.exists()
    assert (target / "keep.txt").read_text(encoding="utf-8") == "owner data"


def test_the_plugin_declares_the_two_slot_targets_on_3ds():
    from plugins.system_3ds.rules import GameRules

    rules = GameRules()

    assert [platform["id"] for platform in rules.get_platforms()] == ["3ds"]
    assert [target["id"] for target in rules.get_build_targets()] == ["build-ru", "build-en"]
    assert {target["kind"] for target in rules.get_build_targets()} == {"layeredfs"}
