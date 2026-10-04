"""Skyward Sword message flows (MSBF, "MsgFlwBn", big endian): which conversation shows which message.

``FLW3`` holds 16-byte nodes and a table of branch targets; ``FEN1`` names the entry nodes (``105_01``: the
flow an NPC or event starts). Node layout (offsets in the node): type u8 at 0 (1 message, 2 branch,
3 event, 4 entry), next u16 at 8; a message node has the message index of the same-named MSBT at 12, a
branch node its target count at 12 and its first slot in the branch table at 14.
"""
from __future__ import annotations

import struct
from typing import Dict, List

from plugins.common.msbp import _labels, _sections

MAGIC = b"MsgFlwBn"
_NONE = 0xFFFF


def conversations(raw: bytes) -> Dict[int, str]:
    """``{message index: entry label}``: the first entry (in label order) whose flow reaches the message."""
    raw = bytes(raw)
    if raw[:8] != MAGIC:
        raise ValueError("Not an MSBF file")
    e = "<" if raw[8:10] == b"\xff\xfe" else ">"
    sections = _sections(raw, e)
    flw = sections.get(b"FLW3", b"")
    if len(flw) < 16:
        return {}
    count, branch_count = struct.unpack_from(e + "HH", flw, 0)
    nodes = [flw[16 + i * 16:32 + i * 16] for i in range(count)]
    branches = struct.unpack_from(f"{e}{branch_count}H", flw, 16 + count * 16)
    result: Dict[int, str] = {}
    for node, label in sorted(_labels(sections.get(b"FEN1", b""), e).items(), key=lambda item: item[1]):
        stack: List[int] = [node]
        seen = set()
        while stack:
            index = stack.pop()
            if index == _NONE or index in seen or index >= count:
                continue
            seen.add(index)
            data = nodes[index]
            kind, following = data[0], struct.unpack_from(e + "H", data, 8)[0]
            if kind == 1:
                result.setdefault(struct.unpack_from(e + "H", data, 12)[0], label)
            if kind == 2:
                targets, first = struct.unpack_from(e + "HH", data, 12)
                stack.extend(branches[first:first + targets])
            else:
                stack.append(following)
    return result
