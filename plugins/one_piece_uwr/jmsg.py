"""Ganbarion jMSG message tables of One Piece: Unlimited World Red (3DS).

jMSG, u32 file size, u32 key count, u32 language mask, then count x languages entries (u32 key hash, u32
offset from 0x10) -- one block of count entries per language, in the order of the mask's set bits (bit 0
Japanese, 4 English, 5 German, ...), each block sorted by key -- then the strings, UTF-16LE, each ended by a NUL.

The model shows the English block, in the order the strings lie in the file. Control sequences are shown as tags:
U+1A00 followed by U+F0xx characters becomes {c:xxxxxx} (the xx bytes: a colour or a reset), any other
private-use character {u:XXXX}, and a literal { becomes {u:007B}. The other languages' strings are
written back unchanged.
"""
from __future__ import annotations

import re
import struct
from typing import List, Sequence

MAGIC = b"jMSG"
ENGLISH_BIT = 4
_MARKUP = re.compile("ᨀ[-]*|[-{]")
_TAG = re.compile(r"\{(c|u):([0-9A-Fa-f]*)\}")


def to_editor(text: str) -> str:
    def tag(m):
        run = m.group()
        if run[0] == "ᨀ":
            return "{c:" + "".join("%02X" % (ord(c) - 0xF000) for c in run[1:]) + "}"
        return "{u:%04X}" % ord(run)
    return _MARKUP.sub(tag, text)


def from_editor(text: str) -> str:
    def back(m):
        if m.group(1) == "c":
            return "ᨀ" + "".join(chr(0xF000 + int(m.group(2)[i:i + 2], 16)) for i in range(0, len(m.group(2)), 2))
        return chr(int(m.group(2), 16))
    return _TAG.sub(back, text)


class Table:
    """A jMSG table. ``build`` returns the original bytes while no English string changed."""

    def __init__(self, raw: bytes):
        if raw[:4] != MAGIC or len(raw) < 0x10:
            raise ValueError("not a jMSG table")
        self.raw = bytes(raw)
        self.count, self.mask = struct.unpack_from("<II", raw, 8)
        langs = max(1, bin(self.mask).count("1"))
        self.total = self.count * langs
        if self.count == 0 or 0x10 + 8 * self.total > len(raw):
            raise ValueError("jMSG table is cut short")
        self.entries = [struct.unpack_from("<II", raw, 0x10 + 8 * i) for i in range(self.total)]
        if not self.mask >> ENGLISH_BIT & 1:
            raise ValueError("no English block")
        self.block = bin(self.mask & ((1 << ENGLISH_BIT) - 1)).count("1")
        self.pool_at = 0x10
        self.strings = {}
        for _key, off in self.entries:
            if off not in self.strings:
                a = 0x10 + off
                e = a
                while raw[e:e + 2] != b"\0\0":
                    e += 2
                self.strings[off] = raw[a:e].decode("utf-16-le")
        end = max((0x10 + off + 2 * len(s) + 2) for off, s in self.strings.items())
        self.tail = raw[end:]
        self.pool_order = sorted(self.strings)
        mine = self.entries[self.block * self.count:(self.block + 1) * self.count]
        self.cells = sorted(range(len(mine)), key=lambda i: mine[i][1])         # English entries in pool order
        self.mine = mine
        self._texts = [to_editor(self.strings[mine[i][1]]) for i in self.cells]

    def texts(self) -> List[str]:
        return list(self._texts)

    def ids(self) -> List[str]:
        return [f"{self.mine[i][0]:08X}" for i in self.cells]

    def build(self, texts: Sequence[str]) -> bytes:
        if list(texts) == self._texts:
            return self.raw
        if len(texts) != len(self.cells):
            raise ValueError(f"the table holds {len(self.cells)} strings, {len(texts)} were given")
        users = {}
        for entry_index, (_key, off) in enumerate(self.entries):
            users.setdefault(off, []).append(entry_index)
        items = [[off, self.strings[off]] for off in self.pool_order]        # [original offset, text], pool order
        own = {off: n for n, (off, _t) in enumerate(items)}
        target = {}                                                          # entry index -> item index
        for entry_index, (_key, off) in enumerate(self.entries):
            target[entry_index] = own[off]
        first = self.block * self.count
        for cell, text in zip(self.cells, texts):
            entry_index = first + cell
            new_text = from_editor(text)
            item = target[entry_index]
            if new_text == items[item][1]:
                continue
            if len(users[self.entries[entry_index][1]]) > 1:                 # shared with another entry: own copy
                items.append([-1, new_text])
                target[entry_index] = len(items) - 1
            else:
                items[item][1] = new_text
        where, pool, at = {}, [], 0
        for n, (_off, t) in enumerate(items):
            where[n] = at
            blob = t.encode("utf-16-le") + b"\0\0"
            pool.append(blob)
            at += len(blob)
        head = bytearray(self.raw[:0x10])
        for entry_index, (key, _off) in enumerate(self.entries):
            head += struct.pack("<II", key, 8 * self.total + where[target[entry_index]])
        out = bytearray(bytes(head) + b"".join(pool) + self.tail)
        struct.pack_into("<I", out, 4, len(out))
        return bytes(out)
