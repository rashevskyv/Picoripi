"""Stella Glow event flows (``event/*.flw``) and string tables (``param/*.str``).

``.str``: UTF-16LE strings, each ended by a NUL. The game reads them by index, so a string may be any length.

``.flw`` (``FLW\\0``): a script of 32-bit words whose pointers are relative to their own position (a word at
``p`` with value ``v`` points to ``p + v``). Dialogue text is kept in pools of NUL-terminated UTF-16LE strings
written one after another; one word of the script points at the first string of a pool and the script reads
the next strings in turn, starting a sub-dialogue at a character offset stored in a record near the pool.
Those offsets are not decoded yet, so a string keeps the room it has: a longer text is refused, a shorter one
is padded with spaces up to the old length and everything else stays where it was.
"""
from __future__ import annotations

import struct
from typing import List, Optional, Tuple

MAGIC = b"FLW\0"
HEADER_SIZE = 0x28
_PUNCT = set(".!?¶…-,:;'’“”")


class FormatError(ValueError):
    """Not a flow file or a string table."""


class TooLong(ValueError):
    """A text does not fit in the room of the string it replaces."""


# ---------------------------------------------------------------- string tables

class StrTable:
    """A ``.str`` file: ``strings``, rebuilt as the NUL-terminated list."""

    def __init__(self, data: bytes):
        data = bytes(data)
        if len(data) % 2 or data[:4] == MAGIC:
            raise FormatError("not a UTF-16 string table")
        parts = data.decode("utf-16-le", "surrogatepass").split("\0")
        self.terminated = parts[-1] == ""
        self.strings = parts[:-1] if self.terminated else parts

    def build(self, texts: List[str]) -> bytes:
        if len(texts) != len(self.strings):
            raise FormatError(f"{len(texts)} strings for {len(self.strings)}")
        body = "\0".join(texts) + ("\0" if self.terminated else "")
        return body.encode("utf-16-le", "surrogatepass")


# ---------------------------------------------------------------- flows

def _valid_char(c: int) -> bool:
    """Latin (with extensions), Greek, Cyrillic and general punctuation: a translated flow is still found. The
    script's own words (0x7D0.. opcodes, flags, floats) fall outside these ranges."""
    return (0x20 <= c <= 0x24F or c in (0x09, 0x0A, 0x0D) or 0x370 <= c <= 0x52F or 0x1E00 <= c <= 0x1EFF
            or 0x2010 <= c <= 0x203A)


def _string_at(data: bytes, at: int, follows: bool = False) -> Optional[Tuple[int, int]]:
    """``(start, end)`` of the NUL-terminated UTF-16 string at ``at`` (end = the NUL's offset), or None. A string
    that follows another one may be a single punctuation mark (``…``)."""
    n, e = len(data), at
    while e + 2 <= n:
        c = data[e] | data[e + 1] << 8
        if c == 0:
            break
        if not _valid_char(c):
            return None
        e += 2
    else:
        return None
    if e == at:
        return None
    text = data[at:e].decode("utf-16-le", "surrogatepass")
    if follows and len(text) == 1 and text in _PUNCT:
        return at, e
    if len(text) < 2 or not (any(ch.isalpha() for ch in text) or sum(ch in _PUNCT for ch in text) >= 2):
        return None
    return at, e


def pools(data: bytes) -> List[List[Tuple[int, int]]]:
    """The string pools of a flow: ``[[(start, end), ...], ...]`` in file order. A pool starts at a string some
    word of the script points at (self-relative) and holds the strings that follow it back to back."""
    if data[:4] != MAGIC:
        raise FormatError("not a flow file")
    n = len(data)
    targets = set()
    for p in range(HEADER_SIZE, n - 3, 4):
        t = (p + struct.unpack_from("<i", data, p)[0]) & 0xFFFFFFFF
        if HEADER_SIZE <= t < n - 2 and t % 2 == 0:
            targets.add(t)
    out: List[List[Tuple[int, int]]] = []
    covered = 0
    for t in sorted(targets):
        if t < covered:
            continue
        first = _string_at(data, t, follows=True)       # a pool may open with a lone "…"
        if first is None:
            continue
        run = [first]
        while True:
            nxt = _string_at(data, run[-1][1] + 2, follows=True)
            if nxt is None:
                break
            run.append(nxt)
        if len(run) == 1 and first[1] - first[0] < 4:      # a lone one-character string is no pool
            continue
        out.append(run)
        covered = run[-1][1] + 2
    return out


class Flow:
    """A parsed flow: ``strings`` (editor text) in pool order; ``build`` writes edited texts into their rooms."""

    def __init__(self, data: bytes):
        self.data = bytes(data)
        self.slots = [slot for pool in pools(self.data) for slot in pool]
        self.raw = [self.data[s:e].decode("utf-16-le", "surrogatepass") for s, e in self.slots]
        self.crlf = [("\r\n" in r) and "\n" not in r.replace("\r\n", "") and "\r" not in r.replace("\r\n", "")
                     for r in self.raw]
        self.strings = [r.replace("\r\n", "\n") if c else r for r, c in zip(self.raw, self.crlf)]

    def room(self, index: int) -> int:
        """How many UTF-16 units string ``index`` may have."""
        s, e = self.slots[index]
        return (e - s) // 2

    def fit(self, texts: List[str]) -> Tuple[List[str], int]:
        """``texts`` with every text cut to the room of its string; how many were cut."""
        out, cut = [], 0
        for i, text in enumerate(texts):
            new = text.replace("\n", "\r\n") if self.crlf[i] else text
            room = self.room(i)
            if len(new.encode("utf-16-le", "surrogatepass")) // 2 > room:
                new = new[:room]
                while new and len(new.encode("utf-16-le", "surrogatepass")) // 2 > room:
                    new = new[:-1]
                text = new.replace("\r\n", "\n") if self.crlf[i] else new
                cut += 1
            out.append(text)
        return out, cut

    def build(self, texts: List[str]) -> bytes:
        if len(texts) != len(self.slots):
            raise FormatError(f"{len(texts)} strings for {len(self.slots)}")
        out = bytearray(self.data)
        for i, (text, (s, e)) in enumerate(zip(texts, self.slots)):
            if text == self.strings[i]:
                continue
            new = text.replace("\n", "\r\n") if self.crlf[i] else text
            raw = new.encode("utf-16-le", "surrogatepass")
            room = e - s
            if len(raw) > room:
                raise TooLong(f"string {i}: {len(raw) // 2} characters, room for {room // 2}")
            out[s:e] = raw + " ".encode("utf-16-le") * ((room - len(raw)) // 2)
        return bytes(out)
