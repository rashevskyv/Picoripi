"""The visible text of the interface and room bundles (``ui-*`` and ``room-*``) of Castlevania: Belmont's Curse (Switch).

Every shown TextMesh Pro text is a MonoBehaviour with ``m_text`` and ``m_fontAsset``. A text counts when it is not empty
and not Unity's ``New Text`` placeholder. One bundle with texts is one project file, ``ui\\<bundle name>.json``:
``{"table": <name>, "entries": [{"id": "<serialized file>/<path id>", "text": ...}]}``. A scene bundle holds several
serialized files; the id names the file and the object. A build writes a text back as ``m_text``; the object's other fields
keep their values. Objects that do not read (managed references of unknown types) are not in the project; they are counted.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

from core.i18n import tr
from core.unity.assets import MONOBEHAVIOUR
from core.unity.serialized import SerializedError, SerializedFile
from core.unity.unityfs import Bundle

UI_BUNDLE = re.compile(r"^Data/StreamingAssets/aa/Switch/(ui|room)-[^/]+\.bundle$")
PLACEHOLDER = "New Text"
FOLDER = "ui"
_STREAM_SUFFIXES = (".resS", ".res", ".resource")
Entry = Tuple[str, str]           # (id, text)


def table_name(bundle_file: str) -> str:
    """The project name of a bundle: its file name without the content hash (``ui-hud``, ``room-...``)."""
    stem = bundle_file[:-len(".bundle")] if bundle_file.endswith(".bundle") else bundle_file
    return re.sub(r"_(assets|scenes)_all_[0-9a-f]+$", "", stem)


def _shown_texts(data: bytes) -> Tuple[List[Tuple[str, int, str]], int]:
    """((serialized file, path id, text) of each shown text, number of objects that do not read)."""
    bundle = Bundle(data)
    found: List[Tuple[str, int, str]] = []
    unread = 0
    for node in bundle.nodes:
        if node.name.endswith(_STREAM_SUFFIXES):
            continue
        serialized = SerializedFile(bundle.read(node.name))
        for obj in serialized.objects:
            if obj.class_id != MONOBEHAVIOUR:
                continue
            try:
                value = serialized.read(obj.path_id)
            except SerializedError:
                unread += 1
                continue
            if not isinstance(value, dict) or "m_text" not in value or "m_fontAsset" not in value:
                continue
            text = str(value.get("m_text") or "")
            if text and text != PLACEHOLDER:
                found.append((node.name, obj.path_id, text))
    return found, unread


def has_text(data: bytes) -> bool:
    """True when the bundle holds at least one shown text."""
    return bool(_shown_texts(data)[0])


def entries(data: bytes) -> Tuple[List[Entry], int]:
    """The (id, text) pairs of one bundle and the number of objects that did not read."""
    found, unread = _shown_texts(data)
    return [(f"{name}/{path_id}", text) for name, path_id, text in found], unread


def table_json(name: str, items: List[Entry]) -> bytes:
    """The project file of one bundle: the JSON text, UTF-8, with a final newline."""
    body = {"table": name, "entries": [{"id": key, "text": text} for key, text in items]}
    return (json.dumps(body, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def parse_table_json(data: bytes) -> Tuple[str, List[Entry]]:
    body = json.loads(data.decode("utf-8"))
    return str(body["table"]), [(str(item["id"]), str(item["text"])) for item in body["entries"]]


def build_bundle(data: bytes, edits: Dict[str, str]) -> Optional[bytes]:
    """The bundle with the non-empty texts of ``edits`` (id -> text) written as ``m_text``; None when nothing changes."""
    bundle = Bundle(data)
    by_file: Dict[str, Dict[int, str]] = {}
    for key, text in edits.items():
        if not text:
            continue
        name, _, path = key.rpartition("/")
        try:
            path_id = int(path)      # a path id may be negative (a 64-bit id)
        except ValueError:
            raise ValueError(tr("{0} is not a text id", key)) from None
        if not name:
            raise ValueError(tr("{0} is not a text id", key))
        by_file.setdefault(name, {})[path_id] = text
    replaced: Dict[str, bytes] = {}
    for name, texts in by_file.items():
        if name not in bundle.names():
            raise ValueError(tr("the bundle has no serialized file {0}", name))
        serialized = SerializedFile(bundle.read(name))
        changes: Dict[int, bytes] = {}
        for path_id, text in texts.items():
            value = serialized.read(path_id)
            if value.get("m_text") == text:
                continue
            value["m_text"] = text
            changes[path_id] = serialized.write(path_id, value)
        if changes:
            replaced[name] = serialized.replace(changes)
    if not replaced:
        return None
    return bundle.build(replaced)
