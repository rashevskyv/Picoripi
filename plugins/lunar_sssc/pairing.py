"""Pair the messages of a Lunar SSS script in two languages (Remastered JP and EN) by their bytecode skeleton.

The Japanese and English ``TEXT*.DAT`` files run the same instructions in the same order. Only the text and
the length of the text differ. So the instruction opcodes, read from the labels in offset order, line up in
both files; a message in one file pairs with a message in the other when the two skeletons align on them.
Translation can add or remove a message: the alignment then leaves that message unpaired.
"""
from __future__ import annotations

import struct
from typing import List, Tuple

from plugins.lunar_sssc import script

Pairs = List[Tuple[int, int]]


def instructions(data: bytes) -> List[Tuple[int, int]]:
    """``(offset, opcode)`` of every instruction reached from a label, in offset order."""
    seen = {}
    visited = set()
    for start in sorted({value * 2 for value in script.labels(data) if value}):
        o = start
        while o < len(data) and o not in visited:
            visited.add(o)
            op = struct.unpack_from("<H", data, o)[0]
            if op >= 97:
                break
            seen[o] = op
            if op in script.END_OPS:
                break
            o += script.length(data, o)
    return sorted(seen.items())


def align(a: List[int], b: List[int]) -> Pairs:
    """The longest common subsequence of two opcode lists, as index pairs ``(i, j)``."""
    n, m = len(a), len(b)
    best = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            best[i][j] = max(best[i + 1][j], best[i][j + 1], best[i + 1][j + 1] + (a[i] == b[j]))
    pairs: Pairs = []
    i = j = 0
    while i < n and j < m:
        if a[i] == b[j] and best[i][j] == best[i + 1][j + 1] + 1:
            pairs.append((i, j))
            i += 1
            j += 1
        elif best[i][j] == best[i + 1][j] and (best[i][j] != best[i][j + 1] or a[i] == script.MESSAGE):
            i += 1  # on a tie, a message is left unpaired before an instruction is skipped, not the reverse
        else:
            j += 1
    return pairs


def pair_messages(en: bytes, jp: bytes) -> Tuple[Pairs, List[int], List[int]]:
    """Message pairs ``(en_index, jp_index)`` in file order, then the unpaired message indices of each file.

    An index counts the messages of its own file (``script.parse`` order), not instructions.
    """
    ea = instructions(en)
    jb = instructions(jp)
    en_index = {off: k for k, (off, op) in enumerate(e for e in ea if e[1] == script.MESSAGE)}
    jp_index = {off: k for k, (off, op) in enumerate(e for e in jb if e[1] == script.MESSAGE)}
    pairs = []
    for i, j in align([op for _, op in ea], [op for _, op in jb]):
        if ea[i][1] == script.MESSAGE:
            pairs.append((en_index[ea[i][0]], jp_index[jb[j][0]]))
    paired_en = {p[0] for p in pairs}
    paired_jp = {p[1] for p in pairs}
    return (
        pairs,
        [k for k in range(len(en_index)) if k not in paired_en],
        [k for k in range(len(jp_index)) if k not in paired_jp],
    )
