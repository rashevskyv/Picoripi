"""The routine commands, the same on Windows, Linux and macOS: ``python tasks.py <command>``.

    test          the default test lane, in parallel (extra arguments go to pytest)
    test-serial   the lane of heavy thread tests, one process
    test-perf     the performance lane
    lint          ruff
    smoke         import the application without a display and validate every plugin
    docs-check    document headers, docs/INDEX.md, the plugin contract page, tests/test_docs
    docs-index    refresh token counts and rebuild docs/INDEX.md
    graph         refresh the code graph (graphify update .)
    bump          next development version (scripts/bump_version.py)
    new-plugin    scaffold a plugin (tools/new_plugin.py <id> "<Name>" --prefix XX)
    run           start Picoripi

Any Python 3.10+ can start this file; the commands themselves run in the
project's environment: the one that is active, else ``venv``/``.venv`` in the
repository, else the interpreter that started this file. Add ``--dry-run``
to see the command lines instead of running them.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent
# Where tests keep their temporary files: inside the repository, because the system
# temp directory is not always writable for the account that runs them.
TEST_TEMP = ROOT / ".tmp_test_run"


def _python_in(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def project_python(prefer: Sequence[str] = ("venv", ".venv")) -> str:
    """The interpreter the commands run in: the active environment, then one in the repository."""
    active = os.environ.get("VIRTUAL_ENV")
    candidates = ([Path(active)] if active else []) + [ROOT / name for name in prefer]
    for environment in candidates:
        python = _python_in(environment)
        if python.exists():
            return str(python)
    return sys.executable


def _environment(headless: bool = False, test_temp: bool = False) -> Dict[str, str]:
    environment = dict(os.environ, PYTHONPATH=str(ROOT))
    if headless:
        environment["QT_QPA_PLATFORM"] = "offscreen"
    if test_temp:
        TEST_TEMP.mkdir(exist_ok=True)
        for name in ("TMPDIR", "TEMP", "TMP"):
            environment[name] = str(TEST_TEMP)
    return environment


class Runner:
    """Runs command lines from the repository root, or only prints them."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def __call__(self, command: List[str], *, headless: bool = False, test_temp: bool = False) -> int:
        if self.dry_run:
            print(" ".join(command))
            return 0
        return subprocess.call(command, cwd=ROOT, env=_environment(headless, test_temp))


def _pytest(run: Runner, extra: List[str], *default: str) -> int:
    return run([project_python(), "-m", "pytest", *default, *extra], headless=True, test_temp=True)


def test(run: Runner, extra: List[str]) -> int:
    workers = [] if any(argument.startswith("-n") for argument in extra) else ["-n", "auto"]
    paths = [] if any(not argument.startswith("-") and Path(argument.split("::")[0]).exists() for argument in extra) else ["tests/"]
    return _pytest(run, extra, *workers, "-q", *paths)


def test_serial(run: Runner, extra: List[str]) -> int:
    return _pytest(run, extra, "-p", "no:xdist", "-q", "-m", "serial", "tests/")


def test_perf(run: Runner, extra: List[str]) -> int:
    return _pytest(run, extra, "-q", "-m", "performance", "tests/test_performance.py")


def lint(run: Runner, extra: List[str]) -> int:
    return run([project_python(), "-m", "ruff", "check", ".", *extra])


def smoke(run: Runner, extra: List[str]) -> int:
    code = run([project_python(), "-c", "import main"], headless=True)
    return code or run([project_python(), "-m", "plugins.validate", *extra], headless=True)


def docs_index(run: Runner, extra: List[str]) -> int:
    return run([project_python(), "tools/docs_index.py", "--write"])


def docs_check(run: Runner, extra: List[str]) -> int:
    code = run([project_python(), "tools/docs_index.py", "--check"])
    return code or _pytest(run, extra, "-q", "-p", "no:cacheprovider", "tests/test_docs")


def graph(run: Runner, extra: List[str]) -> int:
    graphify = shutil.which("graphify")
    if not graphify and not run.dry_run:
        print("graphify is not installed (pip install graphifyy); the graph was not refreshed.")
        return 1
    return run([graphify or "graphify", "update", ".", *extra])


def bump(run: Runner, extra: List[str]) -> int:
    return run([project_python(), "scripts/bump_version.py", *extra])


def new_plugin(run: Runner, extra: List[str]) -> int:
    return run([project_python(), "tools/new_plugin.py", *extra])


def run_application(run: Runner, extra: List[str]) -> int:
    # run.bat has always started the application from .venv; keep that order for it.
    return run([project_python(prefer=(".venv", "venv")), "main.py", *extra])


COMMANDS: Dict[str, Callable[[Runner, List[str]], int]] = {
    "test": test,
    "test-serial": test_serial,
    "test-perf": test_perf,
    "lint": lint,
    "smoke": smoke,
    "docs-check": docs_check,
    "docs-index": docs_index,
    "graph": graph,
    "bump": bump,
    "new-plugin": new_plugin,
    "run": run_application,
}


def main(argv: Optional[List[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in arguments
    if dry_run:
        arguments.remove("--dry-run")
    if not arguments or arguments[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    name, extra = arguments[0], arguments[1:]
    command = COMMANDS.get(name)
    if command is None:
        print(f"Unknown command '{name}'. Commands: {', '.join(COMMANDS)}")
        return 2
    return command(Runner(dry_run), extra)


if __name__ == "__main__":
    sys.exit(main())
