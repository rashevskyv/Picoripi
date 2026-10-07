"""M2 (emote) PSB files: the value tree, its strings and resources (chunks); read and written back.

A PSB is a header, the names (a double-array trie), the value tree, the strings and the resources. ``load``
reads it into Python values (``F32``, ``Res`` and ``IntArray`` keep the stored kinds); ``dump`` writes
versions 2 and 3 back byte for byte when given the file's own name and string lists (checked on every v2/v3
file of Metal Gear Solid Master Collection). Version 4 files (fonts, pictures) are only read; their pixels
are changed in place (``Psb.chunk_spans`` gives each resource's place in the file).
"""
from __future__ import annotations

import struct
import zlib


class F32(float):
    """A float stored as 32 bits."""


class Res(int):
    """A resource (chunk) index."""


class IntArray(tuple):
    """A PSB number array (types 0x0D..0x14)."""


# ---------------------------------------------------------------- PSB reading

def _uint(data, pos, n):
    return int.from_bytes(data[pos:pos + n], "little")


class Psb:
    def __init__(self, data: bytes):
        if data[:4] != b"PSB\0":
            raise ValueError("not a PSB file")
        self.data = data
        self.version, self.flags = struct.unpack_from("<HH", data, 4)
        (_head, self.o_names, self.o_strs, self.o_strdata, self.o_choff, self.o_chlen, self.o_chdata,
         self.o_root) = struct.unpack_from("<8I", data, 8)
        charset, pos = self.array(self.o_names)
        tree, pos = self.array(pos)
        leaves, _ = self.array(pos)
        self.names = []
        for leaf in leaves:
            node, chars = tree[leaf], []
            while node:
                parent = tree[node]
                chars.append(node - charset[parent])
                node = parent
            self.names.append(bytes(reversed(chars)).decode("utf-8"))
        offsets, _ = self.array(self.o_strs)
        self.strings = [data[self.o_strdata + o:data.index(b"\0", self.o_strdata + o)].decode("utf-8")
                        for o in offsets]
        choff, _ = self.array(self.o_choff)
        chlen, _ = self.array(self.o_chlen)
        self.chunk_spans = [(self.o_chdata + o, n) for o, n in zip(choff, chlen)]

    @property
    def chunks(self):
        return [self.data[o:o + n] for o, n in self.chunk_spans]

    def array(self, pos):
        data = self.data
        n = data[pos] - 0x0C
        count = _uint(data, pos + 1, n)
        pos += 1 + n
        width = data[pos] - 0x0C
        pos += 1
        return [_uint(data, pos + i * width, width) for i in range(count)], pos + count * width

    def value(self, pos):
        data = self.data
        t = data[pos]
        if t == 1:
            return None
        if t in (2, 3):
            return t == 3
        if t == 4:
            return 0
        if 5 <= t <= 0x0C:
            return int.from_bytes(data[pos + 1:pos + t - 3], "little", signed=True)
        if 0x0D <= t <= 0x14:
            return IntArray(self.array(pos)[0])
        if 0x15 <= t <= 0x18:
            return self.strings[_uint(data, pos + 1, t - 0x14)]
        if 0x19 <= t <= 0x1C:
            return Res(_uint(data, pos + 1, t - 0x18))
        if t == 0x1D:
            return F32(0.0)
        if t == 0x1E:
            return F32(struct.unpack_from("<f", data, pos + 1)[0])
        if t == 0x1F:
            return struct.unpack_from("<d", data, pos + 1)[0]
        if t == 0x20:
            offsets, start = self.array(pos + 1)
            return [self.value(start + o) for o in offsets]
        if t == 0x21:
            names, q = self.array(pos + 1)
            offsets, start = self.array(q)
            return {self.names[n]: self.value(start + o) for n, o in zip(names, offsets)}
        raise ValueError(f"PSB value type {t:#x} at {pos:#x}")

    def root(self):
        return self.value(self.o_root)


def load(data: bytes):
    """(tree, Psb)"""
    psb = Psb(data)
    return psb.root(), psb


# ---------------------------------------------------------------- PSB writing

