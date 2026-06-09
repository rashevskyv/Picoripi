"""
Static analysis test using pyflakes.

Catches undefined names (NameError at runtime) across project source files.
Ignores: unused imports, star-import warnings (these are not runtime errors).

Run as part of the normal test suite:
    $env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest tests/test_static_analysis.py -v
"""
import subprocess
import sys
import re
from pathlib import Path
import pytest

# Directories to scan (relative to project root)
SOURCE_DIRS = ["components", "core", "dialogs", "handlers", "plugins", "ui", "utils", "main.py"]

# Error patterns from pyflakes that indicate a RUNTIME error (NameError etc.)
# "undefined name 'X'" is the only one that guarantees a runtime NameError.
CRITICAL_PATTERN = re.compile(r"undefined name '(.+)'")

# Known false positives: pyflakes reports these as undefined but they are not
# (e.g. names injected by exec, TYPE_CHECKING guards, or known pyflakes bugs).
KNOWN_FALSE_POSITIVES: set[str] = set()


def _run_pyflakes(project_root: Path) -> list[str]:
    targets = [str(project_root / t) for t in SOURCE_DIRS]
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes"] + targets,
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    # pyflakes writes all output to stdout; exit code 1 just means "found issues"
    lines = result.stdout.splitlines() + result.stderr.splitlines()
    return lines


def _collect_critical_errors(lines: list[str], project_root: Path) -> list[str]:
    """Return only lines that represent critical undefined-name errors."""
    errors = []
    root_str = str(project_root)
    for line in lines:
        if not CRITICAL_PATTERN.search(line):
            continue
        # Strip absolute path prefix so output is readable
        relative_line = line.replace(root_str + "\\", "").replace(root_str + "/", "")
        # Skip known false positives
        match = CRITICAL_PATTERN.search(line)
        if match and match.group(1) in KNOWN_FALSE_POSITIVES:
            continue
        errors.append(relative_line)
    return errors


def test_no_undefined_names_in_source():
    """
    Runs pyflakes on all project source directories and fails if any file
    contains an undefined name — the static equivalent of a runtime NameError.

    Unused imports and star-import ambiguities are intentionally ignored here
    because they do not cause crashes at runtime.
    """
    project_root = Path(__file__).parent.parent.resolve()
    lines = _run_pyflakes(project_root)
    errors = _collect_critical_errors(lines, project_root)

    if errors:
        error_report = "\n".join(errors)
        pytest.fail(
            f"pyflakes found {len(errors)} undefined name(s) in project source "
            f"(these will cause NameError at runtime):\n\n{error_report}"
        )
