"""The room's comments in the project folder (``comments.json``): read and written by every participant's Picoripi.

The room server writes the file too, from its own state. A participant's Picoripi writes the comments it holds when
they change, so they stay after the room closes. A file of another room is read by the host or a moderator, who adopt
its comments into the room (``comment_import``). Stdlib only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from utils.atomic_io import atomic_write_json

PROTOCOL = 2
COMMENTS_NAME = "comments.json"


def comments_path(project_dir: Path) -> Path:
    return Path(project_dir) / COMMENTS_NAME


def read_room_comments(path: Path, fingerprint: str) -> Tuple[str, List[Dict[str, Any]]]:
    """(room id, comments) of ``path`` for this project; an unreadable or foreign file gives ("", [])."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "", []
    if not isinstance(data, dict) or data.get("fingerprint") != fingerprint:
        return "", []
    comments = data.get("comments")
    if not isinstance(comments, list):
        return str(data.get("room_id") or ""), []
    return str(data.get("room_id") or ""), [c for c in comments if isinstance(c, dict) and isinstance(c.get("id"), str)]


def read_comments(path: Path, fingerprint: str) -> List[Dict[str, Any]]:
    return read_room_comments(path, fingerprint)[1]


def write_comments(path: Path, fingerprint: str, room_id: str, comments: List[Dict[str, Any]]) -> None:
    """Replace the file atomically (temporary file, then rename); raises ``OSError`` if it cannot."""
    atomic_write_json(Path(path), {"protocol": PROTOCOL, "fingerprint": fingerprint, "room_id": room_id,
                                   "comments": comments}, ensure_ascii=False)
