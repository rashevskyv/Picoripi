"""A Lunar text file as Picoripi blocks, and the file again from edited blocks.

Two kinds of file: an event script (``LUNADATA/TEXTnnn.DAT``, one block: its messages and the two
answers of each yes/no choice, in file order) and the name and menu tables
(``LUNADATA/SYSTEM.DAT/00_0001.bin``, one block per table that is not empty). A text that comes back
unchanged keeps its original bytes, so an unedited file is rebuilt byte for byte.
"""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

from . import codec, script, strings

Blocks = List[List[str]]


def kind(data: bytes) -> str:
    """``names``, ``script``, or raises ValueError for any other file."""
    try:
        strings.slots(data)
        return "names"
    except ValueError:
        pass
    if script.parse(data):
        return "script"
    raise ValueError("no Lunar text in this file")


def _table_ids(data: bytes) -> List[int]:
    return [t for t, table in enumerate(strings.slots(data)) if table]


def read(data: bytes) -> Tuple[Blocks, Dict[str, str]]:
    """``(blocks, block names)`` of a file."""
    if kind(data) == "names":
        tables = strings.slots(data)
        blocks, names = [], {}
        for t in _table_ids(data):
            names[str(len(blocks))] = strings.NAMES[t]
            blocks.append([codec.decode(data, offset, data.index(b"\xff", offset) + 1) for _slot, offset in tables[t]])
        return blocks, names
    lines: List[str] = []
    for text in script.parse(data):
        for start, end in text.strings:
            lines.append(codec.decode_message(data, start, end) if text.kind == script.MESSAGE
                         else codec.decode(data, start, end))
    return [lines], {}


def write(source: bytes, blocks: Blocks, missing: Set[str]) -> bytes:
    """``source`` with the texts of ``blocks`` (the shape ``read`` returned). Characters the game cannot
    write become '?' and are added to ``missing``."""
    encoder = codec.Encoder()
    if kind(source) == "names":
        tables = strings.slots(source)
        new: Dict[Tuple[int, int], bytes] = {}
        for block, t in zip(blocks, _table_ids(source)):
            for text, (slot, offset) in zip(block, tables[t]):
                end = source.index(b"\xff", offset) + 1
                if text != codec.decode(source, offset, end):
                    new[(t, slot)] = encoder.string(text)
        missing |= encoder.missing
        return strings.rebuild(source, new)
    lines = blocks[0] if blocks else []
    replaced: Dict[int, bytes] = {}
    index = 0
    for text in script.parse(source):
        parts = []
        changed = False
        for start, end in text.strings:
            old = (codec.decode_message(source, start, end) if text.kind == script.MESSAGE
                   else codec.decode(source, start, end))
            new_text = lines[index] if index < len(lines) else old
            index += 1
            if new_text != old:
                changed = True
            parts.append((new_text, old, source[start:end]))
        if not changed:
            continue
        if text.kind == script.MESSAGE:
            new_text, _old, _raw = parts[0]
            body = encoder.message(new_text)
            head = source[text.start:text.start + 2]
        else:
            body = b"".join(encoder.string(t) if t != o else raw for t, o, raw in parts)
            head = source[text.start:text.start + 6]
        replaced[text.start] = head + script.pad(body, text.size, len(head), body[-1], codec.filler(body[-1]))
    missing |= encoder.missing
    return script.rebuild(source, replaced)
