"""English text in M2's PSB files (menus, messages, credits, Master Book): one line per text string.

A message file holds ``{key: {language: [lines]}}``: the lines under ``eng`` are shown, the other languages
are not. Any other file shows its strings that read as text (two words with letters). A string with Cyrillic
letters is a line too, so a translated file shows the same lines as its source. A line is the string
at one place of the tree; saving puts the new string at that place only (strings shared with other places
or languages keep their text there) and writes the file again (``core.m2_psb.dump``); a file with no edit
keeps its bytes.
"""
from __future__ import annotations

import re
from typing import Any, List, Optional, Sequence, Tuple, Union

from core import m2_psb

MAGIC = b"PSB\0"
ENGLISH = "eng"
OTHER_LANGUAGES = {"jpn", "fra", "ger", "ita", "spa", "kor", "zhtw", "zhcn", "chs", "cht", "rus", "por"}
_TEXT = re.compile(r"[A-Za-z]{2,}[^\n]*\s[^\n]*[A-Za-z]{2,}")
_LATIN = re.compile(r"[A-Za-z]")
_CYRILLIC = re.compile("[Ѐ-ӿ]")

Path = Tuple[Union[str, int], ...]


def is_psb(data: bytes) -> bool:
    return bytes(data[:4]) == MAGIC


_NUMBER = re.compile(r"\d+|0x[0-9A-Fa-f]+")


def _is_id(value: str, keys: frozenset) -> bool:
    """A one-word string that names something in the code, not a label: snake_case, a file name, a path, a
    number, or a plain lower-case word (no capital, no space, no digit: stand, logo, static). Capitalised,
    all-caps words, words with a space or a digit (SAVE, Slot 1, OFF, Yes) are labels."""
    if any(c in value for c in "_./\\"):
        return True
    if _NUMBER.fullmatch(value):
        return True
    return value.islower() and " " not in value and not any(c.isdigit() for c in value)


def _keys(value: Any, found: set) -> set:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                found.add(key)
            _keys(item, found)
    elif isinstance(value, list):
        for item in value:
            _keys(item, found)
    return found


def _walk(value: Any, path: Path, english: bool, out: List[Tuple[Path, str]],
          words: bool = False, keys: frozenset = frozenset()) -> None:
    if isinstance(value, str):
        # A translated line must stay a line: Cyrillic letters count as text too.
        if _CYRILLIC.search(value) or (english and _LATIN.search(value)) or (not english and _TEXT.search(value)):
            out.append((path, value))
        elif words and _LATIN.search(value) and not _is_id(value, keys):
            out.append((path, value))              # a single-word label (SAVE, Slot 1, OFF)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in OTHER_LANGUAGES:
                continue
            _walk(item, path + (key,), english or key == ENGLISH, out, words, keys)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk(item, path + (index,), english, out, words, keys)


def lines(data: bytes, words: bool = False) -> List[Tuple[Path, str]]:
    """``[(place in the tree, text)]`` of the file's English text strings.

    ``words=True`` also shows one-word labels (SAVE, Slot 1, OFF) and skips the internal IDs (see ``_is_id``).
    The default keeps the two-word rule of the PlayStation plugin."""
    root, _psb = m2_psb.load(bytes(data))
    out: List[Tuple[Path, str]] = []
    _walk(root, (), False, out, words, frozenset(_keys(root, set())))
    return out


def where(path: Path) -> str:
    return "/".join(str(part) for part in path)


def build(data: bytes, texts: Sequence[Optional[str]], words: bool = False) -> bytes:
    """The file with ``texts`` (one per line of ``lines``; None or the same text = unchanged).

    ``words`` must match the value given to ``lines``."""
    root, psb = m2_psb.load(bytes(data))
    found: List[Tuple[Path, str]] = []
    _walk(root, (), False, found, words, frozenset(_keys(root, set())))
    changed = False
    strings = list(psb.strings)
    known = set(strings)
    for (path, old), new in zip(found, texts):
        if new is None or new == old:
            continue
        holder = root
        for part in path[:-1]:
            holder = holder[part]
        holder[path[-1]] = new
        if new not in known:
            strings.append(new)
            known.add(new)
        changed = True
    if not changed:
        return bytes(data)
    if psb.version not in (2, 3):
        raise ValueError(f"PSB version {psb.version} text cannot be written")
    return m2_psb.dump(root, psb.chunks, psb.version, psb.names, strings)
