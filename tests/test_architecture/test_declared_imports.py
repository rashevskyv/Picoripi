"""Every third-party import in product code is declared in requirements.txt, the file setup.bat installs.

An import inside a ``try`` that catches ImportError is optional (the code has a fallback) and is not checked.
"""
import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRODUCT_DIRS = ("core", "plugins", "ui", "handlers", "utils", "dialogs", "components")
# import name -> the distribution that provides it, where the two names differ
DISTRIBUTION = {
    "PIL": "pillow",
    "Crypto": "pycryptodome",
    "ahocorasick": "pyahocorasick",
    "sip": "pyqt6-sip",
    "urllib3": "requests",  # installed with requests
}


def _normal(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _declared() -> set:
    names = set()
    for line in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].split(";", 1)[0].strip()
        match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", line)
        if match:
            names.add(_normal(match.group(0)))
    return names


def _catches_import_error(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    return any(isinstance(node, ast.Name) and node.id in ("ImportError", "ModuleNotFoundError", "Exception")
               for node in ast.walk(handler.type))


def _guarded(tree: ast.AST) -> set:
    """ids of every node inside a ``try`` body that catches ImportError."""
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(_catches_import_error(handler) for handler in node.handlers):
            for stmt in node.body:
                guarded.update(id(sub) for sub in ast.walk(stmt))
    return guarded


def _third_party_imports() -> dict:
    """import name -> ``file:line`` of its first import in product code."""
    local = {path.name for path in REPO.iterdir() if path.is_dir() and not path.name.startswith(".")}
    local |= {path.stem for path in REPO.glob("*.py")}
    found = {}
    for folder in PRODUCT_DIRS:
        for path in sorted((REPO / folder).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
            guarded = _guarded(tree)
            for node in ast.walk(tree):
                if id(node) in guarded:
                    continue
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    modules = [node.module]
                else:
                    continue
                for module in modules:
                    top = module.split(".")[0]
                    if top == "__future__" or top in sys.stdlib_module_names or top in local:
                        continue
                    found.setdefault(top, f"{path.relative_to(REPO).as_posix()}:{node.lineno}")
    return found


def test_every_third_party_import_is_declared():
    found = _third_party_imports()
    assert "PIL" in found and "PyQt6" in found, "the scan did not see the product code"
    declared = _declared()
    undeclared = {name: where for name, where in found.items()
                  if _normal(DISTRIBUTION.get(name, name)) not in declared}
    assert not undeclared, f"imported but not in requirements.txt: {undeclared}"
