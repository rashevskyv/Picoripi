"""A small GameCube disc for the unpack tests: ``files`` (paths under ``files/``) in an FST, ``sys/main.dol``
(one 0x20-byte text section) and an empty apploader. Nothing from a real game is in it."""
import struct
from typing import Dict

GC_MAGIC = 0xC2339F3D
WII_MAGIC = 0x5D1C9EA3
DOL = bytearray(0x120)
struct.pack_into(">I", DOL, 0, 0x100)
struct.pack_into(">I", DOL, 0x90, 0x20)
DOL = bytes(DOL)


def build_disc(files: Dict[str, bytes], game_id: bytes = b"TSTE01", wii: bool = False) -> bytes:
    tree: dict = {}
    for path, data in files.items():
        *dirs, name = path.split("/")
        node = tree
        for part in dirs:
            node = node.setdefault(part, {})
        node[name] = data
    entries, names, placed = [None], bytearray(), []

    def add(children: dict, parent: int) -> None:
        for name, node in children.items():
            index, name_at = len(entries), len(names)
            names.extend(name.encode() + b"\0")
            entries.append(None)
            if isinstance(node, dict):
                add(node, index)
                entries[index] = (1 << 24 | name_at, parent, len(entries))
            else:
                placed.append((index, node, name_at))

    add(tree, 0)
    entries[0] = (1 << 24, 0, len(entries))
    fst_at = 0x2800
    fst_size = 12 * len(entries) + len(names)
    at = fst_at + fst_size
    for index, data, name_at in placed:
        entries[index] = (name_at, at, len(data))
        at += (len(data) + 3) & ~3
    image = bytearray(at)
    image[0:6] = game_id
    struct.pack_into(">I", image, 0x18 if wii else 0x1C, WII_MAGIC if wii else GC_MAGIC)
    struct.pack_into(">III", image, 0x420, 0x2600, fst_at, fst_size)
    image[0x2600:0x2600 + len(DOL)] = DOL
    image[fst_at:fst_at + fst_size] = b"".join(struct.pack(">III", *e) for e in entries) + bytes(names)
    for index, data, _name_at in placed:
        start = entries[index][1]
        image[start:start + len(data)] = data
    return bytes(image)
