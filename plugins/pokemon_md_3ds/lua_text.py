"""The text of a compiled Lua 5.1 script of a Pokémon Mystery Dungeon 3DS game (a credits line is a string constant).

A Lua 5.1 dump is one stream: the header ``\\x1bLuaQ`` (little-endian, int 4, size_t 4, instruction 4, number 8), then
the main function. A function is: source name, two line numbers, four one-byte counts, the code (count, 4-byte
instructions), the constants (count, then a tag and a value), the nested functions, the line numbers, the local
names and the upvalue names. Integers and sizes are 4 bytes. A string is a size (its length plus the trailing NUL),
the bytes and the NUL. ``dump`` writes the same stream again, so an unchanged script comes back byte for byte; a changed
string only changes its own size and bytes.

Prose: a string constant with a space and a letter is text (``is_prose``). Identifiers, paths and format keys have no
space and stay as they are.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import List, Optional

HEADER = b"\x1bLuaQ\x00\x01\x04\x04\x04\x08\x00"
_STRING, _NUMBER, _BOOLEAN, _NIL = 4, 3, 1, 0
_PROSE = re.compile(r"[^\W\d_]")


class LuaError(ValueError):
    """The bytes are not a Lua 5.1 dump this module reads."""


@dataclass
class Const:
    tag: int
    value: Optional[bytes]          # a string: its bytes without the NUL; a number or boolean: its raw bytes; None: nil


@dataclass
class Proto:
    source: Optional[bytes]
    lines: bytes                    # linedefined, lastlinedefined (8 bytes)
    counts: bytes                   # nups, numparams, is_vararg, maxstacksize (4 bytes)
    code: bytes                     # the instructions, without their count
    consts: List[Const] = field(default_factory=list)
    protos: List["Proto"] = field(default_factory=list)
    lineinfo: List[int] = field(default_factory=list)
    locvars: List[tuple] = field(default_factory=list)      # (name bytes, start pc, end pc)
    upvalues: List[Optional[bytes]] = field(default_factory=list)


def is_prose(value: bytes) -> bool:
    text = value.decode("utf-8", "replace")
    return " " in text and _PROSE.search(text) is not None and not text.startswith("@")


class _Reader:
    def __init__(self, raw: bytes):
        self.raw, self.pos = raw, len(HEADER)

    def take(self, count: int) -> bytes:
        if self.pos + count > len(self.raw):
            raise LuaError("the dump ends early")
        out = self.raw[self.pos:self.pos + count]
        self.pos += count
        return out

    def int(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def string(self) -> Optional[bytes]:
        size = self.int()
        if size == 0:
            return None
        data = self.take(size)
        if data[-1:] != b"\0":
            raise LuaError("a string without its NUL")
        return data[:-1]


def _function(r: _Reader) -> Proto:
    source = r.string()
    lines = r.take(8)
    counts = r.take(4)
    code = r.take(4 * r.int())
    consts = []
    for _ in range(r.int()):
        tag = r.take(1)[0]
        if tag == _NIL:
            consts.append(Const(tag, None))
        elif tag == _BOOLEAN:
            consts.append(Const(tag, r.take(1)))
        elif tag == _NUMBER:
            consts.append(Const(tag, r.take(8)))
        elif tag == _STRING:
            consts.append(Const(tag, r.string()))
        else:
            raise LuaError(f"a constant of type {tag}")
    proto = Proto(source, lines, counts, code, consts)
    proto.protos = [_function(r) for _ in range(r.int())]
    proto.lineinfo = [r.int() for _ in range(r.int())]
    proto.locvars = []
    for _ in range(r.int()):
        name = r.string()
        proto.locvars.append((name, r.int(), r.int()))
    proto.upvalues = [r.string() for _ in range(r.int())]
    return proto


def parse(raw: bytes) -> Proto:
    """The main function of a Lua 5.1 dump."""
    if raw[:len(HEADER)] != HEADER:
        raise LuaError("not a Lua 5.1 dump of this kind")
    r = _Reader(raw)
    main = _function(r)
    if r.pos != len(raw):
        raise LuaError("bytes after the main function")
    return main


def _string(value: Optional[bytes]) -> bytes:
    if value is None:
        return struct.pack("<I", 0)
    return struct.pack("<I", len(value) + 1) + value + b"\0"


def _write(proto: Proto, out: bytearray) -> None:
    out += _string(proto.source) + proto.lines + proto.counts
    out += struct.pack("<I", len(proto.code) // 4) + proto.code
    out += struct.pack("<I", len(proto.consts))
    for const in proto.consts:
        out += bytes([const.tag])
        if const.tag == _STRING:
            out += _string(const.value)
        elif const.tag in (_BOOLEAN, _NUMBER):
            out += const.value
    out += struct.pack("<I", len(proto.protos))
    for nested in proto.protos:
        _write(nested, out)
    out += struct.pack("<I", len(proto.lineinfo)) + b"".join(struct.pack("<I", n) for n in proto.lineinfo)
    out += struct.pack("<I", len(proto.locvars))
    for name, start, end in proto.locvars:
        out += _string(name) + struct.pack("<II", start, end)
    out += struct.pack("<I", len(proto.upvalues)) + b"".join(_string(u) for u in proto.upvalues)


def dump(main: Proto) -> bytes:
    out = bytearray(HEADER)
    _write(main, out)
    return bytes(out)


def _walk(proto: Proto):
    for const in proto.consts:
        yield const
    for nested in proto.protos:
        yield from _walk(nested)


def prose_slots(raw: bytes) -> List[Const]:
    """The string constants that are text, in the order the dump holds them."""
    return [c for c in _walk(parse(raw)) if c.tag == _STRING and c.value is not None and is_prose(c.value)]


def texts(raw: bytes) -> List[str]:
    return [c.value.decode("utf-8") for c in prose_slots(raw)]


def rebuild(raw: bytes, new_texts: List[str]) -> bytes:
    """The dump with its text constants replaced, in order. ``new_texts`` must hold one string per text constant."""
    main = parse(raw)
    slots = [c for c in _walk(main) if c.tag == _STRING and c.value is not None and is_prose(c.value)]
    if len(slots) != len(new_texts):
        raise LuaError(f"{len(new_texts)} strings for {len(slots)} text constants")
    for slot, text in zip(slots, new_texts):
        slot.value = text.encode("utf-8")
    return dump(main)
