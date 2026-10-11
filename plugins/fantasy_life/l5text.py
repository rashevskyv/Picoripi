"""Fantasy Life text files: a Level-5 table of UTF-16 strings, alone or as the first item of a small container.

Table (little endian, at ``base`` in the file; ``base`` is 0 for a plain table)::

    +0x00 u32 0x1D038013  +0x0C u32 payload size (the table's bytes - 0x20)  +0x10 u32 0x20
    +0x20 u32 id  u32 0  u32 0  u32 string count  u32 4  u32 offset of the offset list (0x38)
    +offset: count * u32 offsets of the strings (from ``base``), then the strings: UTF-16, NUL-terminated and
    padded to 4 bytes

Container: ``u32 n`` (1..8), ``n + 1`` u32 offsets (the first is 4 + 4 * (n + 1)), the items back to back.

Text is plain UTF-16. Control sequences use units below 0x20 and from 0xFFF0 on: they are shown as
``{c:XXXX.XXXX...}`` tags (one per run), except the line break (``FFF0 FFFF 0004 0000``, preceded by one ``FFFF``
pad unit when it would start between two 4-byte words), which is a real new line.
"""
from __future__ import annotations

import re
import struct
from typing import List, Optional, Tuple

TABLE_MAGIC = 0x1D038013
TAG_RE = re.compile(r"\{c:[0-9a-f]{4}(?:\.[0-9a-f]{4})*\}")
_BREAK = (0xFFF0, 0xFFFF, 0x0004, 0x0000)


class FormatError(ValueError):
    """Not a Fantasy Life text file."""


def _is_control(unit: int) -> bool:
    return unit < 0x20 or unit >= 0xFFF0


def _table_at(data: bytes, base: int) -> Optional[Tuple[int, int, int]]:
    """``(count, offset list at, end)`` of a table at ``base`` or None."""
    if len(data) < base + 0x40 or struct.unpack_from("<I", data, base)[0] != TABLE_MAGIC:
        return None
    count, stride, at = struct.unpack_from("<III", data, base + 0x2C)
    if stride != 4 or not 0 < count <= 200000 or base + at + 4 * count > len(data):
        return None
    end = base + struct.unpack_from("<I", data, base + 0x0C)[0] + 0x20
    if end > len(data):
        return None
    return count, at, end


def _content(units: Tuple[int, ...]) -> Tuple[int, ...]:
    """The units of a string without its NUL terminator and padding. A command (``FFFx FFFF n 0`` and ``n - 4``
    more bytes) is taken whole, so a command that ends with zeros keeps them."""
    i, last, n = 0, 0, len(units)
    while i < n:
        unit = units[i]
        if unit >= 0xFFF0 and i + 3 < n and units[i + 1] == 0xFFFF:
            i += 2 + units[i + 2] // 2
            last = min(i, n)
            continue
        i += 1
        if unit:
            last = i
    return units[:last]


