"""Grandia (PlayStation) text as editor blocks, read side only.

Two text forms on the disc, both found in the English release (SCUS-94457 / SCUS-94465):

* Battle strings in ``BATLE/B*.BBG``: a chain of records, each NUL-terminated and followed by 0x03. ``battle_records``
  finds the longest such chain (its length is the record count) and returns each record's offset and text.
* Field dialogue in ``FIELD/*.MDP``: printable ASCII runs between control bytes. The control bytes stay in the file;
  ``dialogue_runs`` returns each run. Whether a run can grow is not known yet (the script stream is not decoded).

``blocks(data)`` returns the texts and one name per text, in file order, for the editor. ``is_ps1_text`` is the signal
the plugin uses: a battle chain of at least ``MIN_CHAIN`` records. A Dreamcast message archive never has one.
Writing is not implemented: the plugin keeps the source file unchanged.
"""
from __future__ import annotations

import re
from typing import List, Tuple

MIN_CHAIN = 12           # records in a battle string chain (a real table has 30 or more)
MAX_RECORD = 80          # longest battle string record in bytes
MIN_RUN = 4              # shortest dialogue run in bytes
_RUN = re.compile(rb"[\x20-\x7e]{%d,}" % MIN_RUN)


def battle_records(data: bytes) -> List[Tuple[int, bytes]]:
    """(offset, text) of every record of every chain of at least MIN_CHAIN records, in file order.

    A chain is records that follow each other with exactly one 0x00 and one 0x03 between them. A record holds no
    control byte (below 0x20), so junk bytes end a chain.
    """
    out: List[Tuple[int, bytes]] = []
    chain: List[Tuple[int, bytes]] = []
    at = 0
    while True:
        end = data.find(b"\x00\x03", at)
        if end < 0:
            break
        start = _record_start(data, end)
        text = data[start:end]
        ok = 0 < len(text) <= MAX_RECORD and min(text) >= 0x20
        continues = bool(chain) and start == chain[-1][0] + len(chain[-1][1]) + 2
        if ok and (continues or not chain):
            chain.append((start, text))
        else:
            if len(chain) >= MIN_CHAIN:
                out.extend(chain)
            chain = [(start, text)] if ok else []
        at = end + 2
    if len(chain) >= MIN_CHAIN:
        out.extend(chain)
    return out


def _record_start(data: bytes, end: int) -> int:
    """The start of the record that ends at ``end`` (after the previous 0x00 or 0x03 byte)."""
    at = end
    while at > 0 and data[at - 1] not in (0x00, 0x03):
        at -= 1
    return at


def dialogue_runs(data: bytes) -> List[Tuple[int, bytes]]:
    """(offset, text) of every printable ASCII run of at least MIN_RUN bytes."""
    return [(m.start(), m.group(0)) for m in _RUN.finditer(data)]


def is_ps1_text(data: bytes) -> bool:
    return len(battle_records(data)) >= MIN_CHAIN


def blocks(data: bytes) -> Tuple[List[str], dict]:
    """Editor blocks of a PS1 text file: the battle records if the file has a chain, else the dialogue runs."""
    records = battle_records(data)
    if records:
        names = {f"{i:03d}": f"battle {off:#x}" for i, (off, _) in enumerate(records)}
        return [text.decode("latin-1") for _, text in records], names
    runs = dialogue_runs(data)
    names = {f"{i:03d}": f"run {off:#x}" for i, (off, _) in enumerate(runs)}
    return [text.decode("latin-1") for _, text in runs], names
