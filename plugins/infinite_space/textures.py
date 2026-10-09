"""Infinite Space: which pictures the Textures window lists (``texture_sources.json``).

``.bgd`` (``BGD\\0``, screens: the title logo is ``title.bgd`` and ``TITLE000BG1.bgd``) and ``.obd`` (``OBD\\0``,
menu sprites) share one header: u16 0, u16 32 (bytes a tile), u16 tile bytes / 1024, u16 tile bytes, u16 0,
u16 palettes, u16 palette bytes, u16 map width, u16 map height (in tiles), u16 map bytes (``.bgd``), then u32
offsets at ``0x18``: tiles (4 bits a pixel), palettes (16 BGR555 colours each), the map (``.bgd``: u16 entries,
tile number and palette bank) and the tables after it. ``describe(source folder)`` makes one ``tiles`` entry per
file -- a ``.bgd`` takes the bank of each tile from its map, an ``.obd`` the bank ``OBD_BANKS`` names (else 0) --
and one ``is_tex`` entry per texture ``data/Cg/Texture/*.tex`` (the opening text, the ship plans).
``python -m plugins.infinite_space.textures <source>`` writes the plugin's ``texture_sources.json``.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List

OBD_BANKS = {"T000OBJ.obd": 1}           # the dialogue window and its font use the second bank


def banks(data: bytes, tiles: int) -> str:
    """One hex digit per tile: the bank the first map entry naming the tile uses (``.`` = none)."""
    width, height = struct.unpack_from("<HH", data, 0x12)
    map_at = struct.unpack_from("<I", data, 0x20)[0]
    out = ["."] * tiles
    count = min(width * height, (len(data) - map_at) // 2)
    for (value,) in struct.iter_unpack("<H", data[map_at:map_at + 2 * count]):
        tile = value & 0x3FF
        if tile < tiles and out[tile] == ".":
            out[tile] = f"{value >> 12:x}"
    return "".join(out)


def entry_for(rel: str, data: bytes) -> Dict[str, Any] | None:
    tile_bytes, _zero, _palettes, palette_bytes = struct.unpack_from("<4H", data, 0x0A)
    tiles_at, palette_at = struct.unpack_from("<II", data, 0x18)
    tiles = tile_bytes // 32
    if not tiles:
        return None
    params: Dict[str, Any] = {"bpp": 4, "offset": tiles_at, "tiles": tiles, "per_row": 32,
                              "palette": data[palette_at:palette_at + palette_bytes].hex()}
    name = rel.rsplit("/", 1)[-1]
    if data[:4] == b"BGD\0":
        text = banks(data, tiles)
        params["bank"], params["banks"] = 0, text
    else:
        params["bank"] = OBD_BANKS.get(name, 0)
    kind = "logo" if name.lower().startswith(("title", "logo")) else "menu"
    return {"label": rel.replace("data/Cg/", ""), "kind": kind, "format": "tiles", "path": rel, "params": params}


def describe(source: Path) -> List[Dict[str, Any]]:
    source = Path(source)
    out: List[Dict[str, Any]] = []
    for file in sorted(source.rglob("*")):
        rel = file.relative_to(source).as_posix()
        if not file.is_file():
            continue
        data = file.read_bytes()
        if data[:4] in (b"BGD\0", b"OBD\0"):
            entry = entry_for(rel, data)
            if entry:
                out.append(entry)
        elif rel.endswith(".tex"):
            out.append({"label": rel.replace("data/Cg/", ""), "kind": "menu", "format": "is_tex", "path": rel})
    return out


if __name__ == "__main__":
    found = describe(Path(sys.argv[1]))
    target = Path(__file__).with_name("texture_sources.json")
    target.write_text("[\n" + ",\n".join(json.dumps(e, ensure_ascii=False) for e in found) + "\n]\n", encoding="utf-8")
    print(f"{len(found)} entries -> {target}")
