"""Silent Hill 2 (PC, Enhanced Edition data, also the Switch homebrew data) message files: data\\etc\\message\\*.mes.

Layout, as the game and the packer's sh2mes.py read it: a u16 count, then count u16 offsets (in 16-bit words from the
file start). Message k runs from its offset to the next offset; the last one runs to the end of the file. Message 0
starts right after the table. Each message is one row. A message usually starts with a header ``00 80 XX`` and ends
with ``0e ff ff 00 90`` (or the next header).

Charset (the PC font: codes below 0xE0 are Windows-1252 characters minus 0x20, sh2conv/ui.py): byte b shows the
character b + 0x20. So 0x00 is a space and 0x07 an apostrophe (DON'T). Bytes 0xE0 and up, the two bytes that would
read as a brace (0x5B, 0x5D) and the bytes Windows-1252 leaves undefined are opaque tags ``{XX}``, kept as they are.
``encode(decode(m)) == m`` for every message of every file. The table is rebuilt on save, so a changed message may
take more bytes (the file is a standalone file on the PC).

Before this layout, the table was read from word 0 (one entry too early). Projects saved with that reading are
migrated with silent_hill2_pc/mes_legacy.py.
"""
from __future__ import annotations

import re
import struct
from typing import List, Optional

TAG_RE = re.compile(r"\{([0-9A-Fa-f]{2})\}")


def table_starts(data: bytes) -> List[int]:
    """Byte offset of every message. Message 0 follows the table: the offsets are the words 1..count."""
    if len(data) < 2:
        raise ValueError("not a message file: too short")
    count = struct.unpack_from("<H", data, 0)[0]
    if count == 0 and len(data) == 2:       # an empty message file (stage_apart_boss_*: just 00 00)
        return []
    if count == 0 or 2 + 2 * count > len(data):
        raise ValueError("not a message file: empty table")
    starts = [struct.unpack_from("<H", data, 2 + 2 * i)[0] * 2 for i in range(count)]
    if starts[0] != 2 + 2 * count or any(starts[i] > starts[i + 1] for i in range(count - 1)) or starts[-1] >= len(data):
        raise ValueError("not a message file: table does not fit")
    return starts


def split(data: bytes) -> List[bytes]:
    starts = table_starts(data)
    if not starts:
        return []
    ends = starts[1:] + [len(data)]
    return [data[s:e] for s, e in zip(starts, ends)]


def _shown_char(b: int) -> Optional[str]:
    """The character byte b shows in the PC font, None for a tag."""
    if b >= 0xE0 or b in (0x5B, 0x5D):         # 0x5B and 0x5D would read as a brace
        return None
    try:
        return bytes([b + 0x20]).decode("cp1252")
    except UnicodeDecodeError:
        return None


_SHOWN = {b: ch for b in range(0xE0) for ch in [_shown_char(b)] if ch is not None}
_CODE = {ch: b for b, ch in _SHOWN.items()}


def decode(raw: bytes) -> str:
    out = []
    for b in raw:
        ch = _SHOWN.get(b)
        out.append(ch if ch is not None else "{%02X}" % b)
    return "".join(out)


def encode(text: str) -> bytes:
    out = bytearray()
    pos = 0
    for m in TAG_RE.finditer(text):
        out += _plain(text[pos:m.start()])
        out.append(int(m.group(1), 16))
        pos = m.end()
    out += _plain(text[pos:])
    return bytes(out)


def _plain(text: str) -> bytes:
    out = bytearray()
    for ch in text:
        code = _CODE.get(ch)
        if code is None:
            raise ValueError(f"character {ch!r} is not in the game's text (use {{XX}} for a code)")
        out.append(code)
    return bytes(out)


def build(messages: List[bytes]) -> bytes:
    """A message file from its messages: the count, the offsets (from the file start), then the messages.
    Each message is padded to 2 bytes."""
    if not messages:
        return b"\x00\x00"  # an empty message file
    padded = [m if len(m) % 2 == 0 else m + b"\x00" for m in messages]
    count = len(padded)
    table = bytearray(struct.pack("<H", count))
    position = 2 + 2 * count
    for m in padded:
        table += struct.pack("<H", position // 2)
        position += len(m)
    return bytes(table) + b"".join(padded)


# Ukrainian text (the Switch translation). The game draws the glyph whose atlas cell index equals the byte:
# atlas cell = byte (checked on known words of the translation and on fontwdata.bin widths).
# Cells 1..94 are the ASCII printable characters shifted by 0x20 (byte 0x0E is "." and 0x0C is ","), cell 0 is a
# space, cell 95 is empty. Cells 96..222 are Cyrillic and Latin-1 letters. Cell 223 and bytes 0xE0..0xFF are
# not letters: they stay tags (0xFD is the line break, 0xFF ends a message).
# Cell 122 (byte 0x7A) is the spare Russian-only Ъ of the atlas, reused for the capital Ї that the atlas lacks.
# Its bitmap still looks like Ъ until the translator draws Ї in the Font Editor (the cell is labelled Ї there).
# Ъ has no cell now: encode raises for it, like for any letter outside Ukrainian.
_UK_CYRILLIC_UPPER = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЇЫЬЄЮЯ"   # cells 96..127
_UK_CYRILLIC_LOWER = "абвгдежзийклмнопрстуфхцчшщъыьєюя"   # cells 128..159
_UK_LATIN1 = (                                              # cells 160..222
    "ÀÁÂÃÄÅÆÇÈÉÊËІÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß"
    "àáâãäåæґèéêëіíîїҐñòóôõö÷øùúûüýþ"
)


def _build_uk_table() -> List[Optional[str]]:
    table: List[Optional[str]] = [" "] + [chr(b + 0x20) for b in range(1, 95)] + [None]
    table += list(_UK_CYRILLIC_UPPER) + list(_UK_CYRILLIC_LOWER)
    table += list(_UK_LATIN1)
    table += [None] * (256 - len(table))
    assert len(table) == 256
    return table


UK_CELLS: List[Optional[str]] = _build_uk_table()
_UK_REVERSE = {ch: b for b, ch in enumerate(UK_CELLS) if ch is not None and b != 0}


def decode_uk(raw: bytes) -> str:
    out = []
    for b in raw:
        if b == 0x00:
            out.append(" ")
        elif UK_CELLS[b] is not None:
            out.append(UK_CELLS[b])
        else:
            out.append("{%02X}" % b)
    return "".join(out)


def encode_uk(text: str) -> bytes:
    out = bytearray()
    pos = 0
    for m in TAG_RE.finditer(text):
        out += _plain_uk(text[pos:m.start()])
        out.append(int(m.group(1), 16))
        pos = m.end()
    out += _plain_uk(text[pos:])
    return bytes(out)


def _plain_uk(text: str) -> bytes:
    out = bytearray()
    for ch in text:
        if ch == " ":
            out.append(0x00)
        elif ch in _UK_REVERSE:
            out.append(_UK_REVERSE[ch])
        else:
            raise ValueError(f"character {ch!r} has no glyph in the Ukrainian font (use {{XX}} for a code)")
    return bytes(out)
