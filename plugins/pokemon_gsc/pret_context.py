"""Translation context of pret map files: which person, sign or trainer shows each text of a map.

A map file (``maps/Route30.asm``) lists its people (``object_event ..., SPRITE_YOUNGSTER, ..., Script, event``),
its signs (``bg_event x, y, BGEVENT_READ, Script``) and its trainers (``trainer YOUNGSTER, JOEY1, event,
SeenText, BeatenText, ...``). A script is the lines from its global label to the next one; every unit label it
names is a text it shows. So a text's speaker is the sprite (``Youngster``), trainer (``Youngster Joey``) or
``Sign`` whose script names it; its conversation is that script.
"""
from __future__ import annotations

import re
from typing import Dict, List, Set

from .pret_text import split_comment

_WORD_RE = re.compile(r"[A-Za-z_.][\w.]*")
_GLOBAL_LABEL_RE = re.compile(r"^([A-Za-z_]\w*):{1,2}")


def _pretty(constant: str, drop: str = "") -> str:
    """``SPRITE_COOLTRAINER_F`` -> ``Cooltrainer F``; ``JOEY1`` -> ``Joey``."""
    name = constant[len(drop):] if drop and constant.startswith(drop) else constant
    name = re.sub(r"\d+$", "", name).replace("_", " ").strip()
    return name.title()


def _args(rest: str) -> List[str]:
    return [part.strip() for part in rest.split(",")]


def map_context(text: str, labels: Set[str]) -> Dict[str, Dict[str, List[str]]]:
    """``{text label: {"speakers": [...], "scripts": [...]}}`` for the unit labels ``labels`` of one file."""
    scripts: Dict[str, Set[str]] = {}          # script label -> texts it names
    speakers_of_script: Dict[str, Set[str]] = {}
    trainer_texts: Dict[str, str] = {}         # text label -> trainer
    current = ""
    for line in text.split("\n"):
        code = split_comment(line)[0]
        found = _GLOBAL_LABEL_RE.match(code)
        if found:
            current = found.group(1)
            code = code[found.end():]
        words = code.split(None, 1)
        if not words:
            continue
        cmd, rest = words[0], (words[1] if len(words) > 1 else "")
        if cmd == "object_event":
            args = _args(rest)
            if len(args) >= 12:
                speakers_of_script.setdefault(args[11], set()).add(_pretty(args[2], "SPRITE_"))
        elif cmd == "bg_event":
            args = _args(rest)
            if len(args) >= 4:
                speakers_of_script.setdefault(args[3], set()).add("Sign" if "READ" in args[2] else "Hidden item")
        elif cmd == "trainer":
            args = _args(rest)
            if len(args) >= 5:
                who = f"{_pretty(args[0])} {_pretty(args[1])}".strip()
                for name in args[3:]:
                    if name in labels:
                        trainer_texts[name] = who
        if current:
            for word in _WORD_RE.findall(code):
                if word in labels:
                    scripts.setdefault(current, set()).add(word)
    result: Dict[str, Dict[str, List[str]]] = {}
    for script, texts in scripts.items():
        for label in texts:
            entry = result.setdefault(label, {"speakers": [], "scripts": []})
            if script != label and script not in entry["scripts"]:
                entry["scripts"].append(script)
            for who in sorted(speakers_of_script.get(script, ())):
                if who not in entry["speakers"]:
                    entry["speakers"].append(who)
    for label, who in trainer_texts.items():
        result.setdefault(label, {"speakers": [], "scripts": []})["speakers"] = [who]
    return result