def decode(entry: bytes, start: int = 0) -> str:
    """One string's bytes as editor text (``start``: the string's first unit sits at an odd 2-byte slot, 1)."""
    units = _content(struct.unpack(f"<{len(entry) // 2}H", entry[:len(entry) // 2 * 2]))
    out: List[str] = []
    run: List[int] = []
    pos = start          # units written so far (for the alignment of a break)

    def flush() -> None:
        nonlocal pos
        if not run:
            return
        seq = tuple(run)
        if seq == _BREAK or (seq[:1] == (0xFFFF,) and seq[1:] == _BREAK and pos % 2 == 1):
            out.append("\n")
        else:
            out.append("{c:" + ".".join(f"{u:04x}" for u in seq) + "}")
        pos += len(seq)
        run.clear()

    for unit in units:
        if _is_control(unit):
            run.append(unit)
        else:
            flush()
            out.append(chr(unit) if not 0xD800 <= unit < 0xE000 else "�")
            pos += 1
    flush()
    return "".join(out)


def encode(text: str, pad4: bool = True, start: int = 0) -> bytes:
    """Editor text -> the string's bytes: units, a NUL, zero padding to 4 bytes (``pad4``: the table pads)."""
    units: List[int] = []
    pos = 0
    while pos < len(text):
        tag = TAG_RE.match(text, pos)
        if tag:
            units += [int(u, 16) for u in tag.group()[3:-1].split(".")]
            pos = tag.end()
        elif text[pos] == "\n":
            if (len(units) + start) % 2:
                units.append(0xFFFF)
            units += _BREAK
            pos += 1
        else:
            j = pos
            while j < len(text) and text[j] != "\n" and not TAG_RE.match(text, j):
                j += 1
            raw = text[pos:j].encode("utf-16-le", "surrogatepass")
            units += struct.unpack(f"<{len(raw) // 2}H", raw)
            pos = j
    units.append(0)
    raw = struct.pack(f"<{len(units)}H", *units)
    return raw + bytes(-len(raw) % 4) if pad4 else raw


class L5Text:
    """A parsed text file: ``strings`` (editor text) and ``build``."""

    def __init__(self, data: bytes):
        self.data = bytes(data)
        self.base = 0
        found = _table_at(self.data, 0)
        self.container: List[int] = []
        if found is None and len(self.data) > 16:
            n = struct.unpack_from("<I", self.data, 0)[0]
            if 1 <= n <= 8 and struct.unpack_from("<I", self.data, 4)[0] == 4 + 4 * (n + 1):
                offs = struct.unpack_from(f"<{n + 1}I", self.data, 4)
                for k in range(n):
                    found = _table_at(self.data, offs[k])
                    if found is not None:
                        self.base, self.container = offs[k], list(offs)
                        break
        if found is None:
            raise FormatError("not a Fantasy Life text table")
        self.count, self.list_at, self.end = found
        offs = struct.unpack_from(f"<{self.count}I", self.data, self.base + self.list_at)
        if any(a > b for a, b in zip(offs, offs[1:])):
            raise FormatError("string offsets are not ascending")
        self.entries = [self.data[self.base + o:self.base + (offs[i + 1] if i + 1 < self.count else self.end - self.base)]
                        for i, o in enumerate(offs)]
        # most tables pad every string to 4 bytes; some (older ones) run the strings together
        self.pad4 = all(len(e) % 4 == 0 for e in self.entries)
        self.strings = [decode(e) for e in self.entries]
        self.exact = [encode(s, self.pad4) == e for s, e in zip(self.strings, self.entries)]

    def build(self, texts: List[str]) -> bytes:
        if len(texts) != self.count:
            raise FormatError(f"{len(texts)} strings for {self.count}")
        entries = []
        for i, text in enumerate(texts):
            entries.append(self.entries[i] if text == self.strings[i] else encode(text, self.pad4))
        offsets, at = [], self.list_at + 4 * self.count
        for e in entries:
            offsets.append(at)
            at += len(e)
        table = bytearray(self.data[self.base:self.base + self.list_at])
        table += struct.pack(f"<{self.count}I", *offsets) + b"".join(entries)
        struct.pack_into("<I", table, 0x0C, len(table) - 0x20)
        if not self.container:
            return bytes(table)
        # container: the table item is replaced, the offsets of the items behind it move
        n = len(self.container) - 1
        item = self.container.index(self.base)
        old_len = self.container[item + 1] - self.base
        shift = len(table) - old_len
        offs = [o + shift if k > item else o for k, o in enumerate(self.container)]
        head = struct.pack("<I", n) + struct.pack(f"<{n + 1}I", *offs)
        return head + self.data[self.container[0]:self.base] + bytes(table) + self.data[self.container[item + 1]:]



# ---------------------------------------------------------------- pointer tables (menu and system texts)

class L5PtrText:
    """A text file of the second kind: the same magic, but the 0x20-byte header leads to rows (``count`` x
    ``stride`` bytes) in which some columns are byte offsets of NUL-terminated UTF-16 strings; the strings fill the
    rest of the file. ``strings`` are the distinct strings in order of first use (row by row); ``build`` rewrites a
    changed string in its own space. A longer string is cut to that space and listed in ``cut``: with
    ``allow_growth`` it is appended to the file and every pointer to it moves instead. The game hung after the title
    screen in an Azahar run with such moved strings, so growth is off for now."""

    def __init__(self, data: bytes):
        self.data = bytes(data)
        d = self.data
        if len(d) < 0x40 or struct.unpack_from("<I", d, 0)[0] != TABLE_MAGIC:
            raise FormatError("not a Fantasy Life text table")
        if struct.unpack_from("<I", d, 0x0C)[0] + 0x20 != len(d):
            raise FormatError("the payload size does not match the file")
        at = struct.unpack_from("<I", d, 0x14)[0]
        if not 0x20 <= at <= len(d) - 12 or at % 4:
            raise FormatError("no row table")
        rows, stride, table = struct.unpack_from("<3I", d, at)
        end = table + rows * stride
        if not 0 < rows <= 200000 or stride < 4 or stride % 4 or table < at + 12 or end > len(d):
            raise FormatError("bad row table")
        self.rows, self.stride, self.table, self.heap = rows, stride, table, end
        columns = []
        for j in range(stride // 4):
            values = [struct.unpack_from("<I", d, table + r * stride + 4 * j)[0] for r in range(rows)]
            used = [v for v in values if end <= v < len(d) - 1 and v % 2 == 0]
            # the other cells of a string column are all the same (0, or a "no string" marker)
            if used and len({v for v in values if v not in used}) <= 1 and self._texty(used):
                columns.append(j)
        if not columns:
            raise FormatError("no string column")
        self.columns = columns
        self.refs: dict = {}          # string offset -> [(row, column), ...]
        for r in range(rows):
            for j in columns:
                v = struct.unpack_from("<I", d, table + r * stride + 4 * j)[0]
                if end <= v < len(d) - 1 and v % 2 == 0:
                    self.refs.setdefault(v, []).append((r, j))
        self.offsets = list(self.refs)                 # first use first: the order survives a rebuild
        by_address = sorted(self.offsets)
        self.entries: List[bytes] = []
        self.capacity: List[int] = []
        for v in self.offsets:
            stop = self._nul(v)
            self.entries.append(d[v:stop + 2])
            size = stop + 2 - v
            nxt = by_address.index(v) + 1
            limit = by_address[nxt] if nxt < len(by_address) else len(d)
            self.capacity.append(min(size + -size % 4, max(limit - v, size)))
        self.strings = [decode(e, (v // 2) % 2) for e, v in zip(self.entries, self.offsets)]
        self.exact = [encode(s, False, (v // 2) % 2) == e for s, e, v in zip(self.strings, self.entries, self.offsets)]

    @property
    def count(self) -> int:
        return len(self.strings)

    def _nul(self, at: int) -> int:
        """Offset of the terminating NUL unit of the string at ``at`` (a command ``FFFx FFFF n 0 ...`` is skipped
        whole: it may hold zero units)."""
        d, i = self.data, at
        while i + 2 <= len(d):
            unit = d[i] | d[i + 1] << 8
            if unit == 0:
                return i
            if unit >= 0xFFF0 and i + 8 <= len(d) and d[i + 2] == 0xFF and d[i + 3] == 0xFF:
                i += 4 + (d[i + 4] | d[i + 5] << 8)
                continue
            i += 2
        raise FormatError("string without a terminator")

    def _texty(self, offsets: List[int]) -> bool:
        """Most of the strings at ``offsets`` are text (at least half of the units are not control units); empty
        strings do not count."""
        good = seen = 0
        for v in sorted(set(offsets)):
            try:
                stop = self._nul(v)
                units = struct.unpack(f"<{(stop - v) // 2}H", self.data[v:stop])
            except (FormatError, struct.error):
                return False
            if not units:
                continue
            seen += 1
            if sum(1 for u in units if not _is_control(u) and not 0xD800 <= u < 0xE000) * 2 >= len(units):
                good += 1
        return seen > 0 and good * 10 >= seen * 7

    def build(self, texts: List[str], allow_growth: bool = False) -> bytes:
        if len(texts) != self.count:
            raise FormatError(f"{len(texts)} strings for {self.count}")
        out = bytearray(self.data)
        moved = {}
        self.cut = []
        for k, text in enumerate(texts):
            if text == self.strings[k]:
                continue
            v = self.offsets[k]
            raw = encode(text, False, (v // 2) % 2)
            if len(raw) > self.capacity[k] and not allow_growth:
                self.cut.append(k)
                # ponytail: the cut can fall inside a {c:...} command; the editor shows the cut string, fix it there
                raw = raw[:self.capacity[k] // 2 * 2 - 2] + bytes(2)     # the text without its last unit, then NUL
            if len(raw) <= self.capacity[k]:
                out[v:v + self.capacity[k]] = raw + bytes(self.capacity[k] - len(raw))
                continue
            out += bytes((v % 4 - len(out)) % 4)       # the new place has the same 2-byte phase as the old one
            moved[v] = len(out)
            out += raw + bytes(-len(raw) % 4)
            # the old space becomes padding when no other string starts inside it
            if not any(v < o < v + len(self.entries[k]) for o in self.offsets):
                out[v:v + len(self.entries[k])] = bytes(len(self.entries[k]))
        for v, new in moved.items():
            for r, j in self.refs[v]:
                struct.pack_into("<I", out, self.table + r * self.stride + 4 * j, new)
        struct.pack_into("<I", out, 0x0C, len(out) - 0x20)
        return bytes(out)


def open_text(data: bytes):
    """The text file as a ``L5Text`` (index table) or a ``L5PtrText`` (rows of pointers); FormatError if neither."""
    try:
        return L5Text(data)
    except FormatError:
        return L5PtrText(data)
