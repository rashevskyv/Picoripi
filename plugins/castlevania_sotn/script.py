"""Cutscene scripts and the staff roll of Symphony of the Night: parse into lines, write them back.

A cutscene script (stage overlays, ``SEL.BIN`` endings) is a byte stream: a byte below 25 is a
command with fixed parameters (``SCRIPT_SWITCH`` takes a list of pointers), any other byte is one
character of the 8x8 font (``cell + 0x20``). Pointers in a script are written one nibble per byte
pair (``84 4e e5 5d`` = ``0x80184E5D``). A line is the text from one dialogue page: the characters
from the first to the last one before a page command (``NEXT_DIALOG``, ``CLOSE_DIALOG``, a portrait,
...); a line break is ``\\n``; the other commands inside the text read as tags (``{WAIT 30}``,
``{SPEED 02}``) and must stay. Commands outside the text are kept as they are.

The staff roll (``SEL.BIN``) is a list of entries ``op x text`` (op 1-3); a line is one entry, its
op and parameter read as a leading tag (``{ENTRY 10}``).

A script keeps the room it has in the file: text may grow when other text of the same script
shrinks. Pointers into the script are moved with the text; ``anchors`` (offsets other code points
at) stay where they are.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import codec

NAMES = ("END", "LF", "SPEED", "WAIT", "HIDE", "PORTRAIT", "NEXT", "POS", "CLOSE", "SOUND", "WAITSOUND",
         "CMD11", "EVENTS", "CMD13", "SWITCH", "CMD15", "WAITFLAG", "SETFLAG", "CMD18", "LOADPORTRAIT",
         "CMD20", "CMD21", "RESETFLAG", "CMD23", "WAITRESET")
OPCODE = {name: op for op, name in enumerate(NAMES)}
# parameter widths (bytes); a 4-byte parameter is a nibble pointer
PARAMS = {0: (), 1: (), 2: (1,), 3: (1,), 4: (), 5: (1, 1), 6: (), 7: (1, 1), 8: (), 9: (2,), 10: (), 11: (),
          12: (4,), 13: (), 15: (4,), 16: (1,), 17: (1,), 18: (), 19: (4, 1), 20: (2,), 21: (), 22: (1,),
          23: (), 24: (1,)}
SWITCH = 14
JUMP = 15
# commands that end a line (a new page, a portrait, a voice clip, a jump): a line never spans them
PAGE = {0, 4, 5, 6, 8, 9, 11, 12, 14, 19}
LF = 1
TAG_RE = re.compile(r"\{([A-Z0-9]+)((?: [0-9a-f]+)*)\}")
CREDITS_OPS = ("END", "SUBTEXT", "ENTRY", "SECTION")


class ScriptError(ValueError):
    """The text does not fit the script."""


def read_pointer(raw: bytes) -> int:
    return 0x80100000 | raw[0] << 12 | raw[1] << 8 | raw[2] << 4 | raw[3]


def write_pointer(address: int) -> bytes:
    nibbles = [(address >> shift) & 0xF for shift in (16, 12, 8, 4, 0)]
    return bytes(nibbles[i] << 4 | nibbles[i + 1] for i in range(4))


def _is_pointer(raw: bytes) -> bool:
    return len(raw) == 4 and all(raw[i] & 0x0F == raw[i + 1] >> 4 for i in range(3))


@dataclass
class Op:
    at: int                  # offset in the file
    code: int                # command number, or -1 for a character
    raw: bytes               # the whole op (command byte and parameters, or the character byte(s))

    @property
    def is_char(self) -> bool:
        return self.code < 0


def _op_at(data: bytes, i: int, end: int) -> Op:
    b = data[i]
    if b < len(NAMES):
        if b == SWITCH:
            j = i + 5
            while j + 4 <= end and _is_pointer(data[j:j + 4]):
                j += 4
        else:
            j = i + 1 + sum(PARAMS[b])
        return Op(i, b, bytes(data[i:min(j, end)]))
    return Op(i, -1, bytes(data[i:i + 1]))


def parse_ops(data: bytes, start: int, end: int) -> List[Op]:
    ops = []
    i = start
    while i < end:
        op = _op_at(data, i, end)
        ops.append(op)
        i += len(op.raw)
    return ops


def parse_flow(data: bytes, start: int, end: int, base: int, spare: Sequence[Sequence[int]] = ()) -> List[Op]:
    """The script's ops in the order the game runs them: a jump (command 15) into a free range of the
    file (``spare``: where a translation that outgrew the region continues) is followed, and so is the
    jump back."""
    ops = []
    i = start
    while i < end:
        op = _op_at(data, i, end)
        target = read_pointer(op.raw[1:5]) - base if op.code == JUMP and len(op.raw) == 5 else -1
        if not any(a <= target < b for a, b in spare):
            ops.append(op)
            i += len(op.raw)
            continue
        j, resume = target, i + len(op.raw)
        for _guard in range(0x10000):
            inner = _op_at(data, j, len(data))
            if inner.code == JUMP:
                back = read_pointer(inner.raw[1:5]) - base
                resume = back if start <= back <= end else resume
                break
            ops.append(inner)
            j += len(inner.raw)
            if inner.code == 0:
                break
        i = resume
    return ops


def _tag(op: Op) -> str:
    params = op.raw[1:]
    widths = PARAMS.get(op.code) or (4,) * (len(params) // 4)
    parts, pos = [], 0
    for width in widths:
        parts.append(params[pos:pos + width].hex())
        pos += width
    return "{" + " ".join([NAMES[op.code], *parts]) + "}"


def _untag(name: str, params: str) -> bytes:
    if name not in OPCODE:
        raise ScriptError(f"unknown script command {{{name}}}")
    return bytes([OPCODE[name]]) + b"".join(bytes.fromhex(p) for p in params.split())


@dataclass
class Line:
    first: int               # index of the first op of the line
    last: int                # index after the last op
    speaker: int = -1        # portrait (actor) shown with the line


def lines_of(ops: Sequence[Op]) -> List[Line]:
    lines: List[Line] = []
    start = last_char = -1
    speaker = -1
    for index, op in enumerate(ops):
        if op.code == 5 and len(op.raw) > 1:
            speaker = op.raw[1]
        if op.is_char:
            if start < 0:
                start = index
            last_char = index
        elif op.code in PAGE and start >= 0:
            lines.append(Line(start, last_char + 1, speaker))
            start = last_char = -1
    if start >= 0:
        lines.append(Line(start, last_char + 1, speaker))
    return lines


def line_text(ops: Sequence[Op], line: Line, reverse_map: Optional[Dict[str, str]] = None) -> str:
    out = []
    chars = bytearray()

    def flush():
        if chars:
            out.append(codec.decode_cells(bytes(chars), codec.CS_OFFSET, reverse_map))
            chars.clear()
    for op in ops[line.first:line.last]:
        if op.is_char:
            chars += op.raw
            continue
        flush()
        out.append("\n" if op.code == LF else _tag(op))
    flush()
    return "".join(out)


def encode_line(text: str, mapping: Optional[Dict[str, str]] = None, missing: Optional[Set[str]] = None) -> bytes:
    out = bytearray()
    pos = 0
    for match in TAG_RE.finditer(text):
        out += _chars(text[pos:match.start()], mapping, missing)
        out += _untag(match.group(1), match.group(2))
        pos = match.end()
    out += _chars(text[pos:], mapping, missing)
    return bytes(out)


def _chars(text: str, mapping, missing) -> bytes:
    out = bytearray()
    for part in re.split(r"(\n)", text):
        if part == "\n":
            out.append(LF)
        elif part:
            out += codec.encode_cells(part, codec.CS_OFFSET, mapping, missing)
    return bytes(out)


class Spare:
    """Free byte ranges of a file (data the game never reads) that text may move to; shared by one save."""

    def __init__(self, ranges: Sequence[Sequence[int]] = ()):
        self.free = [[int(a), int(b)] for a, b in ranges]
        self.writes: List[Tuple[int, bytes]] = []

    def take(self, size: int, align: int = 1) -> Optional[int]:
        for gap in self.free:
            at = -(-gap[0] // align) * align
            if at + size <= gap[1]:
                gap[0] = at + size
                return at
        return None

    @property
    def room(self) -> int:
        return sum(b - a for a, b in self.free)


def build(data: bytes, start: int, end: int, new_lines: Dict[int, bytes], base: int,
          anchors: Sequence[int] = (), spare: Optional[Spare] = None) -> bytes:
    """The script region ``[start, end)`` with line ``i`` replaced by ``new_lines[i]`` (encoded bytes).

    Each stretch between two anchors keeps its size. A stretch that no longer fits ends with a jump
    (command 15) to a free range of the file (``spare``), where the rest of it goes, followed by a
    jump back. Nibble pointers to places inside the region follow the text. The bytes placed in free
    ranges are added to ``spare.writes``."""
    ops = parse_ops(data, start, end)
    lines = lines_of(ops)
    pieces: List[Tuple[int, bytes]] = []      # (old offset of the piece, new bytes)
    index = 0
    by_first = {line.first: (n, line) for n, line in enumerate(lines)}
    while index < len(ops):
        if index in by_first and by_first[index][0] in new_lines:
            number, line = by_first[index]
            pieces.append((ops[index].at, new_lines[number]))
            index = line.last
            continue
        pieces.append((ops[index].at, ops[index].raw))
        index += 1
    stops = sorted({start, end, *[a for a in anchors if start < a < end]})
    segments: List[Tuple[int, int, List[Tuple[int, bytes]]]] = []   # (new offset, room, pieces)
    moved: Dict[int, int] = {end: end}
    for left, right in zip(stops, stops[1:]):
        stretch = [(old, raw) for old, raw in pieces if left <= old < right]
        # the END bytes after the stretch's last END are padding: the text may use them
        while len(stretch) > 1 and stretch[-1][1] == b"\x00" and stretch[-2][1] == b"\x00":
            stretch.pop()
        room = right - left
        size = sum(len(raw) for _old, raw in stretch)
        if size <= room:
            segments.append((left, room, stretch))
            continue
        jump_back = not (stretch and stretch[-1][1] == b"\x00") and right < end
        keep, used = [], 0
        for old, raw in stretch:
            if used + len(raw) + 5 > room:
                break
            keep.append((old, raw))
            used += len(raw)
        rest = stretch[len(keep):]
        rest_size = sum(len(raw) for _old, raw in rest) + (5 if jump_back else 0)
        at = spare.take(rest_size) if spare is not None else None
        if at is None:
            free = spare.room if spare is not None else 0
            raise ScriptError(f"the script at {left:#x} is {size - room} bytes too long (room {room} bytes, "
                              f"{free} bytes free elsewhere in the file); shorten its text")
        keep.append((-1, bytes([JUMP]) + write_pointer(base + at)))
        if jump_back:
            rest.append((-1, bytes([JUMP]) + write_pointer(base + right)))
        segments.append((left, room, keep))
        segments.append((at, rest_size, rest))
    for new_at, _room, stretch in segments:
        cursor = new_at
        for old, raw in stretch:
            if old >= 0:
                moved[old] = cursor
            cursor += len(raw)
    out = bytearray(data[start:end])
    for new_at, room, stretch in segments:
        chunk = bytearray(b"".join(raw for _old, raw in stretch))
        for op in parse_ops(bytes(chunk), 0, len(chunk)):
            if op.is_char or op.code not in (12, 14, 15, 19):
                continue
            for k in range(1, len(op.raw) - 3, 4):
                if op.code == 19 and k > 1:
                    break
                raw = op.raw[k:k + 4]
                if not _is_pointer(raw):
                    continue
                target = read_pointer(raw) - base
                if start <= target < end and target in moved and moved[target] != target:
                    chunk[op.at + k:op.at + k + 4] = write_pointer(base + moved[target])
        if start <= new_at < end:
            out[new_at - start:new_at - start + room] = bytes(chunk) + bytes(room - len(chunk))
        else:
            spare.writes.append((new_at, bytes(chunk)))
    return bytes(out)


# ---------------------------------------------------------------- staff roll

def credit_entries(data: bytes, start: int, end: int) -> List[Tuple[int, int, int, bytes]]:
    """``(offset, op, x, text bytes)`` of every entry; text bytes 0x80-0x9F come in pairs."""
    out = []
    i = start
    while i < end:
        op = data[i]
        if op == 0:
            out.append((i, 0, 0, b""))
            i += 1
            continue
        if op > 3:
            raise ScriptError(f"staff roll: unknown op {op:#x} at {i:#x}")
        x = data[i + 1]
        j = i + 2
        while j < end and data[j] > 3:
            j += 2 if 0x80 <= data[j] <= 0x9F else 1
        out.append((i, op, x, bytes(data[i + 2:j])))
        i = j
    return out


def credit_text(op: int, x: int, raw: bytes, reverse_map=None) -> str:
    return "{%s %02x}" % (CREDITS_OPS[op], x) + codec.decode_cells(raw, codec.CS_OFFSET, reverse_map)


def encode_credit(text: str, mapping=None, missing=None) -> bytes:
    match = re.match(r"\{(SUBTEXT|ENTRY|SECTION) ([0-9a-f]{2})\}", text)
    if not match:
        raise ScriptError(f"a staff roll line must start with its tag ({{ENTRY 10}}): {text[:30]!r}")
    body = codec.encode_cells(text[match.end():], codec.CS_OFFSET, mapping, missing)
    if any(b <= 3 for b in body):
        raise ScriptError("a staff roll line holds a control byte")
    return bytes([CREDITS_OPS.index(match.group(1)), int(match.group(2), 16)]) + body


def build_credits(data: bytes, start: int, end: int, new: Dict[int, bytes]) -> bytes:
    """The staff roll region with entry ``i`` (counting text entries) replaced by ``new[i]``."""
    out = bytearray()
    number = 0
    for at, op, x, raw in credit_entries(data, start, end):
        if op == 0:
            out.append(0)
            continue
        out += new.get(number, bytes([op, x]) + raw)
        number += 1
    if len(out) > end - start:
        raise ScriptError(f"the staff roll is {len(out) - (end - start)} bytes too long; shorten it")
    return bytes(out + bytes(end - start - len(out)))