def _min_unsigned(value):
    return max(1, (value.bit_length() + 7) // 8)


def _array(values) -> bytes:
    values = list(values)
    count_width = _min_unsigned(len(values))
    width = _min_unsigned(max(values)) if values else 1
    return (bytes([0x0C + count_width]) + len(values).to_bytes(count_width, "little") + bytes([0x0C + width])
            + b"".join(v.to_bytes(width, "little") for v in values))


def _names_section(names):
    """charset, tree and leaf arrays of the double-array trie of ``names`` (index order), laid out as the
    game's own files are: depth first, children by byte, each base the lowest free one; a leaf's base is its
    name index."""
    trie, ends = [{}], []
    for name in names:
        node = 0
        for byte in name.encode("utf-8") + b"\0":
            nxt = trie[node].get(byte)
            if nxt is None:
                nxt = len(trie)
                trie.append({})
                trie[node][byte] = nxt
            node = nxt
        ends.append(node)
    base, check, place, used, free = {}, {}, {0: 0}, {0}, 1
    todo = [0]
    while todo:
        node = todo.pop()
        kids = sorted(trie[node].items())
        if not kids:
            continue
        b = max(1, free - kids[0][0])
        while any(b + c in used for c, _k in kids):
            b += 1
        base[place[node]] = b
        for c, child in kids:
            used.add(b + c)
            place[child] = b + c
            check[b + c] = place[node]
        while free in used:
            free += 1
        todo.extend(child for _c, child in reversed(kids))
    for index, end in enumerate(ends):
        base[place[end]] = index
    size = max(used) + 1
    return (_array([base.get(i, 0) for i in range(size)]) + _array([check.get(i, 0) for i in range(size)])
            + _array([place[e] for e in ends]))


class _Writer:
    def __init__(self, names, strings):
        self.names = {n: i for i, n in enumerate(names)}
        self.strings = {s: i for i, s in enumerate(strings)}

    def value(self, v) -> bytes:
        if v is None:
            return b"\x01"
        if v is True or v is False:
            return b"\x03" if v else b"\x02"
        if isinstance(v, Res):
            n = _min_unsigned(int(v))
            return bytes([0x18 + n]) + int(v).to_bytes(n, "little")
        if isinstance(v, int):
            if v == 0:
                return b"\x04"
            n = 1
            while not -(1 << (8 * n - 1)) <= v < (1 << (8 * n - 1)):
                n += 1
            return bytes([4 + n]) + v.to_bytes(n, "little", signed=True)
        if isinstance(v, F32):
            return b"\x1d" if v == 0 else b"\x1e" + struct.pack("<f", v)
        if isinstance(v, float):
            return b"\x1f" + struct.pack("<d", v)
        if isinstance(v, str):
            i = self.strings[v]
            n = _min_unsigned(i)
            return bytes([0x14 + n]) + i.to_bytes(n, "little")
        if isinstance(v, IntArray):
            return _array(v)
        if isinstance(v, list):
            return b"\x20" + self._items([self.value(x) for x in v])
        if isinstance(v, dict):
            keys = sorted(v, key=lambda k: self.names[k])
            return b"\x21" + _array([self.names[k] for k in keys]) + self._items([self.value(v[k]) for k in keys])
        raise TypeError(type(v))

    @staticmethod
    def _items(blobs) -> bytes:
        offsets, body, seen = [], bytearray(), {}
        for blob in blobs:
            at = seen.get(blob)
            if at is None:
                at = seen[blob] = len(body)
                body += blob
            offsets.append(at)
        return _array(offsets) + bytes(body)


def _collect(v, names, strings):
    if isinstance(v, str):
        strings.setdefault(v, None)
    elif isinstance(v, list):
        for x in v:
            _collect(x, names, strings)
    elif isinstance(v, dict):
        for k, x in v.items():
            names.setdefault(k, None)
            _collect(x, names, strings)


def dump(root, chunks=(), version=3, names=None, strings=None) -> bytes:
    """A PSB file (version 2 or 3) of ``root``; names and strings sorted unless given (a file's own lists
    give the file back byte for byte)."""
    if version not in (2, 3):
        raise ValueError("only PSB versions 2 and 3 are written")
    found_names, found_strings = {}, {}
    _collect(root, found_names, found_strings)
    names = sorted(found_names, key=lambda n: n.encode("utf-8")) if names is None else names
    strings = sorted(found_strings, key=lambda s: s.encode("utf-8")) if strings is None else strings
    w = _Writer(names, strings)
    head = 0x2C if version == 3 else 0x28
    names_blob = _names_section(names)
    root_blob = w.value(root)
    encoded = [s.encode("utf-8") + b"\0" for s in strings]
    str_offsets, pos = [], 0
    for e in encoded:
        str_offsets.append(pos)
        pos += len(e)
    strs_blob = _array(str_offsets)
    strdata = b"".join(encoded)
    ch_offsets, pos = [], 0
    for c in chunks:
        ch_offsets.append(pos)
        pos += len(c)
    choff_blob, chlen_blob = _array(ch_offsets), _array([len(c) for c in chunks])
    o_names = head
    o_root = o_names + len(names_blob)
    o_strs = o_root + len(root_blob)
    o_strdata = o_strs + len(strs_blob)
    o_choff = o_strdata + len(strdata)
    o_chlen = o_choff + len(choff_blob)
    o_chdata = o_chlen + len(chlen_blob)
    header = bytearray(b"PSB\0" + struct.pack("<HH", version, 0) + struct.pack(
        "<8I", head if version == 3 else 0, o_names, o_strs, o_strdata, o_choff, o_chlen, o_chdata, o_root))
    if version == 3:
        header += struct.pack("<I", zlib.adler32(bytes(header[8:40])))
    return bytes(header) + names_blob + root_blob + strs_blob + strdata + choff_blob + chlen_blob + b"".join(chunks)


def checksum(data: bytes) -> bytes:
    """``data`` with its PSB header checksum (versions 3 and 4) made right again."""
    version = struct.unpack_from("<H", data, 4)[0]
    if version < 3:
        return data
    extra = data[44:56] if version >= 4 else b""
    return data[:40] + struct.pack("<I", zlib.adler32(data[8:40] + extra)) + data[44:]
