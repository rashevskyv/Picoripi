"""Metal Gear Solid 4 (Master Collection) text files ``common/localization/<kind>/<kind>_<language>``.

Five layouts, all little-endian, every string UTF-8 with a closing NUL; a file starts ``u16 version, u32 count``:

- codec (version 1): ``count`` codec calls, each ``u32 id, u32 id, u32 n`` and ``n`` lines ``u32 size, text``
  (size counts the NUL).
- lang (version 2): ``count`` interface strings, each ``u64, u64, u64 id, u32 size, text``.
- subtitles (version 1): demo (cutscenes) and movie use a 16-byte group head, spc (in-game speech) a 12-byte one;
  the head ends ``u32 n, u32 size`` and is followed by ``n`` lines ``u16 size, 12 bytes (times, ids),
  u16 size, u16 flag, text``. A line's size counts the bytes after its first u16; the group's size is the sum
  of its lines' sizes.

``parse`` recognises the layout by reading the whole file with each one; ``build`` writes the file again with
new texts (sizes recomputed). A file whose texts did not change keeps its bytes.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

KINDS = ("codec", "lang", "demo", "spc")      # demo also reads movie files (same layout)


@dataclass
class Group:
    head: bytes                       # the bytes before the lines (ids; sizes are recomputed)
    lines: List[bytes] = field(default_factory=list)   # each line's fixed bytes before its text
    texts: List[str] = field(default_factory=list)


@dataclass
class LocFile:
    kind: str
    version: int
    groups: List[Group]


def _text(data: bytes, start: int, end: int) -> str:
    if data[end - 1] != 0:
        raise ValueError("a string without its NUL")
    return data[start:end - 1].decode("utf-8")


def _codec(data: bytes) -> LocFile:
    version, count = struct.unpack_from("<HI", data, 0)
    pos, groups = 6, []
    for _ in range(count):
        group = Group(data[pos:pos + 8])
        n = struct.unpack_from("<I", data, pos + 8)[0]
        pos += 12
        for _ in range(n):
            size = struct.unpack_from("<I", data, pos)[0]
            group.lines.append(b"")
            group.texts.append(_text(data, pos + 4, pos + 4 + size))
            pos += 4 + size
        groups.append(group)
    return LocFile("codec", version, groups) if pos == len(data) else _fail()


def _lang(data: bytes) -> LocFile:
    version, count = struct.unpack_from("<HI", data, 0)
    pos, group = 6, Group(b"")
    for _ in range(count):
        size = struct.unpack_from("<I", data, pos + 24)[0]
        group.lines.append(data[pos:pos + 24])
        group.texts.append(_text(data, pos + 28, pos + 28 + size))
        pos += 28 + size
    return LocFile("lang", version, [group]) if pos == len(data) else _fail()


def _subtitles(data: bytes, head: int, kind: str) -> LocFile:
    version, count = struct.unpack_from("<HI", data, 0)
    pos, groups = 6, []
    for _ in range(count):
        n, total = struct.unpack_from("<II", data, pos + head - 8)
        group = Group(data[pos:pos + head - 8])
        pos += head
        used = 0
        for _ in range(n):
            size, = struct.unpack_from("<H", data, pos)
            again, _flag = struct.unpack_from("<HH", data, pos + 14)
            if again != size:
                return _fail()
            group.lines.append(data[pos + 2:pos + 14] + data[pos + 16:pos + 18])
            group.texts.append(_text(data, pos + 18, pos + 2 + size))
            pos += 2 + size
            used += size
        if used != total:
            return _fail()
        groups.append(group)
    return LocFile(kind, version, groups) if pos == len(data) else _fail()


def _fail():
    raise ValueError("not this layout")


def parse(data: bytes) -> LocFile:
    """The file's groups and texts; ValueError when it is none of the five layouts."""
    data = bytes(data)
    if len(data) < 6:
        raise ValueError("too short for a localization file")
    tries = ((_lang,) if data[0] == 2 else ()) + (_codec, lambda d: _subtitles(d, 16, "demo"),
                                                  lambda d: _subtitles(d, 12, "spc"))
    for reader in tries:
        try:
            return reader(data)
        except (ValueError, struct.error, UnicodeDecodeError, IndexError):
            continue
    raise ValueError("not a Metal Gear Solid 4 localization file")


def _bytes(text: str) -> bytes:
    return text.encode("utf-8") + b"\0"


def dump(loc: LocFile) -> bytes:
    out = bytearray(struct.pack("<HI", loc.version, len(loc.groups) if loc.kind != "lang" else len(loc.groups[0].texts)))
    for group in loc.groups:
        if loc.kind == "codec":
            out += group.head + struct.pack("<I", len(group.texts))
            for text in group.texts:
                raw = _bytes(text)
                out += struct.pack("<I", len(raw)) + raw
        elif loc.kind == "lang":
            for fixed, text in zip(group.lines, group.texts):
                raw = _bytes(text)
                out += fixed + struct.pack("<I", len(raw)) + raw
        else:
            lines = []
            for fixed, text in zip(group.lines, group.texts):
                raw = _bytes(text)
                size = 16 + len(raw)
                lines.append(struct.pack("<H", size) + fixed[:12] + struct.pack("<H", size) + fixed[12:] + raw)
            out += group.head + struct.pack("<II", len(lines), sum(len(line) - 2 for line in lines))
            out += b"".join(lines)
    return bytes(out)


def texts(loc: LocFile) -> List[List[str]]:
    return [list(group.texts) for group in loc.groups]


def build(data: bytes, blocks: Sequence[Sequence[Optional[str]]]) -> bytes:
    """``data`` with the texts of ``blocks`` (None or the same text = unchanged); the original bytes when
    nothing changed."""
    loc = parse(data)
    changed = False
    for group, new in zip(loc.groups, blocks):
        for index, text in enumerate(list(new)[:len(group.texts)]):
            if text is not None and text != group.texts[index]:
                group.texts[index] = text
                changed = True
    return dump(loc) if changed else bytes(data)
