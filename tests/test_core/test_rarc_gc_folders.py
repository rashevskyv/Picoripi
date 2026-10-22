"""GameCube RARC folders: an entry with attribute 0x02 and file ID 0 is a folder (Luigi's Mansion), not a file."""
import struct

from core.containers.rarc_container import RarcContainer


def _nested_rarc(member: bytes) -> bytes:
    """Root folder holding ``sub``; ``sub`` holds one file ``m.csv``. Big-endian, with the '.' and '..' entries."""
    strings = b"\0ROOT\0sub\0m.csv\0.\0..\0"
    dh, node_at, entries_at, strings_at = 0x20, 0x40, 0x60, 0xD8
    data_at = (strings_at + len(strings) + 0x1F) // 0x20 * 0x20
    data = member + bytes(-len(member) % 0x20)
    size = data_at + len(data)
    out = bytearray(size)
    struct.pack_into(">4sIIIII", out, 0, b"RARC", size, dh, data_at - dh, len(data), len(data))
    struct.pack_into(">IIIIIIHBB", out, dh, 2, node_at - dh, 6, entries_at - dh, len(strings), strings_at - dh, 6, 1, 0)
    # node list: ROOT (entries 0-2), sub (entries 3-5)
    struct.pack_into(">4sIHHI", out, node_at, b"ROOT", 1, 0, 3, 0)
    struct.pack_into(">4sIHHI", out, node_at + 0x10, b"DIR ", 6, 0, 3, 3)

    def entry(index, ident, flags, name_off, data_off, length):
        struct.pack_into(">HHIII", out, entries_at + 0x14 * index, ident, 0, flags << 16 | name_off, data_off, length)

    entry(0, 0, 0x0200, 6, 1, 16)       # sub -> node 1
    entry(1, 0, 0x0200, 13, 0, 16)      # .
    entry(2, 0, 0x0200, 15, 0xFFFFFFFF, 0)   # ..
    entry(3, 0, 0x1100, 10, 0, len(member))  # m.csv
    entry(4, 0, 0x0200, 13, 1, 16)
    entry(5, 0, 0x0200, 15, 0, 0)
    out[strings_at:strings_at + len(strings)] = strings
    out[data_at:data_at + len(data)] = data
    return bytes(out)


def test_a_gc_folder_entry_is_walked_and_its_member_is_read():
    raw = _nested_rarc(b"hello\r\n")
    container = RarcContainer(raw)
    assert container.list_files() == ["sub/m.csv"]
    assert container.read_file("sub/m.csv") == b"hello\r\n"
    assert container.pack() == raw
