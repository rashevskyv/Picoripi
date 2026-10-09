"""Final Fantasy XII: Revenant Wings: which game pictures with text the Textures window lists (``texture_sources.json``).

The pictures are NITRO files: ``*.NCGR`` tiles, ``*.NCLR`` palettes, ``*.NSCR`` screen maps, kept in NARC archives
(the English ``Shellscreen`` packs, the title screen), in ``.dpk`` packs of LZ10-packed NARCs (mission titles,
chapter titles; ``dpk.DpkContainer``) or loose (the English mini maps). ``describe(source folder)`` makes one
``tiles`` entry per NCGR: coloured with the NCLR of the same name (else the archive's first one); a 4-bit sheet
takes its 16-colour banks from the NSCR of the same name (else from every map of the archive). Sprite sheets are
shown in storage order. ``python -m plugins.ff12rw.textures <source>`` writes the plugin's ``texture_sources.json``.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.containers.nitro import NarcContainer

from .dpk import DpkContainer

TITLE = ("data/Shellscreen/title/bg_pack.narc", "data/Shellscreen/title/party_pack.narc",
         "data/Shellscreen/title/title_obj_choice.narc")


def palette(nclr: bytes) -> str:
    """The colours of an NCLR as hex (BGR555, little endian)."""
    size, offset = struct.unpack_from("<II", nclr, 0x20)
    return nclr[0x18 + offset:0x18 + offset + size].hex()


def banks(nscrs: List[bytes], count: int) -> str:
    """One hex digit per tile: the bank the first map entry naming the tile uses (``.`` = none)."""
    out = ["."] * count
    for nscr in nscrs:
        size = struct.unpack_from("<I", nscr, 0x20)[0]
        for (value,) in struct.iter_unpack("<H", nscr[0x24:0x24 + size - size % 2]):
            tile = value & 0x3FF
            if tile < count and out[tile] == ".":
                out[tile] = f"{value >> 12:x}"
    return "".join(out)


def _tiles(ncgr: bytes):
    """``(bits per pixel, tile count)`` of an NCGR."""
    depth = struct.unpack_from("<I", ncgr, 0x1C)[0]
    bpp = 8 if depth == 4 else 4
    size = struct.unpack_from("<I", ncgr, 0x28)[0]
    return bpp, size * 8 // bpp // 64


def entries_for(files: Dict[str, bytes], path: str, prefix: str, label: str, kind: str) -> List[Dict[str, Any]]:
    """Entries for the NCGR files of one archive (``files``: member name -> bytes)."""
    out = []
    nclrs = {name: data for name, data in files.items() if data[:4] == b"RLCN"}
    nscrs = {name: data for name, data in files.items() if data[:4] == b"RCSN"}
    for name, data in files.items():
        if data[:4] != b"RGCN":
            continue
        stem = name.rsplit(".", 1)[0]
        colours: Optional[bytes] = next((d for n, d in nclrs.items() if n.rsplit(".", 1)[0] == stem), None)
        if colours is None and nclrs:
            colours = next(iter(nclrs.values()))
        bpp, count = _tiles(data)
        params: Dict[str, Any] = {}
        if colours is not None:
            params["palette"] = palette(colours)
        if bpp == 4 and nscrs:
            own = [d for n, d in nscrs.items() if n.rsplit(".", 1)[0] == stem]
            text = banks(own or list(nscrs.values()), count)
            if any(c != "." for c in text):
                params["bank"], params["banks"] = 0, text
        entry = {"label": f"{label}: {name}", "kind": kind, "format": "tiles", "path": path,
                 "member": prefix + name, "params": params}
        if not prefix + name:
            entry.pop("member")
        out.append(entry)
    return out


def _kind(path: str) -> str:
    return "logo" if "/title/" in path else "menu"


def describe(source: Path) -> List[Dict[str, Any]]:
    source = Path(source)
    out: List[Dict[str, Any]] = []
    for file in sorted(source.rglob("*")):
        rel = file.relative_to(source).as_posix()
        if not file.is_file() or ("/E/" not in rel and rel not in TITLE):
            continue
        data = file.read_bytes()
        label = rel.replace("data/Shellscreen/", "")
        if data[:4] == b"NARC":
            narc = NarcContainer(data)
            files = {name: narc.read_file(name) for name in narc.list_files()}
            out += entries_for(files, rel, "", label, _kind(rel))
        elif rel.endswith(".dpk") and DpkContainer.can_handle(data):
            pack = DpkContainer(data)
            for member in pack.list_files():
                inner = pack.read_file(member)
                if inner[:4] != b"NARC":
                    continue
                narc = NarcContainer(inner)
                files = {name: narc.read_file(name) for name in narc.list_files()}
                out += entries_for(files, rel, f"{member}/", f"{label} {member}", "menu")
        elif data[:4] == b"RGCN":
            siblings = {f.name: f.read_bytes() for f in file.parent.iterdir()
                        if f.stem == file.stem and f.suffix.upper() in (".NCLR", ".NSCR")}
            siblings[file.name] = data
            for entry in entries_for(siblings, rel, "", label, "map"):
                entry.pop("member", None)
                out.append(entry)
    return out


if __name__ == "__main__":
    found = describe(Path(sys.argv[1]))
    target = Path(__file__).with_name("texture_sources.json")
    target.write_text("[\n" + ",\n".join(json.dumps(e, ensure_ascii=False) for e in found) + "\n]\n", encoding="utf-8")
    print(f"{len(found)} entries -> {target}")
