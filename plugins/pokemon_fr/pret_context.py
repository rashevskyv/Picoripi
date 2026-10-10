"""Translation context of a generation III decompilation: which person or sign shows each text of a map.

A map folder (``data/maps/LittlerootTown``) holds ``scripts.inc`` (the texts and the scripts that show them)
and ``map.json`` (the map's people ``object_events`` and signs ``bg_events``, each naming the script that runs
when the player talks to it). A text's scripts are the scripts that name its label (``pret_text.references``);
its speakers are the people whose ``script`` is one of them: ``OBJ_EVENT_GFX_BOY_2`` -> ``Boy 2``.
"""
from __future__ import annotations

import json
from typing import Dict, List


_BG = {"sign": "Sign", "hidden_item": "Hidden item", "secret_base": "Secret base"}


def pretty(constant: str, drop: str = "OBJ_EVENT_GFX_") -> str:
    name = constant[len(drop):] if constant.startswith(drop) else constant
    return name.replace("_", " ").strip().title()


def speakers_of_scripts(map_json: str) -> Dict[str, List[str]]:
    """``{script label: [speaker names]}`` from the text of a ``map.json``."""
    try:
        data = json.loads(map_json)
    except ValueError:
        return {}
    out: Dict[str, List[str]] = {}
    for event in data.get("object_events") or []:
        script = event.get("script")
        if script and script != "0x0":
            out.setdefault(script, [])
            who = pretty(str(event.get("graphics_id") or ""))
            if who and who not in out[script]:
                out[script].append(who)
    for event in data.get("bg_events") or []:
        script = event.get("script")
        if script:
            who = _BG.get(str(event.get("type")), "Sign")
            out.setdefault(script, [])
            if who not in out[script]:
                out[script].append(who)
    return out
