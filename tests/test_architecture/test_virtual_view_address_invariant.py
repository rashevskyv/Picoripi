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


def _negative_int(node: ast.AST) -> int | None:
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, int)
    ):
        return -node.operand.value
    return None


def test_product_code_never_stores_virtual_sentinel_as_current_block_address():
    offenders: list[str] = []
    for path in _product_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            assignments: list[tuple[ast.AST, ast.AST]] = []
            if isinstance(node, ast.Assign):
                assignments.extend((target, node.value) for target in node.targets)
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                assignments.append((node.target, node.value))

            for target, value in assignments:
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr == "current_block_idx"
                    and _negative_int(value) in {-2, -3, -4}
                ):
                    offenders.append(f"{path}:{node.lineno}")

    assert offenders == []
