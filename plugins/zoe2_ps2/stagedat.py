"""STAGE.DAT of Zone of the Enders: The 2nd Runner: the stage index, its groups and the files inside them.

The file is read through a reader ``read(offset, count)`` (a disc file, see ``iso``). Layout (the format Konami used
for MGS2/MGS3 too; the key schedule follows Joy-Division/ArmsDepot ``dat-extract_enc.c``):

* word 0 is the build time and the seed of the header key; from byte 4 on, the header is XOR-coded word by word:
  version, block count, stage count, game id (0x0806), a hash, then one 20-byte entry per stage (16-byte name, first
  sector of the stage).
* a stage starts with its index: a word with the entry count, then 12-byte entries ``(ext, hash, offset)``. The index is
  coded with a key made from the hash of the stage name.
* the index lists groups. A group starts with an entry whose ``ext`` is a folder id (``0x7F00000x``) and whose offset is
  the size of its data when unpacked; the files follow as ``(ext hash of the extension, name hash, offset)`` and the
  group ends with ``ext == 0x7F000000``. A ``sound`` group (``0x7F000010``) and the delay-load groups are stored plain.
  Every other group is one zlib stream that is XOR-coded with a key taken from its own first word.
"""
from __future__ import annotations

import struct
import zlib
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

from core.i18n import tr

SECTOR = 0x800
MASK = 0xFFFFFFFF
KEY1 = 0x02E90EDD
KEY2 = 0x7A88FB59
KEY34 = 0xA78925D9
KEY6 = 0x00009385
KEY7 = 0x00000116
KEY8 = 0x00006576
GAME_ID = 0x0806
ZLIB_HEAD = bytes((0x78, 0x9C))         # the zlib header the game's streams start with
ZLIB_HEAD_LOW = 0x9C78
ZLIB_HEAD_SHIFT = 0x8F3                  # the coded first word holds (header - 0x8F3) in its low half
END_GROUP = 0x7F000000
PLAIN_GROUPS = (0x7F000010, 0x7F000005, 0x7F000004)
FOLDER_NAMES = {0x7F000010: "sound", 0x7F010000: "nocache", 0x7F000002: "cache", 0x7F000003: "resident",
                0x7F000004: "delayload", 0x7F000005: "delayload_w"}

Reader = Callable[[int, int], bytes]


class DatError(ValueError):
    """The file is not a STAGE.DAT this reader understands."""


def str_code32(text: str) -> int:
    """The name hash of ZONE OF THE ENDERS (``StrCode32``)."""
    value = 0
    for n, c in enumerate(text.encode("ascii")):
        value = (value + ((value << (c & 0x0F)) | (((value >> 3) + (c << (n & 0x0F)) + c) & MASK))) & MASK
    return value


def _xor_header(data: bytes, seed: int) -> bytes:
    """Decode (or encode: it is the same XOR) header words with the key stream of ``decryptHeader``."""
    out = bytearray(data)
    key = seed
    step = seed ^ 0xF0F0
    for i in range(0, len(out) - len(out) % 4, 4):
        word = struct.unpack_from("<I", out, i)[0] ^ key
        struct.pack_into("<I", out, i, word)
        key = (key * KEY1 + step) & MASK
    return bytes(out)


def _stream(data: bytes, key: int, step: int) -> bytes:
    out = bytearray(data)
    for i in range(0, len(out) - len(out) % 4, 4):
        struct.pack_into("<I", out, i, struct.unpack_from("<I", out, i)[0] ^ key)
        key = (key * KEY1 + step) & MASK
    return bytes(out)


def _stage_key(name: str, seed: int) -> Tuple[int, int]:
    h = str_code32(name)
    return ((h << 7) + seed + h + KEY34) & MASK, ((h << 7) + h + KEY2) & MASK


def code_stage_index(data: bytes, name: str, seed: int) -> bytes:
    key, step = _stage_key(name, seed)
    return _stream(data, key, step)


def _content_keys(key5: int) -> Tuple[int, int]:
    base = (key5 ^ KEY6) & MASK
    return (base | ((base ^ KEY8) << 16)) & MASK, (base * KEY7) & MASK


def decode_blob(blob: bytes) -> bytes:
    """The zlib stream of a coded group blob (padded to a whole word)."""
    key, step = _content_keys(struct.unpack_from("<I", blob, 0)[0] & 0xFFFF)
    out = bytearray(_stream(blob, key, step))
    low = (struct.unpack_from("<H", out, 0)[0] + ZLIB_HEAD_SHIFT) & 0xFFFF
    struct.pack_into("<H", out, 0, low)
    return bytes(out)


