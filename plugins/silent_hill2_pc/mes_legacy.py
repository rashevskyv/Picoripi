"""Message rows saved with the first reading of the SH2 message table (before mes.py read it from word 1).

That reading took the count word as the first offset. So each row was the message one entry earlier: row 0 held the
last offset word (2 bytes), and the last row held two messages. The bytes of the files never changed.
migrate_rows() maps old rows to the messages of the current reading by their bytes and returns one note per change.
"""
import struct
from typing import Callable, List, Tuple

from plugins.silent_hill2_pc import mes

APOSTROPHE = 0x07


def legacy_split(data: bytes) -> List[bytes]:
    """The old reading: entry k of the table (words 0..count-1) is the start of old row k."""
    count = struct.unpack_from("<H", data, 0)[0]
    if count == 0 and len(data) == 2:
        return []
    starts = [struct.unpack_from("<H", data, 2 * i)[0] * 2 for i in range(count)]
    ends = starts[1:] + [len(data)]
    return [data[s:e] for s, e in zip(starts, ends)]


def legacy_decode(raw: bytes) -> str:
    """The old source codec: printable ASCII as itself, 0x00 a space, 0x07 an apostrophe, the rest tags."""
    out = []
    for b in raw:
        if b == 0x00:
            out.append(" ")
        elif b == APOSTROPHE:
            out.append("'")
        elif 0x21 <= b <= 0x7E and b not in (0x27, 0x7B, 0x7D):
            out.append(chr(b))
        else:
            out.append("{%02X}" % b)
    return "".join(out)


def _legacy_plain(text: str) -> bytes:
    out = bytearray()
    for ch in text:
        if ch == " ":
            out.append(0x00)
        elif ch == "'":
            out.append(APOSTROPHE)
        elif 0x21 <= ord(ch) <= 0x7E:
            out.append(ord(ch))
        else:
            raise ValueError(f"character {ch!r} is not in the old source text")
    return bytes(out)


def legacy_encode(text: str) -> bytes:
    """Inverse of legacy_decode."""
    out = bytearray()
    pos = 0
    for m in mes.TAG_RE.finditer(text):
        out += _legacy_plain(text[pos:m.start()])
        out.append(int(m.group(1), 16))
        pos = m.end()
    out += _legacy_plain(text[pos:])
    return bytes(out)


def migrate_rows(old_rows: List[str], encode: Callable[[str], bytes]) -> Tuple[List[bytes], List[str]]:
    """Old row texts of one file -> the messages of the current reading, and one note per change.

    ``encode`` turns a row back into its bytes with the codec the row was saved with (legacy_encode for the source,
    mes.encode_uk for a translation). Row 0 (the last offset word) is dropped. The last row holds two messages: it is
    cut where the dropped word says the last message starts.
    """
    rows = [encode(text) for text in old_rows]
    if not rows:
        return [], []
    if len(rows) == 1:
        return [rows[0][2:]], ["one row: its first two bytes are the offset word, the rest is the message"]
    if len(rows[0]) != 2:
        raise ValueError("old row 0 is not one offset word")
    last_offset = struct.unpack("<H", rows[0])[0]
    count = len(rows)
    messages = list(rows[1:count - 1])
    last = rows[count - 1]
    row_start = 2 * count + sum(len(r) for r in rows[:count - 1])
    cut = last_offset * 2 - row_start
    if not 0 <= cut <= len(last):
        raise ValueError("the last row does not hold the two messages the offset word names")
    messages += [last[:cut], last[cut:]]
    notes = [f"row 0 (offset word {last_offset}) dropped",
             f"last row cut at byte {cut} into two messages"]
    return messages, notes
