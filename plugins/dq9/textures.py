"""Dragon Quest IX: which pictures the Textures window lists (``texture_sources.json``).

The pictures with text are Level-5 picture packs (``pac.PacContainer``: ``CHAR`` tiles, ``PALT`` colours, ``SCRN``
maps; a few hold NITRO ``NCGR`` / ``NCLR``) -- loose in ``data/ani`` and ``data/menu`` (the title logo
``data/ani/bg_title.pac``) or as English members (``*_en.pac``) of GPC2 archives -- and English ``*_en.spr``
pictures (``core.texture_formats.dq9_spr``). ``describe(source folder)`` makes one ``tiles`` entry per tile set,
coloured with the pack's palette (the one of the same name first); a 4-bit set takes its 16-colour banks from the
maps of the pack. ``python -m plugins.dq9.textures <source>`` writes the plugin's ``texture_sources.json``.
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List

from .gpc2 import Gpc2
from .pac import PacContainer

ENGLISH = re.compile(r"_en\.(pac|spr)$")


def _stem(name: str) -> str:
    return re.sub(r"(#\d+)?$", "", name).rsplit(".", 1)[0]


def _palette(member: bytes) -> str:
    if member[:4] == b"PALT":
        size = struct.unpack_from("<I", member, 8)[0]
        return member[0x10:0x10 + size].hex()
    size, offset = struct.unpack_from("<II", member, 0x20)        # NITRO NCLR
    return member[0x18 + offset:0x18 + offset + size].hex()


def _banks(maps: List[bytes], count: int) -> str:
    out = ["."] * count
    for screen in maps:
        if screen[:4] == b"SCRN":
            size, at = struct.unpack_from("<I", screen, 0x0C)[0], 0x10
        else:                                                       # NITRO NSCR
            size, at = struct.unpack_from("<I", screen, 0x20)[0], 0x24
        for (value,) in struct.iter_unpack("<H", screen[at:at + size - size % 2]):
            tile = value & 0x3FF
            if tile < count and out[tile] == ".":
                out[tile] = f"{value >> 12:x}"
    return "".join(out)


def pack_entries(pack: PacContainer, path: str, prefix: str, label: str) -> List[Dict[str, Any]]:
    files = {name: pack.read_file(name) for name in pack.list_files()}
    palettes = {n: d for n, d in files.items() if d[:4] in (b"PALT", b"RLCN")}
    maps = {n: d for n, d in files.items() if d[:4] in (b"SCRN", b"RCSN")}
    out = []
    for name, data in files.items():
        if data[:4] == b"CHAR":
            bpp = 8 if data[0x0A] == 1 else 4
            size = struct.unpack_from("<I", data, 0x0C)[0]
            params: Dict[str, Any] = {"bpp": bpp, "offset": 0x10, "tiles": size * 8 // bpp // 64, "per_row": 32}
        elif data[:4] == b"RGCN":
            depth = struct.unpack_from("<I", data, 0x1C)[0]
            bpp = 8 if depth == 4 else 4
            params = {}
        else:
            continue
        count = params.get("tiles") or struct.unpack_from("<I", data, 0x28)[0] * 8 // bpp // 64
        colours = next((d for n, d in palettes.items() if _stem(n).split("_")[0] == _stem(name).split("_")[0]), None)
        colours = colours or next(iter(palettes.values()), None)
        if colours is not None:
            params["palette"] = _palette(colours)
        if bpp == 4 and maps:
            text = _banks(list(maps.values()), count)
            if any(c != "." for c in text):
                params["bank"], params["banks"] = 0, text
        out.append({"label": f"{label}: {name}", "kind": "menu", "format": "tiles", "path": path,
                    "member": prefix + name, "params": params})
    return out


def describe(source: Path) -> List[Dict[str, Any]]:
    source = Path(source)
    out: List[Dict[str, Any]] = []
    for file in sorted(source.rglob("*")):
        rel = file.relative_to(source).as_posix()
        label = rel.replace("data/", "")
        if rel.endswith(".pac"):
            data = file.read_bytes()
            if PacContainer.can_handle(data):
                out += pack_entries(PacContainer(data), rel, "", label)
        elif rel.endswith(".gp2"):
            archive = Gpc2(file.read_bytes())
            for member in archive.names:
                if not ENGLISH.search(member):
                    continue
                inner = archive.read(member)
                if member.endswith(".spr"):
                    out.append({"label": f"{label}: {member}", "kind": "menu", "format": "dq9_spr", "path": rel,
                                "member": member})
                elif PacContainer.can_handle(inner):
                    out += pack_entries(PacContainer(inner), rel, f"{member}/", f"{label} {member}")
    for entry in out:
        if re.search(r"bg_up|bg_title|title_|nintendo", entry["path"] + entry.get("member", "")):
            entry["kind"] = "logo"
    return out


if __name__ == "__main__":
    found = describe(Path(sys.argv[1]))
    target = Path(__file__).with_name("texture_sources.json")
    target.write_text("[\n" + ",\n".join(json.dumps(e, ensure_ascii=False) for e in found) + "\n]\n", encoding="utf-8")
    print(f"{len(found)} entries -> {target}")
