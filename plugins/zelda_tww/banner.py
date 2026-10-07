"""The disc banner ``opening.bnr`` (BNR1): the game's name and description in the GameCube menu and Dolphin.

After the 0x20-byte header and the 96x32 RGB5A3 picture (0x1800 bytes): short name (32 bytes), short maker
(32), long name (64), long maker (64), description (128, may hold one line break); NUL-padded Windows-1252
text. The console's menu font has Latin letters only, so text that does not fit Windows-1252 is refused.
"""
from __future__ import annotations

from typing import List, Sequence

MAGIC = b"BNR1"
FIELDS = ((0x1820, 32, "Short name"), (0x1840, 32, "Short maker"), (0x1860, 64, "Long name"),
          (0x18A0, 64, "Long maker"), (0x18E0, 128, "Description"))


def is_banner(data: bytes) -> bool:
    return data[:4] == MAGIC and len(data) >= 0x1960


def read(data: bytes) -> List[str]:
    return [data[at:at + size].split(b"\0")[0].decode("cp1252", "replace") for at, size, _label in FIELDS]


def write(data: bytes, texts: Sequence[str]) -> bytes:
    out = bytearray(data)
    for (at, size, label), text, old in zip(FIELDS, texts, read(data)):
        if text == old:
            continue
        try:
            raw = str(text).encode("cp1252")
        except UnicodeEncodeError:
            raise ValueError(f"Disc banner, {label}: the GameCube menu shows Latin letters only") from None
        if len(raw) >= size:
            raise ValueError(f"Disc banner, {label}: {len(raw)} bytes, the field holds {size - 1}")
        out[at:at + size] = raw + bytes(size - len(raw))
    return bytes(out)
