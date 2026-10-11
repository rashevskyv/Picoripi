"""Code of Princess text: NUL-terminated wide strings compiled into the game's executable.

3DS (``exefs/code.bin``, decompressed): UTF-16LE. Switch EX (``exefs/main``, an NSO): UTF-32LE, found in the
decompressed segments. The strings of one area lie back to back, each followed by a single NUL unit, so a string can
be rewritten in place and may not grow: a shorter text is padded with NUL units (the terminator stays). A control
unit (the 0x08 that ends a message, 0x01..0x1F) is shown as ``{xNN}``; ``\\n`` is a line break.

Finding the strings: a run of units that are Latin-1 text, general punctuation, Cyrillic, 0x08 or 0x0A, at least
three long, after a NUL unit, ended by a NUL unit; names of files and identifiers (``/chara/x.rani``, ``HIME_100``),
debug text (``Class::Method``) and runs without a letter are not text. Areas are clusters of such strings (gap
below 2 KiB) with at least 20 strings; a string's room is its length plus the NUL padding after it.
"""
from __future__ import annotations

import hashlib
import re
import struct
from typing import Dict, List, Tuple

from core.containers.retro_pak import nso_memory

CONTROL = re.compile(r"\{x([0-9a-fA-F]{1,4})\}")
GAP = 2048
MIN_AREA = 20
_IDENT = re.compile(r"^[A-Za-z0-9_.\\/:%\-]+$")


class PoolError(ValueError):
    pass


def _unit_regex(width: int):
    if width == 2:
        unit = (rb"(?:[\x20-\x7e\xa0-\xff]\x00|[\x08\x0a]\x00|[\x10-\x5f]\x20|[\x00-\xff][\x04])")
        return re.compile(rb"(?<=\x00\x00)(" + unit + rb"{3,})\x00\x00")
    unit = (rb"(?:[\x20-\x7e\xa0-\xff]\x00\x00\x00|[\x08\x0a]\x00\x00\x00|[\x10-\x5f]\x20\x00\x00|"
            rb"[\x00-\xff][\x04]\x00\x00)")
    return re.compile(rb"(?<=\x00\x00\x00\x00)(" + unit + rb"{3,})\x00\x00\x00\x00")


def is_text(text: str) -> bool:
    if not any(c.isalpha() for c in text):
        return False
    if text[0] in "/." or "::" in text or ".cpp" in text or text.endswith(".h") or "()" in text or "!=" in text:
        return False
    if len(text) > 12 and not any(c.isspace() for c in text) and re.search(r"[a-z][A-Z]", text):
        return False        # CamelCase identifier
    return not (_IDENT.match(text) and re.search(r"[_/.\d]", text))


def encode(text: str, width: int) -> bytes:
    units: List[int] = []
    pos = 0
    while pos < len(text):
        m = CONTROL.match(text, pos)
        if m:
            units.append(int(m.group(1), 16))
            pos = m.end()
            continue
        code = ord(text[pos])
        if text[pos] == "\n":
            code = 0x0A
        if code > 0xFFFF and width == 2:
            raise PoolError(f"{text[pos]!r} does not fit one UTF-16 unit")
        if code == 0:
            raise PoolError("a NUL character cannot be part of a string")
        units.append(code)
        pos += 1
    return b"".join(struct.pack("<H" if width == 2 else "<I", u) for u in units)


def decode(raw: bytes, width: int) -> str:
    fmt = "<H" if width == 2 else "<I"
    out = []
    for (u,) in struct.iter_unpack(fmt, raw):
        if u == 0x0A:
            out.append("\n")
        elif u < 0x20 or u in (0x7B, 0x7D):
            out.append("{x%02x}" % u)
        else:
            out.append(chr(u))
    return "".join(out)


class Item:
    __slots__ = ("start", "units", "room", "area")

    def __init__(self, start: int, units: int, room: int, area: int) -> None:
        self.start, self.units, self.room, self.area = start, units, room, area


