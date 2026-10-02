"""Every product module says in one line what it is for (WP7 7.6)."""
import ast
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NOT_PRODUCT = ("tests/", "docs/", "scratch/")


def _product_modules():
    """Python files of the repository: tracked or new, never the ignored ones (environments, local tools)."""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.split("\n")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [name for name in listed if name and not name.startswith(NOT_PRODUCT) and (ROOT / name).exists()]


def test_every_module_has_a_docstring():
    bare = []
    for name in _product_modules():
        source = (ROOT / name).read_text(encoding="utf-8-sig")
        if source.strip() and ast.get_docstring(ast.parse(source)) is None:
            bare.append(name)

    assert sorted(bare) == [], "add a one-line module docstring: what the module is for"


def test_the_list_holds_the_product_and_not_the_environment():
    modules = set(_product_modules())

    assert {"main.py", "core/data_store.py", "plugins/zelda_bmg/rules.py", "tasks.py"} <= modules
    assert not any(name.startswith(("venv/", ".venv", "tests/")) for name in modules)
