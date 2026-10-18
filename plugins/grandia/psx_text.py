"""Grandia (PlayStation) text as editor blocks, with a bounded writer.

Two text forms on the disc (English release SCUS-94457 / SCUS-94465):

* Battle strings in ``BATLE/B*.BBG`` and the window table ``FIELD/WINDT.BIN``: a chain of records, each NUL-terminated
  and followed by 0x03. ``battle_records`` finds every chain of at least ``MIN_CHAIN`` records.
* Field dialogue in ``FIELD/*.MDP``: printable ASCII runs between control bytes. A file is dialogue when it holds the
  speaker sequence ``0F 03 0A 0C 00`` at least twice (186 field scripts on disc 1, none elsewhere).

Each dialogue block is a run plus the bytes after it (up to TAIL_MAX bytes, the next run, or the next speaker
sequence). In the editor text a control byte is a tag ``<XX>`` (two hex digits); a printable byte is itself, and
``<`` is written ``<3C>``. The aliases in config.json (``default_tag_mappings``) name the common tags.

Writing is bounded: a block's new text must encode to at most its original byte count. A shorter text is padded with
spaces to the original length; a longer one is refused and the original bytes stay. Rendering and parsing are exact
inverses, so an unchanged block writes back byte-exact. Growing a block needs the script stream's references, which
are not decoded yet. Text must be printable ASCII plus tags; other characters are refused.

Script structure of a field script (measured on the owner's disc 1; "not decoded" marks what is still open):

* Directory (measured): 8-byte entries from offset 0. Each offset word has a flag in its top byte; 0xFFFFFFFF is an
  empty entry. Entry 0x60 is the dialogue section (flag 0): all speaker sequences of all 186 dialogue scripts lie in
  it, and the last one is at least 73 bytes before its end. ``script_section`` returns that entry.
* Messages (observed, not decoded): a run of text sits between control bytes. ``0E 00`` closes a message and is
  followed by one byte, ``09``, and a 0F-led sequence (speaker or face). ``01`` is a line break and ``02`` ends a box
  in the tag names of config.json; the names are guesses. The opcode table and the reader are not decoded.
* Absolute words (measured): the section holds 6-byte records of a 16-bit value and a 32-bit RAM address (0x80xxxxxx,
  for example 0x801A7000 many times). Their targets are not resolved. Growth must resolve them.
* Relative jumps (measured): no 16-bit relative jump in the section points at a command boundary (13 hits; a shuffled
  byte order gives 13 too), so no relative-jump pattern shows up at this test.
* RAM (measured): the save state holds the whole script file as one byte-for-byte copy (432 KB, no mismatched block).
  The game reads its text from that copy, so a same-length edit in RAM shows on screen.
"""
from __future__ import annotations

import re
import struct
from typing import List, Optional, Sequence, Tuple

MIN_CHAIN = 12           # records in a battle string chain (a real table has 30 or more)
MAX_RECORD = 80          # longest battle string record in bytes
MIN_RUN = 4              # shortest dialogue run in bytes
TAIL_MAX = 24            # most bytes after a run that belong to its block
SPEAKER = b"\x0f\x03\x0a\x0c\x00"
MIN_SPEAKERS = 2         # speaker sequences that mark a dialogue file
_RUN = re.compile(rb"[\x20-\x7e]{%d,}" % MIN_RUN)
_TAG = re.compile(r"<([0-9A-F]{2})>")


def render(block: bytes) -> str:
    """The editor text of a block: printable bytes as themselves, '<' as <3C>, other bytes as <XX>."""
    out = []
    for byte in block:
        if byte == 0x3C or not 0x20 <= byte <= 0x7E:
            out.append(f"<{byte:02X}>")
        else:
            out.append(chr(byte))
    return "".join(out)


def parse(text: str) -> Optional[bytes]:
    """The bytes of an editor text (inverse of render), or None when it holds a character that is not allowed."""
    out = bytearray()
    at = 0
    for match in _TAG.finditer(text):
        for ch in text[at:match.start()]:
            if not 0x20 <= ord(ch) <= 0x7E or ch == "<":
                return None
            out.append(ord(ch))
        out.append(int(match.group(1), 16))
        at = match.end()
    for ch in text[at:]:
        if not 0x20 <= ord(ch) <= 0x7E or ch == "<":
            return None
        out.append(ord(ch))
    return bytes(out)


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


