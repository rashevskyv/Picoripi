"""Small Vagrant Story files built the way the game lays them out (for tests without the disc)."""
import struct

from plugins.vagrant_story import codec, formats


def raw(text: str) -> bytes:
    """A string as the game stores it in a table: end byte, padded to an even length."""
    return codec.terminate(codec.encode(text))


def table(strings, count_in_front: bool = False) -> bytes:
    """A string table: offsets in half-words, then the strings."""
    t = formats.Table(0, len(strings), 0, 2 if count_in_front else 0, 0x10000)
    return t.build([raw(s)[:raw(s).index(codec.END) + 1] for s in strings])


def script(strings, boxes=((13, 3),), block1=b"\x11" * 8, block2=b"\x22" * 4) -> bytes:
    """A script section: header, DialogShow/DialogText for each string, return, the dialog table, two blocks."""
    ops = bytearray()
    for index in range(len(strings)):
        cpl, lines = boxes[index % len(boxes)]
        ops += bytes((formats.DIALOG_SHOW, 0x00, 0x37, 0x01, 0x1A, 0xC6, cpl, lines, 0, 0, 0))
        ops += bytes((formats.DIALOG_TEXT, 0x00, index, 0x00))
        ops += bytes((0x12, 0x00))
    ops += b"\xff"
    ops += bytes(-len(ops) % 4)
    text = 0x10 + len(ops)
    dialog = table(strings)
    dialog += bytes(-len(dialog) % 4)
    b1 = text + len(dialog)
    b2 = b1 + len(block1)
    length = b2 + len(block2)
    return struct.pack("<4H", length, text, b1, b2) + bytes(8) + bytes(ops) + dialog + block1 + block2


def event_file(strings, **kw) -> bytes:
    sec = script(strings, **kw)
    return sec + bytes(formats.EVENT_SIZE - len(sec))


def room_file(strings, slack: int = 600, **kw) -> bytes:
    """A room: six sections (room geometry, cleared, script, doors, enemies, treasure)."""
    sec = script(strings, **kw)
    sizes = [0x40, 4, len(sec), 12, 8, 0]
    body = [b"\x5a" * sizes[0], b"\x01" * 4, sec, b"\x0d" * 12, b"\x0e" * 8, b""]
    header, offset = [], 0x30
    for size in sizes:
        header += [offset, size]
        offset += size
    data = struct.pack("<12I", *header) + b"".join(body)
    room = -(-len(data) // formats.SECTOR) * formats.SECTOR - len(data)
    assert room >= slack, "the sample room must leave room in its last sector"
    return data


def item_names(names) -> bytes:
    out = bytearray(24 * max(8, len(names) + 1))
    out[0] = codec.END
    for i, name in enumerate(names, 1):
        body = codec.encode(name) + bytes((codec.END,))
        out[i * 24:i * 24 + len(body)] = body
    for i in range(len(names) + 1, len(out) // 24):
        out[i * 24] = codec.END
    return bytes(out)


def help_file(strings) -> bytes:
    text = table(strings, count_in_front=True)
    text += bytes(-len(text) % 4)
    sprites, lines = b"\x00\x00", b"\x00\x00"
    return struct.pack("<4I", len(text), len(sprites), len(lines), 0) + text + sprites + lines


def area_file(rooms) -> bytes:
    """An area map: rooms ``[(zone, room, name)]`` with no geometry."""
    out = bytearray(struct.pack("<I", len(rooms)))
    for zone, room, _name in rooms:
        out += struct.pack("<IIHH", 0, 0, zone, room)
    for _zone, _room, name in rooms:
        field = bytes((0xF8, 0, 0xFB, 4, 0xFB, 6)) + codec.encode(name) + bytes((codec.END,))
        out += field.ljust(32, b"\0") + struct.pack("<HH", 0, 0)
    return bytes(out)


def program_file(names, menu) -> bytes:
    """Program data: code-like bytes, names in 24-byte fields, a menu table."""
    out = bytearray(b"\x27\xbd\xff\xe8" * 16)
    for name in names:
        out += bytes(4) + (codec.encode(name) + bytes((codec.END,))).ljust(24, b"\0") + b"\x10\x80\x00\x90"
    out += bytes(-len(out) % 4)
    out += table(menu)
    out += bytes(-len(out) % 4) + b"\x27\xbd\x00\x18" * 8
    return bytes(out)
