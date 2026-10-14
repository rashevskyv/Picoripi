"""A flat RARC archive (one root directory, no sub-folders) for the unit tests. Nothing from a real game is in it."""
import struct
from typing import Dict


def _align(value: int, to: int = 0x20) -> int:
    return (value + to - 1) // to * to


def build_rarc(files: Dict[str, bytes]) -> bytes:
    """A RARC of ``files`` (names without a folder), laid out as the reader expects: header, data header, one root
    node, the file entries, the string table, then the file data, each file aligned to 32 bytes."""
    names = list(files)
    count = len(names)
    strings = bytearray(b"ROOT\0")
    name_at = {}
    for name in names:
        name_at[name] = len(strings)
        strings += name.encode("ascii") + b"\0"
    node_at, entries_at = 0x40, 0x50
    strings_at = entries_at + 20 * count
    data_at = _align(strings_at + len(strings))
    data = bytearray()
    offsets = {}
    for name in names:
        offsets[name] = len(data)
        data += files[name] + bytes(_align(len(files[name])) - len(files[name]))
    file_size = data_at + len(data)
    out = bytearray(file_size)
    struct.pack_into(">4sIIIIIII", out, 0, b"RARC", file_size, 0x20, data_at - 0x20, len(data), len(data), 0, 0)
    struct.pack_into(">IIIIIIHBBI", out, 0x20, 1, node_at - 0x20, count, entries_at - 0x20,
                     len(strings), strings_at - 0x20, count, 1, 0, 0)
    struct.pack_into(">4sIHHI", out, node_at, b"ROOT", 0, 0, count, 0)
    for index, name in enumerate(names):
        at = entries_at + 20 * index
        struct.pack_into(">HHHHII", out, at, index, 0, 0x1100, name_at[name], offsets[name], len(files[name]))
    out[strings_at:strings_at + len(strings)] = strings
    out[data_at:data_at + len(data)] = data
    return bytes(out)
