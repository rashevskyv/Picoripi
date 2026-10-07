"""Offline translation context for A Link to the Past from the snesrev/zelda3 C code: who shows each message, where.

Run once per port revision; the plugin ships the JSON and only reads it.

    python -m plugins.zelda_lttp.port_context --port <zelda3 clone> --out plugins/zelda_lttp/context.json

A message index is the line of the port's ``dialogue.txt`` minus one. Found in ``src/*.c``:
message ids passed to the message calls (``Sprite_ShowMessageUnconditional`` and friends) or assigned to
``dialogue_message_index``, hex or decimal literals outside ``[...]``, plus every entry of a ``*Msg*`` array
the same function reads (``kWishPondMsgs[...]``). Missed: ids held in plain variables set elsewhere.
The speaker is the sprite whose function shows the line (``Sprite_1F_SickKid`` -> ``SickKid``,
``Zelda_InCell`` -> ``Zelda``); lines shown from several sprites get no single speaker.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from plugins.common.zelda64_context import _ARRAY_RE, _FUNC_RE, _balanced, _strip_comments

MESSAGE_COUNT = 397
_CALL_RE = re.compile(r"\b(Sprite_ShowMessageUnconditional|Sprite_ShowSolicitedMessage|Sprite_ShowMessageMinimal|"
                      r"Sprite_ShowMessageOnContact|Sprite_TutorialGuard_ShowMessageOnContact|"
                      r"Attract_ShowTimedTextMessage)\s*\(|\bdialogue_message_index\s*=(?!=)")
_INT_RE = re.compile(r"(?<![\w.])(0x[0-9A-Fa-f]+|\d+)\b")
# Literals compared, masked or shifted (``x == 0 ? 0x163 : 0x17f``, ``0x17a + (n & 1)``) are not message ids.
_OPERAND_RE = re.compile(r"(?:==|!=|<=|>=|<<|>>|[<>&|^])\s*(?:0x[0-9A-Fa-f]+|\d+)\b"
                         r"|\b(?:0x[0-9A-Fa-f]+|\d+)\s*(?:==|!=|<=|>=|<<|>>|[<>&|^])")
_MSG_ARRAY_RE =re.compile(r"\b(k\w*(?:Msg|Message)\w*)\s*\[")
_SPRITE_FILES = {"sprite_main.c", "sprite.c", "tagalong.c"}
# What a file's messages are when no sprite shows them.
ROLES = {"ancilla.c": "ItemGet", "attract.c": "Narration", "ending.c": "Narration", "messaging.c": "Menu"}


def _ints(text: str) -> List[int]:
    """Literals outside brackets (an index is not a message id)."""
    while True:
        stripped = re.sub(r"\[[^\[\]]*\]", " ", text)
        if stripped == text:
            break
        text = stripped
    text = _OPERAND_RE.sub(" ", text)
    return [int(v, 0) for v in _INT_RE.findall(text)]


def speaker_of(function: str) -> str:
    """``Sprite_1F_SickKid`` -> ``SickKid``; ``Zelda_InCell`` -> ``Zelda``; ``Sprite_Witch`` -> ``Witch``."""
    parts = function.split("_")
    if parts[0] == "Sprite":
        parts = parts[1:]
    if parts and re.fullmatch(r"[0-9A-F]{2}", parts[0]):
        parts = parts[1:]
    return parts[0] if parts else function


def scan(port: Path) -> Dict[str, Dict]:
    """``{message index: {"refs", "functions", "speakers", "role"}}`` from the port's ``src/*.c``."""
    sources = {p.name: _strip_comments(p.read_text(encoding="utf-8", errors="replace"))
               for p in sorted((port / "src").glob("*.c"))}
    arrays: Dict[str, List[int]] = {}
    for src in sources.values():
        for m in _ARRAY_RE.finditer(src):
            arrays.setdefault(m.group(1), _ints(src[m.end() - 1:_balanced(src, m.end() - 1)]))
    found: Dict[int, Dict[str, list]] = defaultdict(lambda: {"refs": [], "functions": [], "files": []})
    for name, src in sources.items():
        for func in _FUNC_RE.finditer(src):
            start = func.end() - 1
            body = src[start:_balanced(src, start)]
            ids: Dict[int, int] = {}
            for call in _CALL_RE.finditer(body):
                if call.group(1):
                    args = body[call.end() - 1:_balanced(body, call.end() - 1)]
                else:
                    args = body[call.end():body.find(";", call.end())]
                at = src.count("\n", 0, start + call.start()) + 1
                for value in _ints(args):
                    ids.setdefault(value, at)
            if not ids:
                continue
            for array in _MSG_ARRAY_RE.findall(body):
                at = src.count("\n", 0, start + body.find(array)) + 1
                for value in arrays.get(array, []):
                    ids.setdefault(value, at)
            for value, line in ids.items():
                if 0 <= value < MESSAGE_COUNT:
                    entry = found[value]
                    if func.group(1) not in entry["functions"]:
                        entry["functions"].append(func.group(1))
                        entry["refs"].append(f"src/{name}:{line}")
                        entry["files"].append(name)
    out = {}
    for index in sorted(found):
        entry = found[index]
        speakers = sorted({speaker_of(f) for f, file in zip(entry["functions"], entry["files"]) if file in _SPRITE_FILES})
        roles = {ROLES[file] for file in entry["files"] if file in ROLES}
        item = {"refs": entry["refs"], "functions": entry["functions"]}
        if speakers:
            item["speakers"] = speakers
        if len(roles) == 1 and not speakers:
            item["role"] = roles.pop()
        out[str(index)] = item
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", required=True, type=Path, help="snesrev/zelda3 clone")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        revision = subprocess.run(["git", "-C", str(args.port), "rev-parse", "--short", "HEAD"],
                                  capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unknown"
    messages = scan(args.port)
    document = {"source": f"snesrev/zelda3 {revision}", "messages": messages}
    args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(messages)} of {MESSAGE_COUNT} messages have a code reference -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
