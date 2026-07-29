"""Guards against import-time breakage across the whole codebase.

Unused-import cleanups, module moves and re-export changes all fail here first:
a single missing name turns into an ImportError/NameError for the module that
needs it, which the per-feature suites only catch if they happen to touch it.
"""
import importlib
import subprocess

import pytest

# Top-level packages that make up the application. `scripts/` is excluded on
# purpose: those are standalone entry points, not importable library code.
PACKAGES = ("core", "handlers", "ui", "utils", "components", "dialogs", "plugins", "tools")


def _project_modules():
    files = subprocess.run(
        ["git", "ls-files", "*.py"], capture_output=True, text=True, check=True
    ).stdout.split()
    mods = set()
    for f in files:
        if f.startswith("tests/") or f.split("/")[0] not in PACKAGES:
            continue
        m = f[:-3].replace("/", ".")
        mods.add(m[: -len(".__init__")] if m.endswith(".__init__") else m)
    return sorted(mods)


PROJECT_MODULES = _project_modules()


def test_module_list_is_not_empty():
    """A broken discovery step would make the import test vacuously pass."""
    assert len(PROJECT_MODULES) > 200, PROJECT_MODULES


@pytest.mark.parametrize("module_name", PROJECT_MODULES)
def test_module_imports(qapp, module_name):
    """Every module imports on its own, with no missing names."""
    importlib.import_module(module_name)