def encode_blob(stream: bytes, key5: int) -> bytes:
    """The coded blob of a zlib stream; the inverse of ``decode_blob`` (``key5``: any 16-bit number)."""
    if stream[:2] != b"\x78\x9c":
        raise DatError(tr("The group stream does not start with the zlib header the game expects."))
    padded = bytearray(stream + b"\0" * (-len(stream) % 4))
    struct.pack_into("<H", padded, 0, (ZLIB_HEAD_LOW - ZLIB_HEAD_SHIFT) & 0xFFFF)
    key, step = _content_keys(key5 & 0xFFFF)
    return _stream(bytes(padded), key, step)


class Entry(NamedTuple):
    ext: int
    hash: int
    offset: int


class Member(NamedTuple):
    ext: int            # hash of the extension, e.g. str_code32("tex")
    hash: int           # hash of the file name
    offset: int         # position in the unpacked group data
    size: int


class Group(NamedTuple):
    folder: int                   # 0x7F00000x
    index: int                    # position of the group's first entry in the stage index
    size: int                     # unpacked size
    plain: bool
    blob_offset: int              # position of the stored data from the start of the stage data
    stored: int                   # stored size in bytes (plain: the unpacked size)
    members: Tuple[Member, ...]


class Stage(NamedTuple):
    name: str
    sector: int                   # first sector of the stage in the file
    entries: Tuple[Entry, ...]    # the index, the terminating entry included
    data_at: int                  # byte position of the stage data in the file
    groups: Tuple[Group, ...]


class Toc(NamedTuple):
    seed: int
    version: int
    blocks: int
    game: int
    mark: int
    stages: Tuple[Tuple[str, int], ...]     # (name, first sector)


def read_toc(read: Reader) -> Toc:
    head = read(0, 16)
    if len(head) < 16:
        raise DatError(tr("The file is too short for a STAGE.DAT."))
    seed = struct.unpack_from("<I", head, 0)[0]
    version, blocks, count, game, mark = struct.unpack("<HHHHI", _xor_header(head[4:16], seed))
    if game != GAME_ID or not 0 < count < 4096:
        raise DatError(tr("This STAGE.DAT is not the one of Zone of the Enders: The 2nd Runner."))
    body = _xor_header(read(4, 12 + 20 * count), seed)[12:]
    stages = []
    for i in range(count):
        raw = body[20 * i:20 * i + 16]
        stages.append((raw.split(b"\0")[0].decode("ascii"), struct.unpack_from("<I", body, 20 * i + 16)[0]))
    return Toc(seed, version, blocks, game, mark, tuple(stages))


def read_stage_index(read: Reader, toc: Toc, name: str, sector: int) -> Tuple[Entry, ...]:
    first = code_stage_index(read(sector * SECTOR, 4), name, toc.seed)
    count = struct.unpack("<I", first)[0]
    if not 0 < count < 1 << 20:
        raise DatError(tr("The index of stage {0} is not readable.", name))
    raw = code_stage_index(read(sector * SECTOR, 4 + 12 * count), name, toc.seed)[4:]
    return tuple(Entry(*struct.unpack_from("<III", raw, 12 * i)) for i in range(count))


def parse_stage(read: Reader, toc: Toc, name: str, sector: int) -> Stage:
    entries = read_stage_index(read, toc, name, sector)
    index_bytes = 4 + 12 * len(entries)
    data_at = sector * SECTOR + (index_bytes + SECTOR - 1) // SECTOR * SECTOR
    groups: List[Group] = []
    i = 0
    cursor = 0               # stored groups follow each other, each starting on a sector
    while i < len(entries) and entries[i].ext and entries[i].offset:
        head = entries[i]
        start = i
        size = head.offset
        plain = head.ext in PLAIN_GROUPS
        i += 1
        if plain:
            blob_offset, stored = cursor, size
        else:
            blob_offset, stored = entries[i].offset, entries[i].ext & 0xFFFFFF
            if blob_offset != cursor:
                raise DatError(tr("Group {0} of stage {1} does not follow the group before it.", start, name))
            i += 1
        cursor += (stored + SECTOR - 1) // SECTOR * SECTOR
        members: List[Member] = []
        while i < len(entries) and entries[i].ext != END_GROUP:
            nxt = entries[i + 1].offset if i + 1 < len(entries) else size
            members.append(Member(entries[i].ext, entries[i].hash, entries[i].offset, nxt - entries[i].offset))
            i += 1
        i += 1                                   # the terminator
        groups.append(Group(head.ext, start, size, plain, blob_offset, stored, tuple(members)))
    return Stage(name, sector, entries, data_at, tuple(groups))


