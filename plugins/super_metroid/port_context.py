"""Offline translation context for Super Metroid from the sm_rewrite C code: where each text item is shown.

Run once per port revision; the plugin ships the JSON and only reads it.

    python -m plugins.super_metroid.port_context --port <sm_rewrite clone> --text <workspace>/source/text.json
        --out plugins/super_metroid/context.json

Every item of ``text.json`` carries ``symbol``: the name the port gives it (``kMessageBox_2_Missile``,
``addr_kMenuTilemap_SamusData``, ``addr_kCinematicBgObjectDef_8BCF3F``) or the ROM address of its packed block
(``0x978DF4``). Each use of the symbol in ``src/*.c`` gives a source line and the function around it. The intro
pages are first-person narration by Samus (the only speaker in the game's text).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List

from plugins.common.zelda64_context import _FUNC_RE, _balanced, _strip_comments

NARRATOR = "Samus"
# Items whose symbol the code never names: the message boxes of items picked up through PLM parameters.
FALLBACK = {"kMessageBox_": r"DisplayMessageBox\(plmp\[2\]\)"}


def _find(sources: Dict[str, str], bodies: List, regex: str) -> List:
    """(``src/file:line``, function) of every match inside a function body."""
    found, pattern = [], re.compile(regex, re.I)
    for name, src in sources.items():
        for m in pattern.finditer(src):
            func = next((f for file, f, s, e in bodies if file == name and s <= m.start() < e), None)
            if func:
                found.append((f"src/{name}:{src.count(chr(10), 0, m.start()) + 1}", func))
    return found


def scan(port: Path, items: List[Dict]) -> Dict[str, Dict]:
    """``{item id: {"refs", "functions"[, "speaker"]}}``."""
    sources = {p.name: _strip_comments(p.read_text(encoding="utf-8", errors="replace"))
               for p in sorted((port / "src").glob("*.c"))}
    bodies = []      # (file, function, start, end) of every function body
    for name, src in sources.items():
        for func in _FUNC_RE.finditer(src):
            start = func.end() - 1
            bodies.append((name, func.group(1), start, _balanced(src, start)))
    uses: Dict[str, List] = {}
    out: Dict[str, Dict] = {}
    for item in items:
        symbol = item.get("symbol") or ""
        if symbol not in uses:
            found = _find(sources, bodies, rf"(?<![\w]){re.escape(symbol)}(?![\w])") if symbol else []
            prefix = next((p for p in FALLBACK if symbol.startswith(p)), None)
            uses[symbol] = found or (_find(sources, bodies, FALLBACK[prefix]) if prefix else [])
        entry: Dict = {}
        if uses[symbol]:
            entry["refs"] = [ref for ref, _f in uses[symbol]]
            entry["functions"] = list(dict.fromkeys(f for _r, f in uses[symbol]))
        if item["id"].startswith("intro."):
            entry["speaker"] = NARRATOR
        if entry:
            out[item["id"]] = entry
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", required=True, type=Path, help="sm_rewrite clone")
    parser.add_argument("--text", required=True, type=Path, help="the workspace's source/text.json")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        revision = subprocess.run(["git", "-C", str(args.port), "rev-parse", "--short", "HEAD"],
                                  capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unknown"
    doc = json.loads(args.text.read_text(encoding="utf-8"))
    items = [item for group in doc["groups"] for item in group["items"]]
    found = scan(args.port, items)
    document = {"source": f"enderandrew/sm_rewrite {revision}", "items": found}
    args.out.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{sum(1 for v in found.values() if v.get('refs'))} of {len(items)} items have a code reference -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
