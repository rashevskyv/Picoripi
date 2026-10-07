"""Where the colours of the game's text pictures come from; writes ``texture_sources.json``.

    python -m plugins.zelda_fsae.palettes <workspace source folder>

The tiles hold palette indices; the palettes and the bank of each tile are elsewhere in the game:

- ``subtask_eu_en.cmp`` sheets are sprites: the cell files (NCER) of ``subtask.cmp`` give each tile's 16-colour
  bank (attribute 2 of the sprite that covers it, 2D mapping, 32 tiles a row), the NCLR next to them the colours.
  #0 and #3 are drawn by cells #27 (banks 7-11: one per player and a grey one; the sheet shows bank 11),
  #1 by cells #24 (the sheet starts 256 tiles into that VRAM, after ``subtask.cmp`` #23), #2 by cells #29.
- ``zeldat*.bin`` sheets are loaded by the engine's graphics groups (ARM9 tables of ``zeldat`` entry, VRAM
  address): a background sheet's tile banks come from the map loaded with it (title logo #502: map #503;
  copyright #14: map #489, char base 0x601C000; CHOOSE A STAGE #7: map #448), the colours from the palette
  entry the engine loads for that screen (#53 title, #94 the shared bank 0 of the area palettes).
- Sprites of the engine (area plates, GAME OVER letters, PLEASE WAIT, player marks, Back, script lettering)
  use the sprite palette ``zeldat.bin`` #2 (5 banks: one per player and a grey one); which bank a sprite takes
  is set by code, so the sheets show the grey bank 4 (plates, letters, lettering) or bank 0. Not proven in a
  running game.

``texture_sources.json`` is this module's output (``DESCRIPTORS`` plus the colours); the real-data test checks
that the file matches the game files.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from plugins.zelda_fsae.packs import CmpPack, ZeldatPack

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "texture_sources.json"
# OBJ sizes in tiles by (shape, size).
_OBJ = {(0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8), (1, 0): (2, 1), (1, 1): (4, 1),
        (1, 2): (4, 2), (1, 3): (8, 4), (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8)}

# label, kind, path, member, layout params, colours: ("nclr", cmp member) | ("zeldat", entry) plus a bank rule:
# ("ncer", cmp member, first VRAM tile, default bank) | ("map", zeldat map entry, first map tile) | ("bank", n)
DESCRIPTORS: List[Dict[str, Any]] = [
    dict(label="Keyboard keys, PRESS A (subtask_eu_en #0)", kind="menu", path="subtask_eu_en.cmp", member="#0",
         colours=("nclr", "#31"), banks=("bank", 11)),
    dict(label="Buttons: Begin, Help, OK, Recruit Friends (subtask_eu_en #1)", kind="menu", path="subtask_eu_en.cmp",
         member="#1", colours=("nclr", "#26"), banks=("ncer", "#24", 256, 0)),
    dict(label="File select, multiplayer (subtask_eu_en #2)", kind="menu", path="subtask_eu_en.cmp", member="#2",
         colours=("nclr", "#31"), banks=("ncer", "#29", 0, 0)),
    dict(label="Stage buttons and area names (subtask_eu_en #3)", kind="area_card", path="subtask_eu_en.cmp",
         member="#3", colours=("nclr", "#31"), banks=("bank", 11)),
    dict(label="Player marks, signal (subtask_eu_en #4)", kind="hud", path="subtask_eu_en.cmp", member="#4",
         colours=("nclr", "#31"), banks=("bank", 7)),
    dict(label="PLEASE WAIT", kind="menu", path="zeldat_eu_en.bin", member="#1", params={"cell": [4, 2], "per_row": 8},
         colours=("zeldat", 2), banks=("bank", 0)),
    dict(label="Stage select: area name plates", kind="area_card", path="zeldat_eu_en.bin",
         member="{#2,#3,#4,#5,#6,#8,#9}", params={"cell": [4, 2], "per_row": 8}, colours=("zeldat", 2),
         banks=("bank", 4)),
    dict(label="Stage select: CHOOSE A STAGE", kind="menu", path="zeldat_eu_en.bin", member="#7",
         params={"per_row": 32}, colours=("zeldat", 94), banks=("map", 448, 704)),
    # GAME OVER: the same 128 tiles as 32x32 letters (8 cells, the last one empty) and as 16x32 slots (16): the
    # letter table in main.arm9 (game_over.py) says which tiles and which size each letter takes.
    dict(label="GAME OVER letters", kind="menu", path="zeldat_eu_en.bin", member="#10",
         params={"textures": [{"name": "32x32", "cell": [4, 4], "per_row": 8},
                              {"name": "16x32", "cell": [2, 4], "per_row": 16}]},
         colours=("zeldat", 2), banks=("bank", 4)),
    dict(label="Player marks (P1-P4, YOU)", kind="hud", path="zeldat_eu_en.bin", member="#11", params={"per_row": 16},
         colours=("zeldat", 2), banks=("bank", 0)),
    dict(label="Copyright line (title screen)", kind="title_screen", path="zeldat_eu_en.bin", member="#14",
         params={"per_row": 16}, colours=("zeldat", 53), banks=("map", 489, 128, 3)),
    dict(label="Back button", kind="menu", path="zeldat_eu_en.bin", member="#16", params={"cell": [4, 4], "per_row": 6},
         colours=("zeldat", 2), banks=("bank", 0)),
    dict(label="Script lettering", kind="title_screen", path="zeldat_eu_en.bin", member="#17",
         params={"cell": [8, 4], "per_row": 4}, colours=("zeldat", 2), banks=("bank", 4)),
    dict(label="Title logo (ANNIVERSARY)", kind="title_screen", path="zeldat.bin", member="#502",
         params={"per_row": 32}, colours=("zeldat", 53), banks=("map", 503, 0)),
]


def nclr_colours(data: bytes) -> bytes:
    size, offset = struct.unpack_from("<II", data, 0x20)
    return data[0x18 + offset:0x18 + offset + size]


def ncer_banks(data: bytes, first: int, count: int) -> Dict[int, int]:
    """Sheet tile -> bank, from the sprites of an NCER (2D mapping, 32 tiles a row); the first sprite wins."""
    cells, bank_attr, offset = struct.unpack_from("<HHI", data, 0x18)
    base = 0x18 + offset
    entry = 16 if bank_attr == 1 else 8
    found: Dict[int, int] = {}
    for cell in range(cells):
        sprites, _attr, at = struct.unpack_from("<HHI", data, base + entry * cell)
        for k in range(sprites):
            a0, a1, a2 = struct.unpack_from("<3H", data, base + entry * cells + at + 6 * k)
            width, height = _OBJ[(a0 >> 14, a1 >> 14)]
            for y in range(height):
                for x in range(width):
                    tile = (a2 & 0x3FF) + y * 32 + x - first
                    if 0 <= tile < count:
                        found.setdefault(tile, a2 >> 12)
    return found


def map_banks(data: bytes, first: int, count: int) -> Dict[int, int]:
    """Sheet tile -> bank, from a background map (u16: tile, flips, bank in the top 4 bits)."""
    found: Dict[int, int] = {}
    for (value,) in struct.iter_unpack("<H", data):
        tile = (value & 0x3FF) - first
        if 0 <= tile < count:
            found.setdefault(tile, value >> 12)
    return found


def _tiles(data: bytes, params: Dict[str, Any]) -> int:
    from core.texture_formats import tiles
    return tiles._entries(data, params)[0]["tiles"]


def build(source: Path) -> List[Dict[str, Any]]:
    """The descriptors with ``palette``, ``bank`` and ``banks`` read from the game files in ``source``."""
    subtask = CmpPack((source / "subtask.cmp").read_bytes())
    zeldat = ZeldatPack((source / "zeldat.bin").read_bytes())
    out = []
    for spec in DESCRIPTORS:
        params: Dict[str, Any] = dict(spec.get("params") or {})
        kind, which = spec["colours"]
        colours = nclr_colours(subtask.read_file(which)) if kind == "nclr" else zeldat.read_file(f"#{which}")
        params["palette"] = colours.hex()
        rule = spec["banks"]
        found: Optional[Dict[int, int]] = None
        if rule[0] == "bank":
            params["bank"] = rule[1]
        else:
            first_member = spec["member"].strip("{}").split(",")[0]
            pack = CmpPack if spec["path"].endswith(".cmp") else ZeldatPack
            count = _tiles(pack((source / spec["path"]).read_bytes()).read_file(first_member), params)
            if rule[0] == "ncer":
                found = ncer_banks(subtask.read_file(rule[1]), rule[2], count)
                params["bank"] = rule[3]
            else:
                found = map_banks(zeldat.read_file(f"#{rule[1]}"), rule[2], count)
                params["bank"] = rule[3] if len(rule) > 3 else 0
            params["banks"] = "".join(f"{found[t]:x}" if t in found else "." for t in range(count)).rstrip(".")
        out.append({"label": spec["label"], "kind": spec["kind"], "format": "tiles", "path": spec["path"],
                    "member": spec["member"], "params": params})
    return out


def write(descriptors: List[Dict[str, Any]], path: Path = OUTPUT) -> None:
    lines = [json.dumps(d, ensure_ascii=False) for d in descriptors]
    text = "[\n  " + ",\n  ".join(lines) + "\n]\n"
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


if __name__ == "__main__":
    write(build(Path(sys.argv[1])))
    print(f"wrote {OUTPUT}")