# ---- reading the data of a group ------------------------------------------------------------------------------------

def group_stream(read: Reader, stage: Stage, group: Group) -> bytes:
    """The zlib stream of a stored group (the coded blob decoded)."""
    return decode_blob(read(stage.data_at + group.blob_offset, (group.stored + 3) // 4 * 4))[:group.stored]


def group_data(read: Reader, stage: Stage, group: Group, upto: Optional[int] = None) -> bytes:
    """The unpacked data of a group; ``upto`` stops the inflate once that many bytes are out (the prefix is returned)."""
    if group.plain:
        return read(stage.data_at + group.blob_offset, group.size if upto is None else min(upto, group.size))
    stream = group_stream(read, stage, group)
    if upto is None:
        return zlib.decompress(stream)
    return zlib.decompressobj().decompress(stream, upto)


def member_bytes(read: Reader, stage: Stage, group: Group, member: Member) -> bytes:
    return group_data(read, stage, group, member.offset + member.size)[member.offset:member.offset + member.size]


# ---- writing a stage ------------------------------------------------------------------------------------------------

def _align(value: int, unit: int) -> int:
    return (value + unit - 1) // unit * unit


def join_members(parts: List[bytes]) -> Tuple[bytes, List[int]]:
    """The unpacked data of a group made of ``parts`` (each on a 16-byte boundary) and the offset of each part."""
    out = bytearray()
    offsets = []
    for part in parts:
        out += b"\0" * (_align(len(out), 16) - len(out))
        offsets.append(len(out))
        out += part
    out += b"\0" * (_align(len(out), 16) - len(out))
    return bytes(out), offsets


def split_members(data: bytes, group: Group) -> List[bytes]:
    return [data[m.offset:m.offset + m.size] for m in group.members]


def stage_bytes(read: Reader, toc: Toc, stage: Stage, changes: Dict[int, List[bytes]], level: int = 9) -> bytes:
    """The stage as stored on the disc, with the members of some groups replaced.

    ``changes`` maps a group's position in ``stage.groups`` to the new contents of all its members (in order). A group
    without a change is copied as it is, byte for byte; a changed group is packed again, and every offset after it in
    the index follows. The result is a whole number of sectors.
    """
    entries = [list(e) for e in stage.entries]
    spans: List[bytes] = []
    cursor = 0
    for position, group in enumerate(stage.groups):
        span = _align(group.stored if not group.plain else group.size, SECTOR)
        if position in changes and not group.plain:
            parts = changes[position]
            if len(parts) != len(group.members):
                raise DatError(tr("A changed group must keep its number of files."))
            data, offsets = join_members(parts)
            stream = ZLIB_HEAD + zlib.compress(data, level)[2:]       # the game's header; the level only tunes the packer
            key5 = struct.unpack_from("<I", read(stage.data_at + group.blob_offset, 4))[0] & 0xFFFF
            raw = encode_blob(stream, key5)
            entries[group.index][2] = len(data)
            entries[group.index + 1][0] = (entries[group.index + 1][0] & 0xFF000000) | len(stream)
            for entry, offset in zip(entries[group.index + 2:], offsets):
                entry[2] = offset
            entries[group.index + 2 + len(offsets)][2] = len(data)       # the terminator holds the unpacked size
            spans.append(raw + b"\x00" * (_align(len(raw), SECTOR) - len(raw)))
        else:
            spans.append(read(stage.data_at + group.blob_offset, span))     # as on the disc, padding included
        if not group.plain:
            entries[group.index + 1][2] = cursor
        cursor += len(spans[-1])
    index = struct.pack("<I", len(entries)) + b"".join(struct.pack("<III", *e) for e in entries)
    head = bytearray(read(stage.sector * SECTOR, stage.data_at - stage.sector * SECTOR))   # the index sector's padding
    head[:len(index)] = code_stage_index(index, stage.name, toc.seed)
    return bytes(head) + b"".join(spans)


def toc_with_sectors(read: Reader, toc: Toc, sectors: Dict[int, int]) -> bytes:
    """The coded bytes of the file from byte 4 to the end of the stage list, with the first sector of some stages
    (by position in ``toc.stages``) changed."""
    count = len(toc.stages)
    body = bytearray(_xor_header(read(4, 12 + 20 * count), toc.seed))
    for position, sector in sectors.items():
        struct.pack_into("<I", body, 12 + 20 * position + 16, sector)
    return _xor_header(bytes(body), toc.seed)
