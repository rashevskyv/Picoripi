"""Fragile Dreams message blocks (``.msg`` files of the workspace's source folder).

A ``.msg`` file is one or more blocks, each on 0x20 bytes; bytes after the last block are kept. A block (big
endian): a language tag (``USA `` -- the English the game shows --, ``GBR ``, ``JPN ``...), u32 size (header,
table and strings, without the padding), u32 version, u32 message count, then per message u32 id and u32
offset of its text counted from that table entry; the texts follow the table, NUL-terminated and padded to 4
bytes, in table order. The padding after a block is old memory of the tool that wrote it: an unchanged block
keeps its bytes, a changed one is written again with zero padding.

Texts are single bytes. The game's English is cp1252; the plugin reads and writes cp1251, so Ukrainian
letters get the codes of the font cells 0xC0-0xFF (and 0xA5, 0xAA, 0xAF, 0xB2-0xB4, 0xBA, 0xBF) -- the
punctuation the English uses (0x85, 0x92-0x94, 0x97, 0x99, 0xA9, 0xB0) is the same in both; only é shows as й.
``<...>`` are control codes (``<w>`` wait for a button, ``<v1>`` voice, ``<p>`` new page, ``<c#404040ff>``
colour...) and ``[Value]``-style words are filled in by the game; both stay as they are.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

TAGS = (b"JPN ", b"USA ", b"GBR ", b"FRA ", b"ITA ", b"DEU ", b"ESP ")
ENCODING = "cp1251"
TAG_RE = re.compile(r"<[^<>\n]{1,24}>|\[[A-Za-z][A-Za-z0-9 ]{0,15}\]")


class FormatError(ValueError):
    pass


@dataclass
class Block:
    tag: bytes
    version: int
    ids: List[int]
    texts: List[bytes]
    raw: bytes                     # the block as stored, padding included


@dataclass
class MsgFile:
    blocks: List[Block] = field(default_factory=list)
    tail: bytes = b""


def _align(n: int, to: int) -> int:
    return (n + to - 1) // to * to


def is_block(raw: bytes, at: int = 0) -> bool:
    if raw[at:at + 4] not in TAGS or len(raw) < at + 16:
        return False
    size, _version, count = struct.unpack_from(">III", raw, at + 4)
    return 16 + 8 * count <= size <= len(raw) - at


def is_msg(raw: bytes) -> bool:
    return is_block(bytes(raw))


def parse(raw: bytes) -> MsgFile:
    raw = bytes(raw)
    if not is_block(raw):
        raise FormatError("Not a Fragile Dreams message file")
    out, at = MsgFile(), 0
    while at < len(raw) and is_block(raw, at):
        size, version, count = struct.unpack_from(">III", raw, at + 4)
        ids, texts = [], []
        for i in range(count):
            ident, offset = struct.unpack_from(">II", raw, at + 16 + 8 * i)
            start = at + 16 + 8 * i + offset
            end = raw.find(b"\0", start, at + size)
            if not at + 16 + 8 * count <= start <= at + size or end < 0:
                raise FormatError(f"Message {i} of the block at {at:#x} lies outside it")
            ids.append(ident)
            texts.append(raw[start:end])
        stored = min(_align(size, 0x20), len(raw) - at)
        out.blocks.append(Block(raw[at:at + 4], version, ids, texts, raw[at:at + stored]))
        at += stored
    out.tail = raw[at:]
    return out


def build_block(block: Block, texts: List[bytes]) -> bytes:
    """The block with ``texts``; the same texts give its stored bytes back."""
    if texts == block.texts:
        return block.raw
    count = len(block.ids)
    head = bytearray(block.tag + struct.pack(">III", 0, block.version, count) + bytes(8 * count))
    body = bytearray()
    for i, (ident, text) in enumerate(zip(block.ids, texts)):
        if b"\0" in text:
            raise FormatError("A message cannot hold a NUL byte")
        entry = 16 + 8 * i
        struct.pack_into(">II", head, entry, ident, len(head) + len(body) - entry)
        body += text + bytes(_align(len(text) + 1, 4) - len(text))
    struct.pack_into(">I", head, 4, len(head) + len(body))
    out = bytes(head + body)
    return out + bytes(-len(out) % 0x20)


def build(msg: MsgFile, new_texts: Dict[int, List[bytes]]) -> bytes:
    """``msg`` with the texts of blocks ``{block index: texts}``."""
    return b"".join(build_block(b, new_texts.get(i, b.texts)) for i, b in enumerate(msg.blocks)) + msg.tail


# -- main.dol ------------------------------------------------------------------------------------
# The executable holds its own blocks: the Wii system and save messages (shown before the game's files are
# read: the save check at start), the copyright line and the disc errors. The game shows the USA ones in English.
DOL_TAG = b"USA "


def is_dol(raw: bytes) -> bool:
    return bytes(raw[:4]) == b"\x00\x00\x01\x00" and len(raw) > 0x100 and not is_block(bytes(raw))


def dol_blocks(raw: bytes) -> List[tuple]:
    """``[(offset, room, Block)]`` of the English blocks of main.dol; ``room`` is what a rebuilt block may take
    (its size, up to the next 0x20 when only zeros follow)."""
    raw = bytes(raw)
    out, at = [], raw.find(DOL_TAG)
    while at >= 0:
        if at % 0x20 == 0 and is_block(raw, at):
            size = struct.unpack_from(">I", raw, at + 4)[0]
            end = _align(size, 0x20)
            room = end if not any(raw[at + size:at + end]) else size
            out.append((at, room, parse(raw[at:at + size]).blocks[0]))
        at = raw.find(DOL_TAG, at + 4)
    return out


def build_dol(raw: bytes, new_texts: Dict[int, List[bytes]]) -> bytes:
    """main.dol with the texts of its English blocks ``{block index: texts}`` written in place."""
    out = bytearray(raw)
    for index, (at, room, block) in enumerate(dol_blocks(raw)):
        if index not in new_texts or new_texts[index] == block.texts:
            continue
        blob = build_block(block, new_texts[index])
        size = struct.unpack_from(">I", blob, 4)[0]
        blob = blob[:size]
        if size > room:
            raise FormatError(f"main.dol block {index + 1}: the texts take {size} bytes, the game has room for {room}")
        out[at:at + room] = blob + bytes(room - size)
    return bytes(out)


def to_editor(text: bytes) -> str:
    return text.decode(ENCODING, "replace")


def from_editor(text: str, missing: Optional[Set[str]] = None) -> bytes:
    out = bytearray()
    for char in text:                      # a few item texts break lines with CR LF: kept as they are
        try:
            out += char.encode(ENCODING)
        except UnicodeEncodeError:
            if missing is not None:
                missing.add(char)
            out += b"?"
    return bytes(out)
