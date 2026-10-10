"""Text of the Metal Gear Solid Master Collection launcher (Unity): ``text/*.mctext`` files.

The workspace scripts (``_shared/scripts/zt/mclauncher.py``) write each text MonoBehaviour of the launcher as its
type tree in JSON: menus and messages (``TextDataList`` rows with one field per language), credits and licences
(``DataList`` ``str``), the Screenplay Book (``data`` lines ``text``, pages ``pageTitle`` / ``TextArea*``, the
index) and its speakers (``speakerName_EN``). A line is one English string at one place of the tree; saving
writes the tree back the way the scripts write it (``json.dumps(indent=1)``), so an unedited file keeps its bytes.
Used by the Metal Gear Solid 4, Peace Walker and Metal Gear 1/2 plugins.
"""
from __future__ import annotations

import json
from typing import Any, List, Optional, Sequence, Tuple, Union

EXTENSION = ".mctext"
_TEXT_KEYS = {"english", "str", "text", "pageTitle", "speakerName_EN", "name_EN", "title_EN"}

Path = Tuple[Union[str, int], ...]


def _is_text_key(key: str) -> bool:
    return key in _TEXT_KEYS or key.startswith("TextArea")


def _walk(value: Any, path: Path, out: List[Tuple[Path, str]]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str):
                if _is_text_key(key):       # empty ones too: a line never disappears when emptied
                    out.append((path + (key,), item))
            else:
                _walk(item, path + (key,), out)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk(item, path + (index,), out)


def is_launcher_text(data: bytes) -> bool:
    head = bytes(data[:200]).lstrip()
    return head.startswith(b"{") and b'"m_Script"' in bytes(data[:400])


def dump(tree: Any) -> bytes:
    return (json.dumps(tree, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def lines(data: bytes) -> List[Tuple[Path, str]]:
    """``[(place in the tree, English text)]``."""
    out: List[Tuple[Path, str]] = []
    _walk(json.loads(bytes(data).decode("utf-8")), (), out)
    return out


def where(path: Path) -> str:
    return "/".join(str(part) for part in path)


def build(data: bytes, texts: Sequence[Optional[str]]) -> bytes:
    """The file with ``texts`` (one per line of ``lines``; None or the same text = unchanged)."""
    tree = json.loads(bytes(data).decode("utf-8"))
    found: List[Tuple[Path, str]] = []
    _walk(tree, (), found)
    changed = False
    for (path, old), new in zip(found, texts):
        if new is None or new == old:
            continue
        holder = tree
        for part in path[:-1]:
            holder = holder[part]
        holder[path[-1]] = new
        changed = True
    return dump(tree) if changed else bytes(data)
