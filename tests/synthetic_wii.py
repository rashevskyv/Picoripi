"""A synthetic Wii disc for the tests: fake keys, fake files, one DATA partition, encrypted with a fake title key.

The hash blocks are not valid (the writer tests seal a disc before they check hashes). Nothing from a real game is in it.
"""
import struct

from Crypto.Cipher import AES

from core.containers import wii_disc

MAGIC = 0x5D1C9EA3
PART, TMD_AT, TMD_SIZE, H3_AT, DATA_AT = 0x50000, 0x2C0, 0x208, 0x8000, 0x20000
DOL_AT, FST_AT, FILES_AT = 0x3000, 0x8000, 0x10000
CLUSTER_DATA = 0x7C00
TITLE_ID = b"00010000"
COMMON = bytes(range(16))
TITLE = bytes(range(100, 116))


def _encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).encrypt(data)


def _fst(paths: dict) -> bytes:
    """The file system table of the files ``{path: (offset, size)}``: a folder entry per folder, then the files."""
    tree: dict = {}
    for path in paths:
        node = tree
        parts = path.split("/")
        for folder in parts[:-1]:
            node = node.setdefault(folder, {})
        node[parts[-1]] = path
    entries = [[1 << 24, 0, 0]]
    names = bytearray(b"\0")

    def name_at(text: str) -> int:
        at = len(names)
        names.extend(text.encode("ascii") + b"\0")
        return at

    def emit(folder: dict, parent: int) -> None:
        for key in sorted(folder):
            value = folder[key]
            if isinstance(value, dict):
                index = len(entries)
                entries.append([1 << 24 | name_at(key), parent, 0])
                emit(value, index)
                entries[index][2] = len(entries)
            else:
                offset, size = paths[value]
                entries.append([name_at(key), offset >> 2, size])

    emit(tree, 0)
    entries[0][2] = len(entries)
    table = b"".join(struct.pack(">III", *e) for e in entries)
    return table + bytes(names) + bytes(-(len(table) + len(names)) % 4)


def make_disc(path, files: dict, game_id: bytes = b"RZZP8P", common: bytes = COMMON, title: bytes = TITLE) -> str:
    """A Wii ISO with one DATA partition: ``files`` {path: bytes} in its file system, encrypted with ``title``."""
    layout, cursor = {}, FILES_AT
    for rel in sorted(files):
        layout[rel] = (cursor, len(files[rel]))
        cursor += len(files[rel]) + (-len(files[rel]) % 0x20)
    fst = _fst(layout)
    assert FST_AT + len(fst) <= FILES_AT
    clusters = -(-cursor // CLUSTER_DATA) + 8             # spare clusters at the end, as retail discs have
    plain = bytearray(clusters * CLUSTER_DATA)
    boot = bytearray(0x440)
    boot[:6] = game_id
    struct.pack_into(">I", boot, 0x18, MAGIC)
    struct.pack_into(">III", boot, 0x420, DOL_AT >> 2, FST_AT >> 2, len(fst) >> 2)
    plain[:0x440] = boot
    plain[FST_AT:FST_AT + len(fst)] = fst
    for rel, data in files.items():
        offset = layout[rel][0]
        plain[offset:offset + len(data)] = data
    data_view = bytearray(clusters * 0x8000)
    iv_zero = bytes(16)
    for c in range(clusters):
        hashes = _encrypt(title, iv_zero, bytes(0x400))
        data = _encrypt(title, hashes[0x3D0:0x3E0], bytes(plain[c * CLUSTER_DATA:(c + 1) * CLUSTER_DATA]))
        data_view[c * 0x8000:(c + 1) * 0x8000] = hashes + data
    image = bytearray(PART + DATA_AT + len(data_view))
    image[:6] = game_id
    struct.pack_into(">I", image, 0x18, MAGIC)
    struct.pack_into(">II", image, 0x40000, 1, 0x40020 >> 2)
    struct.pack_into(">II", image, 0x40020, PART >> 2, 0)
    header = PART
    image[header + 0x1BF:header + 0x1CF] = _encrypt(common, TITLE_ID + bytes(8), title)
    image[header + 0x1DC:header + 0x1E4] = TITLE_ID
    struct.pack_into(">II", image, header + 0x2A4, TMD_SIZE, TMD_AT >> 2)
    struct.pack_into(">I", image, header + 0x2B4, H3_AT >> 2)
    struct.pack_into(">I", image, header + 0x2B8, DATA_AT >> 2)
    struct.pack_into(">I", image, header + 0x2BC, (clusters * 0x8000) >> 2)
    image[PART + TMD_AT:PART + TMD_AT + TMD_SIZE] = bytes(TMD_SIZE)
    image[PART + DATA_AT:PART + DATA_AT + len(data_view)] = data_view
    with open(path, "wb") as out:
        out.write(image)
    return str(path)


def read_disc(path: str, common: bytes = COMMON) -> dict:
    with open(path, "rb") as stream:
        reader = wii_disc.WiiImage(stream, common)
        entries = {e.path[len("files/"):]: e for e in reader.entries() if e.path.startswith("files/")}
        return {rel: reader.read(entry) for rel, entry in entries.items()}
