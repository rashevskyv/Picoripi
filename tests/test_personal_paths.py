"""No hard-coded personal drive path in the test suite.

The suite runs on the owner's PC and on other machines. A literal path on the owner's drives, or in the owner's
home folder, makes a test read or write the owner's folders. Real game files go through ``romhacking_root``; scratch output goes to
``tmp_path`` or ``PICORIPI_SCRATCH``.
"""
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent
# Built from parts so this file never matches its own pattern.
PATTERN = re.compile(r"(?i)\b[" + "de" + r"]:[\\/]|\bc:[\\/]+users")
TEXT_SUFFIXES = {".py", ".json", ".txt", ".cfg", ".ini", ".toml", ".yaml", ".yml", ".md", ".csv", ".xml"}
# Relative posix paths that may keep a match, each with its reason. Empty on purpose.
ALLOW: dict = {}


def _hits():
    found = []
    for path in sorted(TESTS.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(TESTS).as_posix()
        if rel in ALLOW:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                found.append(f"tests/{rel}:{number}: {line.strip()[:120]}")
    return found


def test_no_hard_coded_personal_drive_path_in_tests():
    hits = _hits()
    assert not hits, "personal drive path in the test suite (use romhacking_root or tmp_path):\n" + "\n".join(hits)
