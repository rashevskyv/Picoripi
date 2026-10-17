"""Grandia (PlayStation) text as editor blocks, with a bounded writer.

Two text forms on the disc (English release SCUS-94457 / SCUS-94465):

* Battle strings in ``BATLE/B*.BBG``: a chain of records, each NUL-terminated and followed by 0x03. ``battle_records``
  finds every chain of at least ``MIN_CHAIN`` records and returns each record's offset and text.
* Field dialogue in ``FIELD/*.MDP``: printable ASCII runs between control bytes. A file is dialogue when it holds the
  speaker sequence ``0F 03 0A 0C 00`` at least twice (186 field scripts on disc 1, none elsewhere). The control bytes
  stay in the file; each run is one block. The speaker sequence is followed by the speaker ID byte.

Writing is bounded: a block's new text must fit its original byte count. A shorter text is padded with spaces to the
original length; a longer text is refused and the original bytes stay. Every other byte of the file is copied as it is,
so an unchanged file is byte-exact. Growing a block needs the script stream's references, which are not decoded yet.
Text must be Latin-1 (the game font has no Cyrillic); other text is refused.
"""
from __future__ import annotations

import re
from typing import List, Sequence, Tuple

MIN_CHAIN = 12           # records in a battle string chain (a real table has 30 or more)
MAX_RECORD = 80          # longest battle string record in bytes
MIN_RUN = 4              # shortest dialogue run in bytes
SPEAKER = b"\x0f\x03\x0a\x0c\x00"
MIN_SPEAKERS = 2         # speaker sequences that mark a dialogue file
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


def is_dialogue(data: bytes) -> bool:
    return data.count(SPEAKER) >= MIN_SPEAKERS


def is_ps1_text(data: bytes) -> bool:
    return len(battle_records(data)) >= MIN_CHAIN or is_dialogue(data)


def entries(data: bytes) -> Tuple[str, List[Tuple[int, bytes]]]:
    """(kind, [(offset, original bytes)]) of the editable blocks: 'battle', 'dialogue' or '' for no text."""
    records = battle_records(data)
    if records:
        return "battle", records
    if is_dialogue(data):
        return "dialogue", dialogue_runs(data)
    return "", []


def blocks(data: bytes) -> Tuple[List[str], dict]:
    """Editor texts and one name per text, in file order."""
    kind, found = entries(data)
    names = {str(i): f"{kind} {off:#x}" for i, (off, _) in enumerate(found)}
    return [text.decode("latin-1") for _, text in found], names


def write(data: bytes, texts: Sequence[str]) -> Tuple[bytes, List[int]]:
    """The file with the new texts, bounded to each block's byte count.

    Returns (new bytes, refused block indices). A refused block keeps its original bytes. A block with no entry in
    ``texts`` keeps its original bytes. An unchanged text writes the original bytes exactly.
    """
    _kind, found = entries(data)
    out = bytearray(data)
    refused: List[int] = []
    for index in reversed(range(len(found))):
        if index >= len(texts):
            continue
        offset, original = found[index]
        new = texts[index].encode("latin-1", errors="strict") if _latin1(texts[index]) else None
        if new is None or len(new) > len(original):
            refused.append(index)
            continue
        if new == original:
            continue
        out[offset:offset + len(original)] = new + b" " * (len(original) - len(new))
    return bytes(out), sorted(refused)


def _latin1(text: str) -> bool:
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        return False
    return True
