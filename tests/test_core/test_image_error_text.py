"""Every ImageError message of the readers and the plugin unpack files goes through tr() and has a Ukrainian entry.

The error text reaches the Project Manager wizard, so an English-only message would show in the Ukrainian interface.
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _source_files():
    files = sorted((ROOT / "core" / "containers").glob("*.py"))
    files += sorted(ROOT.glob("plugins/*/unpack.py"))
    return files


def _image_error_messages():
    """``(file, line, first argument node)`` of every ImageError(...) call in the reader and unpack files."""
    found = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ImageError"
                    and node.args):
                found.append((path.relative_to(ROOT).as_posix(), node.lineno, node.args[0]))
    return found


def _is_tr_call(node):
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr"


def test_every_image_error_message_is_a_tr_call():
    not_translated = [f"{name}:{line}" for name, line, arg in _image_error_messages() if not _is_tr_call(arg)]

    assert not_translated == []


def test_every_image_error_literal_has_a_ukrainian_entry():
    catalog = json.loads((ROOT / "locales" / "uk.json").read_text(encoding="utf-8"))
    missing = []
    for name, line, arg in _image_error_messages():
        if _is_tr_call(arg) and arg.args and isinstance(arg.args[0], ast.Constant):
            text = arg.args[0].value
            if text not in catalog:
                missing.append(f"{name}:{line}: {text}")

    assert missing == []
