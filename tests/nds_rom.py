"""Nintendo DS images and NARC archives built in a test: the header, the file name table (folders), the file
allocation table and the file data, as the unpack tests need them. No game bytes."""
import struct
from typing import Dict, List, Tuple

LOGO_CRC = 0xCF56
ROOT_DIR = 0xF000
ARM9 = b"ARM9CODE"


class _Folder:
    def __init__(self, parent: int) -> None:
        self.parent = parent
        self.first = 0
        self.dirs: Dict[str, "_Folder"] = {}
        self.files: Dict[str, bytes] = {}
        self.id = 0


def _align(value: int, unit: int) -> int:
    return (value + unit - 1) // unit * unit


def _tree(files: Dict[str, bytes]) -> _Folder:
    root = _Folder(ROOT_DIR)
    for path, data in files.items():
        *folders, name = path.split("/")
        node = root
        for folder in folders:
            node = node.dirs.setdefault(folder, _Folder(0))
        node.files[name] = data
    return root


def _name_table(root: _Folder) -> Tuple[bytes, List[bytes]]:
    """(the file name table, the file data in file id order)."""
    folders: List[_Folder] = []

    def visit(node: _Folder, parent: int) -> None:
        node.id = ROOT_DIR + len(folders)
        node.parent = parent
        folders.append(node)
        for sub in node.dirs.values():
            visit(sub, node.id)

    visit(root, ROOT_DIR)
    datas: List[bytes] = []
    for node in folders:
        node.first = len(datas)
        datas.extend(node.files.values())
    main = bytearray(8 * len(folders))
    subs = bytearray()
    for index, node in enumerate(folders):
        struct.pack_into("<IHH", main, 8 * index, len(main) + len(subs), node.first, node.parent & 0xFFFF)
        for name in node.files:
            raw = name.encode("ascii")
            subs += bytes([len(raw)]) + raw
        for name, sub in node.dirs.items():
            raw = name.encode("ascii")
            subs += bytes([0x80 | len(raw)]) + raw + struct.pack("<H", sub.id)
        subs += b"\x00"
    return bytes(main + subs), datas


def nds_rom(files: Dict[str, bytes], title: bytes = b"TEST", code: bytes = b"TEST") -> bytes:
    """A cartridge image with ``files`` ({path: bytes}) in its NitroFS, and a game code at 0x0C."""
    fnt, datas = _name_table(_tree(files))
    arm9_at = 0x200
    fnt_at = _align(arm9_at + len(ARM9), 0x200)
    fat_at = _align(fnt_at + len(fnt), 0x200)
    data_at = _align(fat_at + 8 * len(datas), 0x200)
    body, fat = bytearray(), bytearray()
    for data in datas:
        start = data_at + len(body)
        body += data + b"\0" * (-len(data) % 4)
        fat += struct.pack("<II", start, start + len(data))
    rom = bytearray(data_at) + body
    rom[0:12] = title.ljust(12, b"\0")
    rom[0x0C:0x10] = code
    struct.pack_into("<4I", rom, 0x20, arm9_at, 0x2000000, 0x2000000, len(ARM9))
    struct.pack_into("<4I", rom, 0x40, fnt_at, len(fnt), fat_at, len(fat))
    rom[arm9_at:arm9_at + len(ARM9)] = ARM9
    rom[fnt_at:fnt_at + len(fnt)] = fnt
    rom[fat_at:fat_at + len(fat)] = fat
    struct.pack_into("<H", rom, 0x15C, LOGO_CRC)
    return bytes(rom)


def narc(members: List[bytes]) -> bytes:
    """A NARC with its BTAF table, an empty BTNF and the GMIF body (members 4-byte aligned)."""
    fat, body = bytearray(), bytearray()
    for member in members:
        start = len(body)
        body += member + b"\xff" * (-len(member) % 4)
        fat += struct.pack("<II", start, start + len(member))
    btaf = b"BTAF" + struct.pack("<II", 12 + len(fat), len(members)) + bytes(fat)
    btnf = b"BTNF" + struct.pack("<I", 8)
    gmif = b"GMIF" + struct.pack("<I", 8 + len(body)) + bytes(body)
    total = 16 + len(btaf) + len(btnf) + len(gmif)
    return b"NARC" + b"\xfe\xff\x00\x01" + struct.pack("<IHH", total, 16, 3) + btaf + btnf + gmif
