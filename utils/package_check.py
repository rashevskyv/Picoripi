"""Third-party packages that Picoripi imports late, and what to say when one is missing.

Nothing here imports a package: ``missing`` only asks the import system where each one is.
"""
from __future__ import annotations

import importlib.util

REQUIREMENTS_COMMAND = "python -m pip install -r requirements.txt"

# import name -> pip name, for the packages that are imported inside a function or a plugin
PACKAGES = {
    "numpy": "numpy",
    "Crypto": "pycryptodome",
}


def pip_name(import_name: str) -> str:
    return PACKAGES.get(import_name, import_name)


def missing() -> list:
    """The pip names of the packages in ``PACKAGES`` that cannot be found."""
    return [pip_name(name) for name in PACKAGES if importlib.util.find_spec(name) is None]
