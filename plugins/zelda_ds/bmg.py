"""BMG message files of The Legend of Zelda: Phantom Hourglass and Spirit Tracks (Nintendo DS, little endian).

Layout: ``MESGbmg1`` header (0x20 bytes: magic, total size, section count, encoding 2 = UTF-16, three zero words),
then the sections ``INF1`` (message table), ``DAT1`` (the texts) and, in some files, ``FLW1`` / ``FLI1`` (flow
data), each as a 4-byte magic and a u32 size that counts the 8-byte section header.

``INF1`` body: u16 count, u16 entry size, u32 id, then ``count`` entries of ``entry size`` bytes: u32 offset of the
text inside the ``DAT1`` body (the bytes after its 8-byte header), then the entry's remaining bytes (kept as they are).
A text is UTF-16 little endian, ends with a 0x0000 unit, and may start with a 0x0000 unit (the first text of a
file begins at offset 2 then).

Control codes: the unit 0x001A, a length byte (the whole code, counted from its first byte), a type byte, then the
data. The editor shows a code as ``[tag:TT:HEX]`` (TT = type, HEX = data bytes).

Nothing is re-encoded that did not change: ``build`` copies the raw bytes of every text the caller leaves alone, so an
unedited file comes back byte for byte.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Tuple

MAGIC = b"MESGbmg1"
HEADER_SIZE = 0x20
ESC = b"\x1a\x00"
END = b"\x00\x00"
TAG_RE = re.compile(r"\[tag:([0-9a-f]{2}):([0-9a-f]*)\]")


class BmgError(ValueError):
    """Not a BMG file, or a text the file cannot store."""


class Bmg:
    """A parsed BMG file. ``sections`` keeps every section in file order as ``[magic, body]``."""

    def __init__(self, data: bytes):
        if len(data) < HEADER_SIZE or data[:8] != MAGIC:
            raise BmgError("not a BMG file (no MESGbmg1 magic)")
        total = struct.unpack_from("<I", data, 8)[0]
        if total < HEADER_SIZE:
            raise BmgError(f"BMG size field {total} is too small")
        # bytes after the size field belong to the file's container (the NitroFS entry pads it): kept as they are
        self.tail = bytes(data[total:]) if total <= len(data) else b""
        # some files state more bytes than their NitroFS entry holds (the last section is cut short there):
        # the missing bytes read as zero here and are dropped again when the file is written back unchanged
        self.short = max(0, total - len(data))
        data = bytes(data[:total]) + b"\x00" * self.short
        self.head = bytearray(data[:HEADER_SIZE])
        self.sections: List[List[bytes]] = []
        pos = HEADER_SIZE
        # the count field is not trusted (clean files state more sections than they hold): sections run to the size
        while pos < len(data):
            if pos + 8 > len(data):
                raise BmgError("truncated section header")
            size = struct.unpack_from("<I", data, pos + 4)[0]
            if size < 8 or pos + size > len(data):
                raise BmgError("bad section size")
            self.sections.append([data[pos:pos + 4], data[pos + 8:pos + size]])
            pos += size
        self.count, self.entry_size, self.file_id = 0, 0, 0
        inf = self._section(b"INF1")
        dat = self._section(b"DAT1")
        if inf is None or dat is None:
            raise BmgError("no INF1 or DAT1 section")
        self.count, self.entry_size, self.file_id = struct.unpack_from("<HHI", inf, 0)
        if self.entry_size < 4:
            raise BmgError("INF1 entry size below 4")
        self.offsets = [struct.unpack_from("<I", inf, 8 + i * self.entry_size)[0] for i in range(self.count)]
        self.dat_index = next(i for i, (magic, _b) in enumerate(self.sections) if magic == b"DAT1")
        self.inf_index = next(i for i, (magic, _b) in enumerate(self.sections) if magic == b"INF1")

    def _section(self, magic: bytes):
        for name, body in self.sections:
            if name == magic:
                return body
        return None

    def segments(self) -> Tuple[bytes, Dict[int, bytes], List[int]]:
        """``(prefix, {offset: raw text bytes}, sorted distinct offsets)``; a raw text runs to the next offset."""
        body = bytes(self.sections[self.dat_index][1])
        distinct = sorted(set(self.offsets))
        if not distinct:
            return body, {}, []
        if distinct[-1] > len(body):
            raise BmgError("INF1 offset beyond the DAT1 body")
        bounds = distinct[1:] + [len(body)]
        raw = {off: body[off:end] for off, end in zip(distinct, bounds)}
        return body[:distinct[0]], raw, distinct

    def texts(self) -> List[str]:
        _prefix, raw, _distinct = self.segments()
        return [decode_text(raw[off]) for off in self.offsets]


def decode_text(raw: bytes) -> str:
    """The editor form of one raw text: UTF-16 characters and ``[tag:TT:HEX]`` for control codes."""
    out: List[str] = []
    run = bytearray()
    pos = 0
    while pos + 2 <= len(raw):
        unit = raw[pos:pos + 2]
        if unit == END:
            break
        if unit == ESC:
            if run:
                out.append(run.decode("utf-16-le"))
                run = bytearray()
            if pos + 4 > len(raw):
                raise BmgError("control code cut off")
            length, kind = raw[pos + 2], raw[pos + 3]
            if length < 4 or pos + length > len(raw):
                raise BmgError(f"bad control code length {length} at {pos}")
            out.append(f"[tag:{kind:02x}:{raw[pos + 4:pos + length].hex()}]")
            pos += length
            continue
        run += unit
        pos += 2
    if run:
        out.append(run.decode("utf-16-le"))
    return "".join(out)


def encode_text(text: str) -> bytes:
    """The raw form of an editor text (control codes back to bytes), with its 0x0000 end unit."""
    if "\x00" in text:
        raise BmgError("a text cannot hold a NUL character")
    out = bytearray()
    pos = 0
    for match in TAG_RE.finditer(text):
        out += text[pos:match.start()].encode("utf-16-le")
        data = bytes.fromhex(match.group(2))
        length = 4 + len(data)
        if length > 0xFF:
            raise BmgError("control code too long")
        out += ESC + bytes([length, int(match.group(1), 16)]) + data
        pos = match.end()
    out += text[pos:].encode("utf-16-le")
    out += END
    return bytes(out)


def build(data: bytes, changed: Dict[int, str]) -> bytes:
    """The file with the texts ``changed`` ({message index: new editor text}) replaced; the rest stays as it is.

    A text that shares its place in DAT1 with others keeps that place for the others; an edited copy gets a new
    place at the end of DAT1.
    """
    bmg = Bmg(data)
    for index in changed:
        if not 0 <= index < bmg.count:
            raise BmgError(f"no text {index} in this file")
    current = bmg.texts()
    edits = {i: t for i, t in changed.items() if t != current[i]}
    if not edits:
        return bytes(data)
    prefix, raw, distinct = bmg.segments()
    groups: Dict[int, List[int]] = {}
    for i, off in enumerate(bmg.offsets):
        groups.setdefault(off, []).append(i)
    body = bytearray(prefix)
    index_pos: Dict[int, int] = {}
    appended: List[int] = []
    for off in distinct:
        members = groups[off]
        edited = [i for i in members if i in edits]
        kept = [i for i in members if i not in edits]
        if not edited:
            index_pos.update({i: len(body) for i in members})
            body += raw[off]
        elif not kept and all(edits[i] == edits[edited[0]] for i in edited):
            index_pos.update({i: len(body) for i in members})
            body += encode_text(edits[edited[0]])
        else:
            if kept:
                index_pos.update({i: len(body) for i in kept})
                body += raw[off]
            appended.extend(edited)
    for i in appended:
        index_pos[i] = len(body)
        body += encode_text(edits[i])
    inf = bytearray(bmg.sections[bmg.inf_index][1])
    for i in range(bmg.count):
        struct.pack_into("<I", inf, 8 + i * bmg.entry_size, index_pos[i])
    bmg.sections[bmg.inf_index][1] = bytes(inf)
    bmg.sections[bmg.dat_index][1] = bytes(body)
    return _assemble(bmg)


def _assemble(bmg: Bmg) -> bytes:
    out = bytearray(bmg.head)
    for magic, body in bmg.sections:
        out += magic + struct.pack("<I", 8 + len(body)) + body
    struct.pack_into("<I", out, 8, len(out))
    if bmg.short and bytes(out[-bmg.short:]) == b"\x00" * bmg.short:
        out = out[:-bmg.short]
    return bytes(out) + bmg.tail