class Pool:
    """The editable strings of an executable and the way to write them back."""

    def __init__(self, raw: bytes) -> None:
        raw = bytes(raw)
        self.raw = raw
        self.nso = raw[:4] == b"NSO0"
        self.width = 4 if self.nso else 2
        try:
            self.memory = bytearray(nso_memory(raw) if self.nso else raw)
        except (ValueError, IndexError, struct.error) as error:
            raise PoolError(f"not a Code of Princess executable ({error})") from None
        self.items: List[Item] = []
        found = []
        for m in _unit_regex(self.width).finditer(bytes(self.memory)):
            if m.start() % self.width:
                continue
            try:
                text = m.group(1).decode("utf-16le" if self.width == 2 else "utf-32le")
            except UnicodeDecodeError:
                continue
            if is_text(text):
                found.append((m.start(), len(text)))
        areas: List[List[Tuple[int, int]]] = []
        for start, units in found:
            if areas and start - (areas[-1][-1][0] + areas[-1][-1][1] * self.width) <= GAP:
                areas[-1].append((start, units))
            else:
                areas.append([(start, units)])
        for number, area in enumerate(a for a in areas if len(a) >= MIN_AREA):
            for start, units in area:
                end = start + units * self.width
                zeros = 0
                while end + zeros * self.width + self.width <= len(self.memory) and \
                        self.memory[end + zeros * self.width:end + (zeros + 1) * self.width] == b"\0" * self.width:
                    zeros += 1
                self.items.append(Item(start, units, units + max(0, zeros - 1), number))
        self.areas = sorted({i.area for i in self.items})

    def texts(self) -> List[List[str]]:
        """One list of strings per area."""
        out: Dict[int, List[str]] = {}
        for item in self.items:
            raw = bytes(self.memory[item.start:item.start + item.units * self.width])
            out.setdefault(item.area, []).append(decode(raw, self.width))
        return [out[a] for a in sorted(out)]

    def rebuild(self, texts: List[List[str]]) -> bytes:
        flat = [t for block in texts for t in block]
        if len(flat) != len(self.items):
            raise PoolError(f"{len(flat)} strings for {len(self.items)} in the executable")
        memory = bytearray(self.memory)
        # in-memory order of items matches texts() order (areas ascending, strings in file order)
        ordered = sorted(self.items, key=lambda i: (i.area, i.start))
        for item, text in zip(ordered, flat):
            raw = encode(text, self.width)
            if len(raw) // self.width > item.room:
                raise PoolError(f"the string at {item.start:#x} is {len(raw) // self.width - item.room} "
                                f"characters too long (room {item.room} characters): {text[:40]!r}")
            end = item.start + item.room * self.width
            memory[item.start:end] = raw + b"\0" * (end - item.start - len(raw))
        if memory == self.memory:
            return self.raw
        if not self.nso:
            return bytes(memory)
        return nso_build(bytes(memory), self.raw)


def nso_build(memory: bytes, original: bytes) -> bytes:
    """An NSO with the same layout whose segments are ``memory`` (stored uncompressed, hashes written again)."""
    head = bytearray(original[:0x100])
    flags = struct.unpack_from("<I", head, 0xC)[0]
    struct.pack_into("<I", head, 0xC, flags & ~0x7)
    body = bytearray()
    cursor = 0x100
    # the original file's name block (module name) is kept right behind the header
    name_off, name_size = struct.unpack_from("<II", original, 0x1C)[0], struct.unpack_from("<I", original, 0x2C)[0]
    name = original[name_off:name_off + name_size] if name_size else b""
    struct.pack_into("<I", head, 0x1C, cursor)
    body += name
    cursor += len(name)
    for index in range(3):
        _file_at, mem_at, size = struct.unpack_from("<III", head, 0x10 + index * 0x10)
        segment = memory[mem_at:mem_at + size]
        struct.pack_into("<I", head, 0x10 + index * 0x10, cursor)
        struct.pack_into("<I", head, 0x60 + index * 4, size)
        head[0xA0 + index * 0x20:0xC0 + index * 0x20] = hashlib.sha256(segment).digest()
        body += segment
        cursor += len(segment)
    return bytes(head) + bytes(body)
