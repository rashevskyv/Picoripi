"""Where Vagrant Story keeps its text, file by file, and how each place is rewritten.

Three kinds of places:

``Table``
    A string table: ``u16`` offsets in half-words, then the strings (each ends with 0xE7 and is
    padded to an even length with 0xEB). In most tables the first offset is also the count
    (the strings start right after the table); a help file (``.HF0``) has the count in front.
    A rewritten table is laid out again inside its region (equal strings share their bytes).
``Slot``
    A string in a field of fixed size (item names: 24 bytes, monster names: 28, room names: 32)
    or a string inside program data: rewritten in place, never longer than its room.
``Script``
    The script section of an event (``EVENT/*.EVT``) or a room (``MAP/*.MPD``): a 16-byte header
    (section length, then the offsets of the dialog table and of two data blocks after it), the
    opcodes, the dialog table, the two blocks. When the dialog grows, the blocks after it move and
    the header follows (the Russian fan translation does the same in ``0066.EVT``); an event stays
    6144 bytes, a room may grow to the end of its last CD sector (the zone file reserves whole
    sectors for each room).

Every other file keeps its size: the game loads them by size and allocates buffers for that size.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import codec

SECTOR = 2048
EVENT_SIZE = 6144
# Lengths of the 256 script opcodes, as BATTLE.PRG's table has them (0 = not used by the game).
OPCODE_LENGTHS = bytes.fromhex(
    "010a030304120b0b26000101010303010b0402090202040607010104020204050906060507090c070a07070606070a"
    "030606060b08070705060a040102020a04060603010203030401030403030201010404050304020304020407040704"
    "030203030201020203050a040402040201020804030202010105020302050203040105040501030302020201000000"
    "000005030204030303010201020305050201020502020101010200020205000000000000020804070307060103020301"
    "020103070103030409000a0b020a0300000000070103030409000a0b020a03000002020202060605060502030304040405"
    "000602020502020402030101010101010101")
DIALOG_SHOW, DIALOG_TEXT = 0x10, 0x11


class FormatError(ValueError):
    """The bytes are not the structure they were taken for, or the text does not fit."""


# -- strings ---------------------------------------------------------------------------------

def valid_string(data: bytes, start: int, limit: int) -> Optional[int]:
    """End (after 0xE7) of a well-formed string at ``start`` that ends before ``limit``, else None."""
    i = start
    while i < limit:
        code = data[i]
        if code == codec.END:
            return i + 1
        if code >= codec.PARAM_FIRST:
            i += 2
        elif code in codec.CHARS or code in codec.SIMPLE_TAGS or code in (codec.NEWLINE, codec.PAD):
            i += 1
        else:
            return None
    return None


# -- string tables ---------------------------------------------------------------------------

@dataclass
class Table:
    """A string table at ``start``; offsets count half-words from ``base``."""

    start: int
    count: int
    base: int
    refs: int                       # where the offsets begin
    region_end: int                 # the table may use bytes up to here when rewritten
    offsets: List[int] = field(default_factory=list)

    def string_at(self, data: bytes, index: int) -> bytes:
        begin = self.base + self.offsets[index] * 2
        return data[begin:codec.string_end(data, begin)]

    def strings(self, data: bytes) -> List[bytes]:
        return [self.string_at(data, i) for i in range(self.count)]

    @property
    def header_size(self) -> int:
        return self.refs + self.count * 2 - self.start

    def used_end(self, data: bytes) -> int:
        ends = [codec.string_end(data, self.base + o * 2) for o in self.offsets]
        end = max(ends + [self.refs + self.count * 2])
        return end + (end & 1)

    def build(self, raws: Sequence[bytes]) -> bytes:
        """The table and its strings (``raws`` end with 0xE7), equal strings stored once."""
        head = bytearray(self.refs - self.start)          # the count in front, if any
        if head:
            struct.pack_into("<H", head, 0, self.count)
        body = bytearray()
        first = self.refs + self.count * 2 - self.base
        placed: Dict[bytes, int] = {}
        offsets = []
        for raw in raws:
            raw = raw if len(raw) % 2 == 0 else raw + bytes((codec.PAD,))
            if raw not in placed:
                placed[raw] = (first + len(body)) // 2
                body += raw
            offsets.append(placed[raw])
        if offsets and offsets[0] > 0xFFFF or any(o > 0xFFFF for o in offsets):
            raise FormatError("string table too large")
        out = bytes(head) + struct.pack(f"<{len(offsets)}H", *offsets) + bytes(body)
        return out


def read_table(data: bytes, start: int, region_end: Optional[int] = None, count_in_front: bool = False,
               min_letters: int = 1) -> Optional[Table]:
    """The table at ``start`` if every offset leads to a well-formed string inside the region."""
    end = len(data) if region_end is None else region_end
    if start + 2 > end:
        return None
    if count_in_front:
        count = struct.unpack_from("<H", data, start)[0]
        refs = start + 2
        first_expected = count + 1
    else:
        count = struct.unpack_from("<H", data, start)[0]
        refs = start
        first_expected = count
    if not 1 <= count <= 4000 or refs + count * 2 > end:
        return None
    offsets = list(struct.unpack_from(f"<{count}H", data, refs))
    if offsets[0] != first_expected:
        return None
    letters = 0
    for offset in offsets:
        begin = start + offset * 2
        if begin < refs + count * 2 or begin >= end:
            return None
        stop = valid_string(data, begin, end)
        if stop is None:
            return None
        letters += sum(1 for code, param in codec.tokens(data[begin:stop]) if param is None and 0x0A <= code <= 0x85)
    if letters < min_letters:
        return None
    return Table(start, count, start, refs, end, offsets)


def write_table(data: bytearray, table: Table, raws: Sequence[bytes], what: str) -> None:
    """Put the rebuilt table into ``data`` (zero-filling what it no longer uses)."""
    built = table.build(raws)
    room = table.region_end - table.start
    if len(built) > room:
        raise FormatError(f"{what}: the text needs {len(built) - room} more bytes than its {room} "
                          f"(shorten some lines)")
    data[table.start:table.start + len(built)] = built
    data[table.start + len(built):table.region_end] = bytes(room - len(built))


# -- script sections (events, rooms) ----------------------------------------------------------

@dataclass
class Dialog:
    """How a dialog string is shown: the box of the DialogShow before the DialogText."""

    chars_per_line: int
    line_count: int


@dataclass
class Script:
    """A script section at ``start`` of a file (events: the whole file)."""

    start: int
    length: int
    text: int                      # dialog table offset inside the section
    block1: int
    block2: int
    table: Optional[Table]
    dialogs: Dict[int, Dialog] = field(default_factory=dict)      # text id -> box


def read_script(data: bytes, start: int, length: int) -> Optional[Script]:
    if length < 16 or start + length > len(data):
        return None
    sec_len, text, block1, block2 = struct.unpack_from("<4H", data, start)
    if sec_len != length and not (sec_len <= length):
        return None
    if not (0x10 <= text <= block1 <= block2 <= sec_len <= length) or any(data[start + 8:start + 16]):
        return None
    dialogs = {}
    boxes: Dict[int, Dialog] = {}
    i = start + 0x10
    while i < start + text:
        op = data[i]
        size = OPCODE_LENGTHS[op]
        if size == 0:
            return None
        if op == DIALOG_SHOW and i + size <= start + text:
            boxes[data[i + 1] & 0xF] = Dialog(data[i + 6], data[i + 7])
        elif op == DIALOG_TEXT and i + size <= start + text:
            box = boxes.get(data[i + 1] & 0xF)
            if box is not None:
                dialogs.setdefault(data[i + 2], box)
        i += size
    if i != start + text:
        return None
    table = None
    if block1 > text:
        table = read_table(data, start + text, start + block1, min_letters=0)
        if table is None:
            return None
    return Script(start, sec_len, text, block1, block2, table, dialogs)


def rebuild_script(data: bytes, script: Script, raws: Sequence[bytes], limit: int, what: str) -> Tuple[bytes, int]:
    """The section with a new dialog table; returns ``(section bytes, growth)``. ``limit`` is the
    largest section length the file allows."""
    assert script.table is not None
    sec = data[script.start:script.start + script.length]
    built = script.table.build(raws)
    old_room = script.block1 - script.text
    if len(built) <= old_room:          # fits where it was: nothing else moves
        new = bytearray(sec)
        new[script.text:script.text + len(built)] = built
        new[script.text + len(built):script.block1] = bytes(old_room - len(built))
        return bytes(new), 0
    grow = len(built) - old_room
    grow += (-grow) % 4                 # the blocks after the table stay 4-aligned
    new_len = script.length + grow
    if new_len > limit or new_len > 0xFFFF:
        raise FormatError(f"{what}: the dialog needs {new_len - limit} more bytes than the file can hold "
                          f"(shorten some lines)")
    new = bytearray(sec[:script.text]) + built + bytes(old_room + grow - len(built)) + sec[script.block1:]
    struct.pack_into("<4H", new, 0, script.length + grow, script.text, script.block1 + grow, script.block2 + grow)
    return bytes(new), grow


# -- whole files --------------------------------------------------------------------------------

MPD_SECTIONS = 6


def mpd_header(data: bytes) -> Optional[List[Tuple[int, int]]]:
    """The six ``(offset, length)`` sections of a room file, or None."""
    if len(data) < 0x30:
        return None
    values = struct.unpack_from("<12I", data, 0)
    sections = [(values[i], values[i + 1]) for i in range(0, 12, 2)]
    if sections[0][0] != 0x30:
        return None
    for (offset, length), (nxt, _l) in zip(sections, sections[1:]):
        if offset + length != nxt:
            return None
    last = sections[-1]
    if last[0] + last[1] > len(data):
        return None
    return sections


def is_event(data: bytes) -> bool:
    if len(data) != EVENT_SIZE:
        return False
    sec_len = struct.unpack_from("<H", data, 0)[0]
    return 0x10 <= sec_len <= EVENT_SIZE and read_script(data, 0, sec_len) is not None and not any(data[sec_len:])


def slot_strings(data: bytes, size: int) -> Optional[List[bytes]]:
    """Fixed fields of ``size`` bytes, each a string (or empty): ``ITEMNAME.BIN``."""
    if len(data) % size or len(data) < size * 8:
        return None
    out = []
    for at in range(0, len(data), size):
        stop = valid_string(data, at, at + size)
        if stop is None:
            return None
        if any(data[stop:at + size]):
            return None
        out.append(data[at:stop - 1])
    return out


MONSTER_COUNT, MONSTER_RECORD, MONSTER_NAME = 150, 44, 16


def is_monster_file(data: bytes) -> bool:
    return len(data) > MONSTER_COUNT * MONSTER_RECORD and read_table(
        data, MONSTER_COUNT * MONSTER_RECORD) is not None and all(
        valid_string(data, i * MONSTER_RECORD + MONSTER_NAME, (i + 1) * MONSTER_RECORD) is not None
        for i in range(MONSTER_COUNT))


ROOM_NAME, ROOM_INFO = 32, 36


def area_rooms(data: bytes) -> Optional[List[Tuple[int, int, int]]]:
    """``[(zone, room, name offset)]`` of an area map (``SMALL/SCEN*.ARM``), or None."""
    if len(data) < 4:
        return None
    count = struct.unpack_from("<I", data, 0)[0]
    if not 1 <= count <= 128 or 4 + count * 12 > len(data):
        return None
    heads = [struct.unpack_from("<IIHH", data, 4 + i * 12) for i in range(count)]
    if any(h[0] for h in heads):
        return None
    names = 4 + count * 12 + sum(h[1] for h in heads)        # after every room's geometry
    if len(data) - names != count * ROOM_INFO:
        return None
    out = []
    for i, (_zero, _size, zone, room) in enumerate(heads):
        at = names + i * ROOM_INFO
        if valid_string(data, at, at + ROOM_NAME) is None:
            return None
        out.append((zone, room, at))
    return out


def help_table(data: bytes) -> Optional[Table]:
    """The text table of a help file (``SMALL/HELP*.HF0``): header, then count and offsets."""
    if len(data) < 18:
        return None
    text_len, sprites, _lines, reserved = struct.unpack_from("<4I", data, 0)
    if reserved or 16 + text_len + sprites > len(data):
        return None
    table = read_table(data, 16, 16 + text_len, count_in_front=True)
    if table is None:
        return None
    return table


def _reads_as_text(data: bytes, table: Table) -> bool:
    from .program import looks_like_text
    texts = [codec.decode(raw[:-1]) for raw in table.strings(data)]
    texts = [text for text in texts if text.strip()]
    good = sum(1 for text in texts if looks_like_text(text) or (text.isupper() and looks_like_text(text.title())))
    return bool(texts) and good >= 0.5 * len(texts)


def find_tables(data: bytes, start: int = 0, end: Optional[int] = None, min_count: int = 3) -> List[Table]:
    """String tables inside program data (menus, executable): at least ``min_count`` strings."""
    end = len(data) if end is None else end
    found = []
    t = start + (start & 1)
    while t + 6 <= end:
        count = struct.unpack_from("<H", data, t)[0]
        if min_count <= count <= 2000:
            table = read_table(data, t, end, min_letters=6)
            if table is not None and _reads_as_text(data, table):
                table.region_end = table.used_end(data)
                found.append(table)
                t = table.region_end
                continue
        t += 2
    return found
