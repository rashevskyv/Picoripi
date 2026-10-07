"""GCX scripts (``*.gcx`` of STAGE.DIR): the GCL bytecode of a stage, with its text strings.

Layout (big endian): ``u32 proc length``, the proc table (``u16 id, u16 offset`` from the end of the
table; four zero bytes end it), the proc blocks, ``u32 script length``, the main script block, then
``u32`` and the script's own 12x12 glyphs. A block is ``0x40, u16 size`` (counted from the size field)
and statements: ``0x30`` expression and ``0x70`` proc call (``u8 size`` counted from the size byte),
``0x60`` command (``u16 size``, ``u16 id``, ``u8`` offset of its options from that byte, arguments,
``0x50`` options: ``char, u8 size``), ``0x00`` end. Values: ``0x01`` short, ``0x02-04`` byte,
``0x06/08`` u16, ``0x09/0A`` u32, ``0x07`` string (``u8 length`` with the NUL), ``0x1x`` variable
(4 bytes), ``0x20`` array (2 bytes), ``0x40`` block.

Text strings are ``0x07`` strings with letters in them (pick-up labels, mission log pages, VR menu
titles); names of stages, files and models are left out. Changing one fixes every size around it and
the proc offsets.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from . import codec
from .spans import Field, SizeError, rewrite

_IDENT = re.compile(rb"^[a-z0-9_./]*$|^\w+\.\w{2,3}$")


class FormatError(ValueError):
    """Not a GCX script this plugin understands."""


@dataclass
class Script:
    procs: List[Tuple[int, int]] = field(default_factory=list)   # (table entry offset, block offset)
    proc_body: int = 0
    script_at: int = 0                                           # the u32 script length
    font_at: int = 0
    strings: List[Tuple[int, int]] = field(default_factory=list)  # (start, end) of the bytes, no NUL
    fields: List[Field] = field(default_factory=list)


class _Parser:
    def __init__(self, data: bytes, script: Script):
        self.d, self.s = data, script

    def u16(self, at: int) -> int:
        return struct.unpack_from(">H", self.d, at)[0]

    def block(self, at: int) -> int:
        if self.d[at] != 0x40:
            raise FormatError(f"block expected at {at:#x}")
        end = at + 1 + self.u16(at + 1)
        self.s.fields.append(Field(at + 1, 2, at + 1, end))
        self.statements(at + 3, end)
        return end

    def statements(self, pos: int, end: int) -> None:
        d = self.d
        while pos < end:
            kind = d[pos]
            if kind == 0x00:
                pos += 1
            elif kind == 0x30:
                pos += 1 + d[pos + 1]
            elif kind == 0x70:
                stop = pos + 1 + d[pos + 1]
                self.s.fields.append(Field(pos + 1, 1, pos + 1, stop))
                self.values(pos + 4, stop)
                pos = stop
            elif kind == 0x60:
                stop = pos + 1 + self.u16(pos + 1)
                self.s.fields.append(Field(pos + 1, 2, pos + 1, stop))
                ofs_at = pos + 5
                options = ofs_at + d[ofs_at]
                if options > ofs_at + 1:          # arguments before the options: their length counts
                    self.s.fields.append(Field(ofs_at, 1, ofs_at + 1, options))
                self.values(ofs_at + 1, stop)
                pos = stop
            else:
                raise FormatError(f"statement {kind:#x} at {pos:#x}")
            if pos > end:
                raise FormatError(f"statement runs past its block at {pos:#x}")

    def values(self, pos: int, end: int, in_option: bool = False) -> int:
        d = self.d
        while pos < end:
            kind = d[pos]
            if in_option and kind == 0x50:
                return pos
            if in_option and kind == 0x00:          # the option's own end byte
                return pos + 1
            if kind == 0x00:
                pos += 1
            elif kind == 0x07:
                length = d[pos + 1]
                stop = pos + 2 + length
                if length and not d[stop - 1]:
                    raw = d[pos + 2:stop - 1]
                    if _is_text(raw):
                        self.s.fields.append(Field(pos + 1, 1, pos + 2, stop))
                        self.s.strings.append((pos + 2, stop - 1))
                pos = stop
            elif kind == 0x50:
                # The size byte keeps only the low 8 bits of a long option (a mission log page), so the
                # option is read value by value up to the next option or the end of the arguments.
                size = d[pos + 2]
                mark = (len(self.s.fields), len(self.s.strings))
                stop = self.values(pos + 3, end, in_option=True)
                if not size:                            # size 0: the option runs to the end of the command
                    pos = stop
                    continue
                if (stop - (pos + 2)) & 0xFF != size and d[stop - 1] == 0:
                    stop -= 1                           # the end byte after it is the command's
                if (stop - (pos + 2)) & 0xFF != size:
                    del self.s.fields[mark[0]:]
                    del self.s.strings[mark[1]:]
                    stop = pos + 2 + size
                    if stop > end:
                        raise FormatError(f"option at {pos:#x} runs past its command")
                    self.values(pos + 3, stop)
                self.s.fields.append(Field(pos + 2, 1, pos + 2, stop, wrap=True))
                pos = stop
            elif kind == 0x40:
                pos = self.block(pos)
            elif kind == 0x30:
                pos += 1 + d[pos + 1]
            elif kind & 0xF0 == 0x10:
                pos += 4
            elif kind in (0x01, 0x06, 0x08):
                pos += 3
            elif kind in (0x02, 0x03, 0x04, 0x20):
                pos += 2
            elif kind in (0x09, 0x0A):
                pos += 5
            else:
                raise FormatError(f"value {kind:#x} at {pos:#x}")
        if pos != end:
            raise FormatError(f"values run past {end:#x}")
        return pos


def _is_text(raw: bytes) -> bool:
    """A string a player reads: letters and a space or capitals, not a file or model name."""
    if len(raw) < 2 or _IDENT.match(raw):
        return False
    return codec.has_letters(raw) and (b" " in raw or raw.upper() == raw or codec.is_wide(raw))


def read(data: bytes) -> Script:
    if len(data) < 16:
        raise FormatError("too short for a GCX script")
    proc_len = struct.unpack_from(">I", data, 0)[0]
    script = Script()
    pos = 4
    while True:
        if pos + 4 > len(data):
            raise FormatError("proc table has no end")
        if struct.unpack_from(">I", data, pos)[0] == 0:
            break
        script.procs.append((pos, struct.unpack_from(">H", data, pos + 2)[0]))
        pos += 4
    script.proc_body = pos + 4
    script.script_at = 4 + proc_len
    if script.script_at + 7 > len(data):
        raise FormatError("proc length runs past the file")
    script.fields.append(Field(0, 4, 4, script.script_at))
    parser = _Parser(data, script)
    starts = sorted({script.proc_body + offset for _entry, offset in script.procs})
    for start in starts:
        parser.block(start)
    body = script.script_at + 4
    script.fields.append(Field(script.script_at, 4, body, body + struct.unpack_from(">I", data, script.script_at)[0]))
    script.font_at = parser.block(body)
    if script.font_at != body + struct.unpack_from(">I", data, script.script_at)[0]:
        raise FormatError("script length does not match its block")
    return script


def looks_like(data: bytes) -> bool:
    try:
        read(data)
    except (FormatError, IndexError, struct.error):
        return False
    return True


def build(data: bytes, script: Script, new: Dict[int, bytes]) -> bytes:
    """The script with string ``index -> new bytes`` (no NUL); proc offsets follow the moved blocks."""
    edits = [(script.strings[i][0], script.strings[i][1], raw) for i, raw in new.items()]
    if not any(data[s:e] != raw for s, e, raw in edits):
        return bytes(data)
    out = bytearray(rewrite(data, script.fields, edits))

    def moved(at: int) -> int:
        return at + sum(len(raw) - (e - s) for s, e, raw in edits if e <= at)

    for entry, offset in script.procs:
        new_offset = moved(script.proc_body + offset) - script.proc_body
        if new_offset > 0xFFFF:
            raise SizeError("the procs of the script grew past 64 KB")
        struct.pack_into(">H", out, entry + 2, new_offset)
    return bytes(out)


def strings_of(data: bytes, script: Sequence = ()) -> List[bytes]:
    script = script or read(data)
    return [data[s:e] for s, e in script.strings]
