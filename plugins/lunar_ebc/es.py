"""Lunar 2 script blocks ("ES"): the messages a script shows, and the block again with new messages.

Header (u32s): ``"ES" 00 01``, block size, code size, code offset, 0, text offset, text size, text
offset. The code is 4-byte instructions, the opcode in the top byte (the interpreter's table is at
SLUS_010.71 0x80081FD0); jumps and calls are relative to the code, and only opcode 0x1D ("show
message") names a message, by its offset in the text. The text is a run of messages, each a u16 byte
length (itself included) and its units. A rebuild lays the messages out again and points every 0x1D at
the new place; whatever follows the block in the file is the caller's to move.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, List, Tuple

MAGIC = b"ES\x00\x01"
SHOW = 0x1D


class ScriptError(ValueError):
    """Not a script block, or one whose messages do not tile its text."""


@dataclass
class Block:
    start: int                  # of the block in the file
    size: int
    code: Tuple[int, int]       # (offset, size) in the block
    text: Tuple[int, int]
    messages: List[Tuple[int, int]]   # (offset in the text, length)


def parse(data: bytes, start: int = 0) -> Block:
    if data[start:start + 4] != MAGIC:
        raise ScriptError("no script block here")
    size, code_size, code_off, _zero, _text2, text_size, text_off = struct.unpack_from("<7I", data, start + 4)
    if not (code_off + code_size <= text_off and text_off + text_size <= size <= len(data) - start):
        raise ScriptError("script block header out of range")
    messages = []
    pos = 0
    while pos < text_size:
        length = struct.unpack_from("<H", data, start + text_off + pos)[0]
        if length < 2 or length % 2 or pos + length > text_size:
            raise ScriptError(f"message at 0x{pos:X} has a bad length")
        messages.append((pos, length))
        pos += length
    return Block(start, size, (code_off, code_size), (text_off, text_size), messages)


def shows(data: bytes, block: Block) -> List[int]:
    """Offsets (in the file) of the code words that show a message."""
    code_off, code_size = block.code
    base = block.start + code_off
    return [base + i for i in range(0, code_size, 4) if data[base + i + 3] == SHOW]


def rebuild(data: bytes, block: Block, new: Dict[int, bytes]) -> bytes:
    """The block (only the block) with the messages ``{index: new bytes with their length}`` replaced."""
    text_off, text_size = block.text
    base = block.start + text_off
    out_text = bytearray()
    moved: Dict[int, int] = {}
    for index, (offset, length) in enumerate(block.messages):
        moved[offset] = len(out_text)
        body = new.get(index, data[base + offset:base + offset + length])
        if len(body) % 2 or struct.unpack_from("<H", body, 0)[0] != len(body):
            raise ScriptError(f"message {index}: length word does not match")
        out_text += body
    moved[text_size] = len(out_text)
    head = bytearray(data[block.start:block.start + text_off])
    for at in shows(data, block):
        word = struct.unpack_from("<I", data, at)[0]
        target = word & 0xFFFFFF
        if target not in moved:
            raise ScriptError(f"0x1D at 0x{at:X} points inside a message")
        struct.pack_into("<I", head, at - block.start, SHOW << 24 | moved[target])
    size = (text_off + len(out_text) + 3) & ~3
    struct.pack_into("<I", head, 4, size)
    struct.pack_into("<I", head, 0x18, len(out_text))
    body = bytes(head) + bytes(out_text)
    old_tail = data[block.start + text_off + text_size:block.start + block.size]
    pad = old_tail if size - len(body) == len(old_tail) else bytes(size - len(body))
    return body + pad
