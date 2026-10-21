"""The dialogue graphs of the narration bundle (``narration_assets_all_*``) of Castlevania: Belmont's Curse (Switch).

A graph is a MonoBehaviour whose name is the scene's name (``Medusa_Fight_Random``). Its nodes hold managed references.
A dialogue node has an actor (``ActorRef``, a GUID) and a Unity Localization line: the string table collection
(``m_TableCollectionName``, for example ``Narration_ACT1``) and the key id of its entry. The line's text is in the English
string table of that collection (``message\\Narration_ACT1_en.json``); the graph only refers to it. ``index`` lists, for
each entry, the scenes and the speaker GUIDs that use it; the unpack writes them into the table file as optional
``scenes`` and ``speakers`` fields. The build ignores them. A line whose collection is a GUID or empty is not in the English
tables (the character names come from another collection); ``index`` counts those.
"""
from __future__ import annotations

import re
from typing import Dict, Iterator, List, Set, Tuple

from core.unity.assets import MONOBEHAVIOUR
from core.unity.serialized import SerializedError, SerializedFile
from core.unity.unityfs import Bundle

BUNDLE = re.compile(r"^Data/StreamingAssets/aa/Switch/narration_assets_all_[0-9a-f]+\.bundle$")
TABLE_SUFFIX = "_en"
_STREAM_SUFFIXES = (".resS", ".res", ".resource")
Index = Dict[str, Dict[int, Dict[str, List[str]]]]     # collection -> key id -> {"scenes": [...], "speakers": [...]}


def collection_of(table: str) -> str:
    """The string table collection of a table file's name: ``Narration_ACT1_en`` gives ``Narration_ACT1``."""
    return table[:-len(TABLE_SUFFIX)] if table.endswith(TABLE_SUFFIX) else table


def _lines(value, speaker: str) -> Iterator[Tuple[str, int, str]]:
    """(collection, key id, speaker) of each localized line in ``value``; a speaker is the nearest ``ActorRef`` above."""
    if isinstance(value, dict):
        actor = value.get("ActorRef")
        if isinstance(actor, dict) and actor.get("m_AssetGUID"):
            speaker = str(actor["m_AssetGUID"])
        table = value.get("m_TableReference")
        entry = value.get("m_TableEntryReference")
        if isinstance(table, dict) and isinstance(entry, dict):
            yield str(table.get("m_TableCollectionName") or ""), int(entry.get("m_KeyId") or 0), speaker
        for item in value.values():
            yield from _lines(item, speaker)
    elif isinstance(value, list):
        for item in value:
            yield from _lines(item, speaker)


def index(data: bytes) -> Tuple[Index, int]:
    """The index of the bundle's dialogue lines, and the number of lines outside the English tables (GUID or empty)."""
    bundle = Bundle(data)
    found: Dict[Tuple[str, int], Dict[str, Set[str]]] = {}
    outside = 0
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
                continue
            scene = str(value.get("m_Name") or "") if isinstance(value, dict) else ""
            for collection, key, speaker in _lines(value, ""):
                if not collection or collection.startswith("GUID:"):
                    outside += 1
                    continue
                entry = found.setdefault((collection, key), {"scenes": set(), "speakers": set()})
                if scene:
                    entry["scenes"].add(scene)
                if speaker:
                    entry["speakers"].add(speaker)
    result: Index = {}
    for (collection, key), items in found.items():
        result.setdefault(collection, {})[key] = {"scenes": sorted(items["scenes"]),
                                                  "speakers": sorted(items["speakers"])}
    return result, outside
