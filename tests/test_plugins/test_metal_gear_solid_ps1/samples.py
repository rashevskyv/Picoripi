"""Small Metal Gear Solid (PlayStation) files built the way the game lays them out (tests without the discs)."""
import struct

from plugins.metal_gear_solid_ps1 import codec, subs


def _element(code: int, payload: bytes) -> bytes:
    return bytes((0xFF, code)) + struct.pack(">H", len(payload) + 2) + payload


def _block(body: bytes) -> bytes:
    return b"\x80" + struct.pack(">H", len(body) + 3) + body + b"\0"


def talk(text: str, character: int = 0x21CA) -> bytes:
    return _element(1, struct.pack(">HHH", character, 0, 0) + codec.encode(text) + b"\0")


def call(lines, frequency: int = 14085, voice: bool = True) -> bytes:
    """One codec call: header, a block with talk lines (the second half inside a voice element)."""
    half = len(lines) // 2
    body = b"".join(talk(line) for line in lines[:half])
    inner = b"".join(talk(line) for line in lines[half:])
    if voice:
        body += _element(2, struct.pack(">I", 0x141C2) + _block(inner))
    else:
        body += inner
    return struct.pack(">HIH", frequency, 0x5E000313, 0) + _block(body)


def radio(calls) -> bytes:
    """RADIO.DAT: calls one after another, zero padding after each."""
    return b"".join(call(lines) + bytes(5) for lines in calls)


def gcx(strings, proc_strings=()) -> bytes:
    """A GCX script: one proc and the main script, each a block of ``mesg``-like commands with string arguments."""
    def command(text: bytes) -> bytes:
        option = b"\x50\x73" + bytes((len(text) + 4,)) + b"\x07" + bytes((len(text) + 1,)) + text + b"\0"
        body = struct.pack(">H", 0x22FF) + b"\x01" + option + b"\0"
        return b"\x60" + struct.pack(">H", len(body) + 2) + body

    def block(texts) -> bytes:
        body = b"".join(command(t.encode("ascii")) for t in texts) + b"\0"
        return b"\x40" + struct.pack(">H", len(body) + 2) + body

    proc = block(proc_strings)
    table = struct.pack(">HH", 0x1234, 0) + bytes(4)
    script = block(strings)
    return (struct.pack(">I", len(table) + len(proc)) + table + proc + struct.pack(">I", len(script)) + script
            + struct.pack(">I", 0))


def subtitle_block(lines) -> bytes:
    body = bytearray()
    for number, text in enumerate(lines):
        raw = codec.encode(text, codec.SUB_LF)
        padded = raw + bytes(4 - len(raw) % 4)
        size = 0 if number == len(lines) - 1 else 16 + len(padded)
        body += struct.pack("<4I", size, 100 * number, 60, 0) + padded
    head = struct.pack("<IIHHI", 0, 0x7FFFFFFF, 16, 20, 0) + b"\xf0\0\0\0"
    out = bytearray(head + body)
    struct.pack_into("<I", out, 12, len(out))
    return bytes(out)


def subs_file(blocks, room: int = 4096) -> bytes:
    return subs.write([subs.Record(room, [(1, 0, 0, 0)], subtitle_block(lines)) for lines in blocks])


def program(strings) -> bytes:
    """A PS-X EXE with word-aligned strings after its header."""
    out = bytearray(b"PS-X EXE" + bytes(0x800 - 8))
    for text in strings:
        raw = text.encode("ascii") + b"\0"
        out += raw + bytes(-len(raw) % 4)
    return bytes(out + bytes(64))
