import ast
from pathlib import Path


PRODUCT_PATHS = (
    Path("main.py"),
    Path("components"),
    Path("core"),
    Path("dialogs"),
    Path("handlers"),
    Path("plugins"),
    Path("tools"),
    Path("ui"),
    Path("utils"),
)


def _product_python_files() -> list[Path]:
    files: list[Path] = []
    for path in PRODUCT_PATHS:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(path.rglob("*.py"))
    return sorted(files)


def test_product_code_does_not_call_qt_process_events():
    offenders: list[str] = []
    for path in _product_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "processEvents":
                offenders.append(f"{path}:{node.lineno}")

    assert offenders == []
