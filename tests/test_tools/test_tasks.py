"""tasks.py: one entry for the routine commands, with the interpreter taken from the environment (WP7 7.5)."""
import os
import sys
from pathlib import Path

import pytest

import tasks


def _lines(capsys):
    return capsys.readouterr().out.strip().splitlines()


def _environment(tmp_path, name):
    python = tmp_path / name / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    return python


class TestInterpreter:
    def test_the_active_environment_wins(self, tmp_path, monkeypatch):
        active = _environment(tmp_path, "active")
        _environment(tmp_path, "venv")
        monkeypatch.setattr(tasks, "ROOT", tmp_path)
        monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "active"))

        assert tasks.project_python() == str(active)

    def test_without_an_active_one_the_repository_s_environment_is_used(self, tmp_path, monkeypatch):
        _environment(tmp_path, ".venv")
        venv = _environment(tmp_path, "venv")
        monkeypatch.setattr(tasks, "ROOT", tmp_path)
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)

        assert tasks.project_python() == str(venv)
        assert tasks.project_python(prefer=(".venv", "venv")) == str(tmp_path / ".venv" / venv.relative_to(tmp_path / "venv"))

    def test_with_no_environment_at_all_it_is_the_interpreter_that_runs_the_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tasks, "ROOT", tmp_path)
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)

        assert tasks.project_python() == sys.executable

    def test_an_active_environment_that_has_no_interpreter_is_skipped(self, tmp_path, monkeypatch):
        venv = _environment(tmp_path, "venv")
        monkeypatch.setattr(tasks, "ROOT", tmp_path)
        monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "deleted"))

        assert tasks.project_python() == str(venv)


class TestCommands:
    @pytest.fixture(autouse=True)
    def fixed_interpreter(self, monkeypatch):
        monkeypatch.setattr(tasks, "project_python", lambda prefer=("venv", ".venv"): "PY" if prefer[0] == "venv" else "PY-APP")

    def test_the_documented_commands_exist(self):
        documented = [line.split()[0] for line in tasks.__doc__.splitlines() if line.startswith("    ") and line.strip()]

        assert sorted(documented) == sorted(tasks.COMMANDS)

    def test_test_runs_the_whole_suite_in_parallel(self, capsys):
        assert tasks.main(["test", "--dry-run"]) == 0

        assert _lines(capsys) == ["PY -m pytest -n auto -q tests/"]

    def test_arguments_go_to_pytest_and_replace_the_defaults_they_name(self, capsys):
        tasks.main(["test", "--dry-run", "-n", "4", "tests/test_tools/test_tasks.py", "-k", "tasks"])

        assert _lines(capsys) == ["PY -m pytest -q -n 4 tests/test_tools/test_tasks.py -k tasks"]

    def test_the_other_lanes(self, capsys):
        tasks.main(["test-serial", "--dry-run"])
        tasks.main(["test-perf", "--dry-run"])

        assert _lines(capsys) == [
            "PY -m pytest -p no:xdist -q -m serial tests/",
            "PY -m pytest -q -m performance tests/test_performance.py",
        ]

    def test_lint_smoke_docs_and_helpers(self, capsys):
        for command in ("lint", "smoke", "docs-index", "bump"):
            tasks.main([command, "--dry-run"])
        tasks.main(["new-plugin", "--dry-run", "my_game", "My Game", "--prefix", "MG"])

        assert _lines(capsys) == [
            "PY -m ruff check .",
            "PY -c import main",
            "PY -m plugins.validate",
            "PY tools/docs_index.py --write",
            "PY scripts/bump_version.py",
            "PY tools/new_plugin.py my_game My Game --prefix MG",
        ]

    def test_docs_check_checks_the_index_then_runs_the_document_tests(self, capsys):
        tasks.main(["docs-check", "--dry-run"])

        lines = _lines(capsys)
        assert lines == ["PY tools/docs_index.py --check", "PY -m pytest -q -p no:cacheprovider tests/test_docs"]

    def test_the_application_starts_from_the_environment_run_bat_always_used(self, capsys):
        tasks.main(["run", "--dry-run"])

        assert _lines(capsys) == ["PY-APP main.py"]

    def test_help_and_an_unknown_command(self, capsys):
        assert tasks.main([]) == 0
        assert "python tasks.py <command>" in capsys.readouterr().out
        assert tasks.main(["deploy"]) == 2
        assert "Unknown command 'deploy'" in capsys.readouterr().out


class TestEnvironment:
    def test_tests_run_headless_from_the_repository_with_their_own_temp_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tasks, "ROOT", tmp_path)
        monkeypatch.setattr(tasks, "TEST_TEMP", tmp_path / ".tmp_test_run")

        environment = tasks._environment(headless=True, test_temp=True)

        assert environment["PYTHONPATH"] == str(tmp_path)
        assert environment["QT_QPA_PLATFORM"] == "offscreen"
        assert {environment[name] for name in ("TMPDIR", "TEMP", "TMP")} == {str(tmp_path / ".tmp_test_run")}
        assert (tmp_path / ".tmp_test_run").is_dir()

    def test_other_commands_keep_the_caller_s_environment(self, monkeypatch):
        monkeypatch.setenv("QT_QPA_PLATFORM", "windows")

        assert tasks._environment()["QT_QPA_PLATFORM"] == "windows"


def test_the_launch_scripts_call_tasks_py_instead_of_naming_an_environment():
    root = Path(tasks.__file__).resolve().parent
    for name in ("test_all.ps1", "run.bat", "run.sh"):
        text = (root / name).read_text(encoding="utf-8")
        assert "tasks.py" in text, name
        assert "venv\\Scripts" not in text and "venv/bin" not in text, name
