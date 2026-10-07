"""Lunar event scripts (``TEXT*.DAT``): find the text in the byte code and rebuild a file with new text.

A script file starts with 1024 little-endian u16 labels (word offsets, 0 = unused); every jump, call
and branch of the byte code names a label, never an address. The code is a stream of u16 opcodes with
their arguments (lengths below, read from the game's interpreter, SLUS_006.28 0x800B333C). Text lives
in two instructions:

- ``0x0002`` message: the text right after the opcode, up to its end (``codec.message_end``), padded to
  an even length;
- ``0x0007`` yes/no choice: label, two bytes, then two strings ended by 0xFF, padded to an even length.

Walking the code from every label finds every reachable instruction. A rebuilt file moves the code after
each changed text and points the labels at the new places. Each text keeps its length modulo 4
(``pad``) so the four instructions that align an argument to 4 bytes (28-30, 61) stay as they were.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

LABELS = 1024
HEADER = LABELS * 2
MESSAGE, CHOICE = 2, 7

_FIXED = {3: 4, 4: 4, 5: 2, 31: 4, 32: 4, 33: 6, 34: 6, 35: 4, 36: 6, 40: 4, 41: 4, 42: 4, 43: 8, 44: 6, 45: 6,
          46: 4, 47: 2, 48: 4, 49: 4, 50: 2, 51: 4, 57: 2, 58: 2, 59: 2, 60: 2, 63: 2, 64: 2, 66: 6, 67: 4, 68: 4,
          69: 4, 70: 6, 71: 4, 72: 4, 73: 4, 76: 2, 77: 2, 80: 6, 81: 2, 82: 4, 83: 2, 84: 2, 85: 4, 86: 4, 87: 4,
          88: 2, 89: 4, 90: 4, 91: 2, 92: 2, 94: 2, 95: 4, 96: 4}
_WORD_LIST = {8: 2, 9: 2, 10: 2, 11: 4, 12: 4, 13: 4}                      # u16 list ended by 0
_BYTE_LIST = {14: 2, 15: 2, 16: 4, 17: 4, 18: 4, 24: 2, 25: 2, 37: 2, 53: 2, 62: 2, 65: 2, 78: 3, 79: 2}
_PAIR_LIST = {19: 2, 20: 2, 21: 4, 22: 4, 23: 4, 26: 2}                   # 2-byte items, first byte 0 ends
_ACTOR_STEP = {0xF0: 2, 0xF1: 2, 0xF2: 2, 0xF3: 5, 0xF4: 5, 0xF5: 2, 0xF6: 2, 0xF7: 5, 0xF8: 4}
END_OPS = {3, 5, 38, 66, 94}          # goto, return, scene change + goto, jump, stop: no fall-through


class ScriptError(ValueError):
    """The file is not a Lunar script or holds an instruction this parser does not know."""


def _even(n: int) -> int:
    return n + (n & 1)


def message_end(data: bytes, at: int) -> int:
    """Offset just after the text that starts at ``at``: 0x05 inside a 0x0E (compressed) run, or 0xFF
    outside one, ends it (the game's decoder, SLUS_006.28 0x8005A884)."""
    p = at
    while True:
        b = data[p]
        if b == 0xFF:
            return p + 1
        if b == 0x0E:
            p += 1
            while True:
                c = data[p]
                p += 1
                if c == 0:
                    break
                if c == 0x05:
                    return p
                if c in (0xFD, 0xFE):
                    p += 1
            continue
        p += 2 if b >= 0xD6 else 1


def string_end(data: bytes, at: int) -> int:
    """Offset just after a 0xFF-ended string (a choice; the game scans for the byte itself)."""
    return data.index(b"\xff", at) + 1


def _list_end(data: bytes, at: int, item: int, word: bool) -> int:
    p = at
    while (struct.unpack_from("<H", data, p)[0] if word else data[p]) != 0:
        p += item
    return p + 2 if word else _even(p + 1)


def length(data: bytes, o: int) -> int:
    """Byte length of the instruction at ``o``."""
    op = struct.unpack_from("<H", data, o)[0]
    if op in _FIXED:
        return _FIXED[op]
    if op == MESSAGE:
        return _even(message_end(data, o + 2)) - o
    if op == CHOICE:
        return _even(string_end(data, string_end(data, o + 6))) - o
    if op in _WORD_LIST:
        return _list_end(data, o + _WORD_LIST[op], 2, True) - o
    if op in _BYTE_LIST:
        return _list_end(data, o + _BYTE_LIST[op], 1, False) - o
    if op in _PAIR_LIST:
        return _list_end(data, o + _PAIR_LIST[op], 2, False) - o
    if op in (28, 29, 30):                           # byte or label, then a u32 aligned to 4
        return (((o + 2) & ~3) + 8) - o
    if op == 61:
        return ((o & ~3) + 8) - o
    if op == 38:                                     # load a scene, then jump
        return 8 if data[o + 4] else 18
    if op == 39:
        return 4 if data[o + 2] else 14
    if op == 52:
        return 4 if data[o + 2] < 11 else 16
    if op == 56:                                     # actor moves: steps 0xF0-0xF8 until 0xF9
        p = o + 3
        while data[p] != 0xF9:
            step = _ACTOR_STEP.get(data[p])
            if step is None:
                raise ScriptError(f"actor step 0x{data[p]:02X} at 0x{p:X}")
            p += step
        return _even(p + 1) - o
    raise ScriptError(f"unknown opcode {op} at 0x{o:X}")


@dataclass
class Text:
    """One text of a script: a message or a choice (``strings`` = byte ranges of its strings)."""

    kind: int
    start: int
    size: int
    strings: List[Tuple[int, int]]


def labels(data: bytes) -> Tuple[int, ...]:
    if len(data) < HEADER + 2:
        raise ScriptError("too short for a script")
    return struct.unpack_from(f"<{LABELS}H", data, 0)


def parse(data: bytes) -> List[Text]:
    """Every message and choice reachable from the labels, in file order."""
    targets = sorted({value * 2 for value in labels(data) if value})
    if not targets or targets[0] < HEADER or targets[-1] > len(data):
        raise ScriptError("label table does not point into the file")
    seen: Dict[int, Text] = {}
    visited = set()
    for start in targets:
        o = start
        while o < len(data) and o not in visited:
            visited.add(o)
            op = struct.unpack_from("<H", data, o)[0]
            if op >= 97:                             # data behind a label (debug tables): not code
                break
            size = length(data, o)
            if op == MESSAGE:
                seen[o] = Text(MESSAGE, o, size, [(o + 2, message_end(data, o + 2))])
            elif op == CHOICE:
                first = string_end(data, o + 6)
                seen[o] = Text(CHOICE, o, size, [(o + 6, first), (first, string_end(data, first))])
            if op in END_OPS:
                break
            o += size
    return [seen[o] for o in sorted(seen)]


def pad(body: bytes, old_size: int, head: int, terminator: int, filler: bytes) -> bytes:
    """``head`` + ``body`` padded so its even length differs from ``old_size`` by a multiple of 4.

    ``filler`` (two bytes the game skips) goes before the terminator byte at the end of ``body``.
    """
    size = _even(head + len(body))
    if (size - old_size) % 4:
        body = body[:-1] + filler + body[-1:]
        size += 2
    if body[-1] != terminator:
        raise ScriptError("text without its terminator")
    return body + bytes(size - head - len(body))


def rebuild(data: bytes, replaced: Dict[int, bytes]) -> bytes:
    """``data`` with the instructions at the given offsets replaced (``{start: new instruction bytes}``)."""
    if not replaced:
        return bytes(data)
    texts = {text.start: text for text in parse(data)}
    out = bytearray(data[:HEADER])
    moves: List[Tuple[int, int]] = []                # (old offset, shift for offsets at or after it)
    shift = 0
    pos = HEADER
    for start in sorted(replaced):
        text = texts.get(start)
        if text is None:
            raise ScriptError(f"no text at 0x{start:X}")
        new = replaced[start]
        if (len(new) - text.size) % 4:
            raise ScriptError(f"text at 0x{start:X}: length changes by {len(new) - text.size}, not a multiple of 4")
        out += data[pos:start]
        out += new
        pos = start + text.size
        shift += len(new) - text.size
        moves.append((pos, shift))
    out += data[pos:]

    def moved(offset: int) -> int:
        result = offset
        for after, delta in moves:
            if offset >= after:
                result = offset + delta
            else:
                break
        return result

    for index, value in enumerate(labels(data)):
        if value:
            offset = value * 2
            for start in replaced:
                if start < offset < start + texts[start].size:
                    raise ScriptError(f"label {index} points inside the text at 0x{start:X}")
            new = moved(offset)
            if new // 2 > 0xFFFF:
                raise ScriptError("script grew past 128 KB")
            struct.pack_into("<H", out, index * 2, new // 2)
    return bytes(out)


def find(texts: List[Text], start: int) -> Optional[Text]:
    for text in texts:
        if text.start == start:
            return text
    return None
