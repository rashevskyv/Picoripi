"""No test reads a real key file: the owner's Switch, 3DS and Wii keys stay out of the suite.

The key tests generate their keys in ``tmp_path`` (``test_n3ds_decrypt.py``, ``test_switch_crypto.py``,
``test_switch_image.py``, ``test_wii_image.py``). A line that names the owner's key folder or a key file at a real
location fails this guard. The check is per line, in the text of each test file.
"""
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent
TEXT_SUFFIXES = {".py", ".json", ".txt", ".cfg", ".ini", ".toml", ".yaml", ".yml", ".md", ".csv", ".xml"}
# Built from parts so this file does not match its own patterns.
KEY_FILE = re.compile(r"(?i)prod" + r"\.keys|title" + r"\.keys|aes_keys" + r"\.txt|keys" + r"\.bin|boot" + r"9")
KEY_FOLDER = re.compile(r"(?i)[\\/\"']\.sw" + r"itch[\\/\"']|3ds_" + r"keys")
REAL_LOCATION = re.compile(r"(?i)home" + r"\(\)|expanduser|romhacking|_shared|[a-z]:[\\/]")


def _hits():
    found = []
    for path in sorted(TESTS.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES or "__pycache__" in path.parts:
            continue
        if path.name == Path(__file__).name:
            continue
        rel = path.relative_to(TESTS).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if KEY_FOLDER.search(line) or (KEY_FILE.search(line) and REAL_LOCATION.search(line)):
                found.append(f"tests/{rel}:{number}: {line.strip()[:120]}")
    return found


def test_no_test_names_a_real_key_file_or_key_folder():
    hits = _hits()
    assert not hits, ("a test names a real key file or key folder (generate the keys in tmp_path instead):\n"
                      + "\n".join(hits))
