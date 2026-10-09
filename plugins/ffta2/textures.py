"""Final Fantasy Tactics A2: which game pictures with text the Textures window lists (``texture_sources.json``).

- The title logo and the company / licence logos: DS 3D textures in ``effect/common/c_all_title_eu.efx``; the
  auction and world map effects (``effect/common/us/*.efx``) the same way (format ``ffta2_efx``).
- The menus: ``menu/nc_rom/us/nc.a2pak`` (``nc_rom.idx`` + ``nc.pak``, members ``#n``). A member starts with a
  16-byte header: u32 width and height in tiles, u32 bits per pixel (4 / 8), u32 data size. Tile sheets hold
  ``width * height`` 8 x 8 tiles; screen maps hold one u16 per tile (tile in bits 0-9, 16-colour bank in bits
  12-15); a palette member is u32 colours, u32 banks, u32 size and the BGR555 colours (the last 512 bytes).
  The other members are sprite cell tables.

``describe(source folder)`` makes the ``tiles`` entries: every tile sheet, coloured with the last palette
before it, its banks taken from the screen maps that follow it (colours are a guess where several palettes could
fit; writing keeps every pixel index that did not change). ``python -m plugins.ffta2.textures <source>`` writes
the plugin's ``texture_sources.json``.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List

from plugins.ffta2 import a2text

MENU = "menu/nc_rom/us/nc.a2pak"
EFFECTS = (("effect/common/c_all_title_eu.efx", "logo", "Title logo, company and licence logos"),
           ("effect/common/us/c_all_auction.efx", "menu", "Auction effects"),
           ("effect/common/us/c_all_worldmap.efx", "menu", "World map effects"))


def classify(member: bytes) -> str:
    """``tiles``, ``map``, ``palette`` or ``other``."""
    if len(member) < 16:
        return "other"
    width, height, bpp, size = struct.unpack_from("<4I", member, 0)
    if size == len(member) - 16 and bpp in (4, 8) and size == width * height * 8 * bpp:
        return "tiles"
    if size == len(member) - 16 and size == width * height * 2:
        return "map"
    if bpp == 0x200 and len(member) >= 512:
        return "palette"
    return "other"


def menu_entries(blob: bytes) -> List[Dict[str, Any]]:
    _kind, index, pak = a2text.split_file(blob)
    members = a2text.members(index, pak)
    kinds = [classify(m) if m else "empty" for m in members]
    out, palette = [], ""
    for number, member in enumerate(members):
        if kinds[number] == "palette":
            palette = member[-512:].hex()
        if kinds[number] != "tiles":
            continue
        width, height, bpp, _size = struct.unpack_from("<4I", member, 0)
        count = width * height
        banks = ["."] * count
        follow = number + 1
        while follow < len(members) and kinds[follow] != "tiles":
            if kinds[follow] == "map" and bpp == 4:
                entries = len(members[follow]) // 2 - 8
                for value in struct.unpack_from(f"<{entries}H", members[follow], 16):
                    tile = value & 0x3FF
                    if tile < count and banks[tile] == ".":
                        banks[tile] = f"{value >> 12:x}"
            follow += 1
        params: Dict[str, Any] = {"bpp": bpp, "offset": 16, "tiles": count, "per_row": 32}
        if palette:
            params["palette"] = palette
        if bpp == 4:
            params["bank"] = 0
            if any(b != "." for b in banks):
                params["banks"] = "".join(banks)
        out.append({"label": f"Menu sheet {number} (nc.pak)", "kind": "menu", "format": "tiles", "path": MENU,
                    "member": f"#{number}", "params": params})
    return out


def describe(source: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = [{"label": label, "kind": kind, "format": "ffta2_efx", "path": path}
                                 for path, kind, label in EFFECTS]
    menu = Path(source) / MENU
    if menu.is_file():
        out += menu_entries(menu.read_bytes())
    return out


if __name__ == "__main__":
    entries = describe(Path(sys.argv[1]))
    target = Path(__file__).with_name("texture_sources.json")
    target.write_text("[\n" + ",\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n]\n", encoding="utf-8")
    print(f"{len(entries)} entries -> {target}")
