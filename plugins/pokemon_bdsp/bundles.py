"""The English message tables of the Brilliant Diamond / Shining Pearl bundles, as the plugin's JSON files.

Two bundles hold all the English tables: ``Message/english`` and ``Message/common_msbt``. Each holds one serialized
file whose MonoBehaviours named ``english_<table>`` (with a ``labelDataArray``) are the tables. A table's file in the
project is its type tree as JSON (``json.dumps(..., ensure_ascii=False, indent=1)`` and a newline), the same text the
Unity export of ``1_unpack.bat`` writes.
"""
from __future__ import annotations

import json
from typing import Dict, Tuple

from core.unity.serialized import SerializedFile
from core.unity.unityfs import Bundle

MESSAGE_DIR = "Data/StreamingAssets/AssetAssistant/Message/"
MESSAGE_BUNDLES = (MESSAGE_DIR + "english", MESSAGE_DIR + "common_msbt")
LANGUAGE = "english_"
MONOBEHAVIOUR = 114


def open_bundle(data: bytes) -> Tuple[Bundle, SerializedFile]:
    """The bundle and the serialized file of its one ``CAB-`` entry."""
    bundle = Bundle(data)
    if len(bundle.nodes) != 1:
        raise ValueError("a message bundle holds one serialized file")
    return bundle, SerializedFile(bundle.read(bundle.nodes[0].name))


def tables(serialized: SerializedFile) -> Dict[str, int]:
    """Table name -> path id of each English message table of a serialized file."""
    found = {}
    for obj in serialized.objects:
        if obj.class_id != MONOBEHAVIOUR:
            continue
        value = serialized.read(obj.path_id)
        name = value.get("m_Name", "")
        if isinstance(name, str) and name.startswith(LANGUAGE) and "labelDataArray" in value:
            found[name] = obj.path_id
    return found


def table_json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