def dialogue_blocks(data: bytes) -> List[Tuple[int, bytes]]:
    """(offset, block bytes) of every dialogue block: a run and the bytes after it, bounded as described above."""
    runs = dialogue_runs(data)
    out: List[Tuple[int, bytes]] = []
    for index, (offset, text) in enumerate(runs):
        end_run = offset + len(text)
        limit = min(runs[index + 1][0] if index + 1 < len(runs) else len(data), end_run + TAIL_MAX)
        speaker = data.find(SPEAKER, end_run, limit)
        if speaker >= 0:
            limit = speaker
        out.append((offset, data[offset:limit]))
    return out


def is_dialogue(data: bytes) -> bool:
    return data.count(SPEAKER) >= MIN_SPEAKERS


DIRECTORY_END = 0x200    # the entry table of a field script ends before this offset
EMPTY_ENTRY = 0xFFFFFFFF


def script_section(data: bytes) -> Optional[Tuple[int, int]]:
    """(offset, size) of the directory entry that holds the most speaker sequences, or None without speakers.

    The table holds 8-byte entries: an offset word (its top byte is a flag, not an address) and a size. An entry of
    0xFFFFFFFF words is empty. On disc 1 the entry at 0x60 holds every speaker sequence of all 186 dialogue scripts.
    """
    speakers = [m.start() for m in re.finditer(re.escape(SPEAKER), data)]
    best: Optional[Tuple[int, int]] = None
    best_count = 0
    for at in range(0, min(DIRECTORY_END, len(data) - 7), 8):
        off_word, size = struct.unpack_from("<II", data, at)
        if off_word == EMPTY_ENTRY and size == EMPTY_ENTRY:
            continue
        offset = off_word & 0xFFFFFF
        end = offset + size
        if end > len(data):
            continue
        count = sum(1 for pos in speakers if offset <= pos < end)
        if count > best_count:
            best, best_count = (offset, size), count
    return best


def is_ps1_text(data: bytes) -> bool:
    return len(battle_records(data)) >= MIN_CHAIN or is_dialogue(data)


def entries(data: bytes) -> Tuple[str, List[Tuple[int, bytes]]]:
    """(kind, [(offset, original block bytes)]) of the editable blocks: 'battle', 'dialogue' or '' for no text."""
    records = battle_records(data)
    if records:
        return "battle", [(off, text) for off, text in records]
    if is_dialogue(data):
        return "dialogue", dialogue_blocks(data)
    return "", []


def blocks(data: bytes) -> Tuple[List[str], dict]:
    """Editor texts (control bytes as tags) and one name per text, in file order."""
    kind, found = entries(data)
    names = {str(i): f"{kind} {off:#x}" for i, (off, _) in enumerate(found)}
    return [render(block) for _, block in found], names


def write(data: bytes, texts: Sequence[str]) -> Tuple[bytes, List[int]]:
    """The file with the new texts, bounded to each block's byte count.

    Returns (new bytes, refused block indices). A refused block keeps its original bytes, and so does a block with no
    entry in ``texts``. An unchanged text writes the original bytes exactly.
    """
    _kind, found = entries(data)
    out = bytearray(data)
    refused: List[int] = []
    for index in reversed(range(len(found))):
        if index >= len(texts):
            continue
        offset, original = found[index]
        new = parse(texts[index])
        if new is None or len(new) > len(original):
            refused.append(index)
            continue
        if new == original:
            continue
        out[offset:offset + len(original)] = new + b" " * (len(original) - len(new))
    return bytes(out), sorted(refused)


def budget(data: bytes) -> dict:
    """Measured byte budget of one script: how many editable blocks it has, and the bytes a translation may use.

    ``bytes`` is the sum of the block sizes, ``largest`` the biggest single block. A translated block must fit its
    own size, so these are the limits the bounded writer enforces.
    """
    _kind, found = entries(data)
    sizes = [len(block) for _, block in found]
    return {"blocks": len(sizes), "bytes": sum(sizes), "largest": max(sizes) if sizes else 0}
