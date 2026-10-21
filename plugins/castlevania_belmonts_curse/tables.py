"""The English string tables of Castlevania: Belmont's Curse (Switch, Unity Localization) as project files.

The English localization bundle holds 45 string tables (MonoBehaviours with ``m_TableData``). Each table is one JSON file
of the project's ``message`` folder: ``{"table": <name>, "entries": [{"id": <key id>, "text": <string>}, ...]}``. Ids
identify an entry; the table name identifies the table. The SWUK translation (a Ukrainian mod) is imported by table name
and id; a build writes the translation's texts back into the bundle, with every other byte of the bundle unchanged.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from core.unity.serialized import SerializedError, SerializedFile
from core.unity.unityfs import Bundle

MONOBEHAVIOUR = 114
TABLE_KEY = "m_TableData"
Entry = Tuple[int, str]          # (key id, text)


def table_json(name: str, entries: List[Entry]) -> bytes:
    """The project file of one table: the JSON text, UTF-8, with a final newline."""
    body = {"table": name, "entries": [{"id": key, "text": text} for key, text in entries]}
    return (json.dumps(body, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def parse_table_json(data: bytes) -> Tuple[str, List[Entry]]:
    """The table name and its (id, text) entries of a project file made by ``table_json``."""
    body = json.loads(data.decode("utf-8"))
    entries = [(int(item["id"]), str(item["text"])) for item in body["entries"]]
    return str(body["table"]), entries


def open_bundle(data: bytes) -> Tuple[Bundle, SerializedFile]:
    """The bundle and the serialized file of its one ``CAB-`` entry (the localization bundles have one)."""
    bundle = Bundle(data)
    cabs = [name for name in bundle.names() if name.startswith("CAB-") and not name.endswith((".resS", ".resource"))]
    if len(cabs) != 1:
        raise ValueError("a localization bundle holds one serialized file")
    return bundle, SerializedFile(bundle.read(cabs[0]))


def tables(serialized: SerializedFile) -> Dict[str, int]:
    """Table name -> path id of each string table in the file."""
    found: Dict[str, int] = {}
    for obj in serialized.objects:
        if obj.class_id != MONOBEHAVIOUR:
            continue
        try:
            value = serialized.read(obj.path_id)
        except SerializedError:
            continue
        if isinstance(value, dict) and TABLE_KEY in value:
            found[str(value.get("m_Name") or obj.path_id)] = obj.path_id
    return found


def read_entries(serialized: SerializedFile, path_id: int) -> List[Entry]:
    """The (id, text) pairs of one table, in the table's order."""
    value = serialized.read(path_id)
    return [(int(item["m_Id"]), str(item["m_Localized"] or "")) for item in value[TABLE_KEY]]


def import_translation(mod_bundle: bytes, source_entries: Dict[str, List[Entry]]) -> Dict[str, List[Entry]]:
    """The translation texts of ``mod_bundle`` for each table of ``source_entries`` that it holds with the same ids.

    A table whose ids differ from the source is not imported (the caller reports it). Returns table -> (id, text).
    """
    _bundle, serialized = open_bundle(mod_bundle)
    found = tables(serialized)
    imported: Dict[str, List[Entry]] = {}
    for name, entries in source_entries.items():
        if name not in found:
            continue
        mod_entries = read_entries(serialized, found[name])
        if [key for key, _text in mod_entries] != [key for key, _text in entries]:
            continue
        imported[name] = mod_entries
    return imported


def build_bundle(original: bytes, edits: Dict[str, Dict[int, str]]) -> Optional[bytes]:
    """The bundle with the texts of ``edits`` (table -> id -> text) written into its tables; None when nothing changes.

    Ids without a text, or with an empty one, keep their original text. Every other table keeps its bytes.
    """
    bundle, serialized = open_bundle(original)
    found = tables(serialized)
    changes: Dict[int, bytes] = {}
    for name, texts in edits.items():
        if name not in found:
            raise ValueError(f"the bundle has no table {name}")
        value = serialized.read(found[name])
        changed = False
        for item in value[TABLE_KEY]:
            text = texts.get(int(item["m_Id"]))
            if text and text != item["m_Localized"]:
                item["m_Localized"] = text
                changed = True
        if changed:
            changes[found[name]] = serialized.write(found[name], value)
    if not changes:
        return None
    cab = next(name for name in bundle.names() if name.startswith("CAB-") and not name.endswith((".resS", ".resource")))
    return bundle.build({cab: serialized.replace(changes)})
