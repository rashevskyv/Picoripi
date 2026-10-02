"""Product code does not find out by itself that a test is running (WP6 6.4)."""
import re

from pathlib import Path

PRODUCT_PATHS = ("main.py", "components", "core", "dialogs", "handlers", "plugins", "tools", "ui", "utils")


def _product_python_files():
    for name in PRODUCT_PATHS:
        path = Path(name)
        yield from ([path] if path.is_file() else sorted(path.rglob("*.py")))

# The caller says how it runs (utils.app_mode.headless); sniffing for the test runner, or replacing another
# module's globals so that a test can patch them, hides what the code does when a person uses it.
FORBIDDEN = {
    "the test runner looked up in sys.modules": re.compile(r"""['"]pytest['"]\s+(not\s+)?in\s+sys\.modules"""),
    "the test runner's environment variable": re.compile(r"PYTEST_CURRENT_TEST"),
    "a late-bound name injected into another module": re.compile(r"\b_ShimName\b"),
    "a mock imported into product code": re.compile(r"^\s*(from unittest(\.mock)? import|import unittest\.mock)", re.M),
}
# Helpers whose job is testing: they are shipped for plugin authors, they are not application code.
EXEMPT = {"plugins/testing.py", "tools/generate_test_stubs.py", "utils/app_mode.py"}


def test_product_code_does_not_detect_tests():
    offenders = []
    for path in _product_python_files():
        if path.as_posix() in EXEMPT:
            continue
        text = path.read_text(encoding="utf-8-sig")
        for what, pattern in FORBIDDEN.items():
            for found in pattern.finditer(text):
                offenders.append(f"{path.as_posix()}:{text.count(chr(10), 0, found.start()) + 1}: {what}")

    assert offenders == []


def test_the_switch_is_read_when_needed_never_copied_at_import():
    """``from utils.app_mode import headless`` would freeze the value before the caller could set it."""
    offenders = [
        path.as_posix() for path in _product_python_files()
        if re.search(r"from utils\.app_mode import", path.read_text(encoding="utf-8-sig"))
    ]

    assert offenders == []
