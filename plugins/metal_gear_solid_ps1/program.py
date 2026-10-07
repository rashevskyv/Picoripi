"""Strings of the game program (``SLUS_005.94``) and of the stage overlays (``*.bin`` of STAGE.DIR).

Code points at these strings by address, so each one is edited in place: it may take the bytes of its
slot -- the string, its NUL and the padding up to the next 4-byte boundary -- and no more. The strings
are found by their shape: word-aligned, after a zero byte, NUL-terminated, made of ASCII and the
game's two-byte codes, with words in them; the developers' debug messages are left out.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from . import codec

PSX_EXE = b"PS-X EXE"
_DEBUG = re.compile(r"%|!!|\.c\b|\.(pcx|dbl|dat|pll|kmd|dmo|str)\b|error|ERROR|Error|Warning|WARNING|illegal|[a-z]_[a-z]|"
                    r"^[a-z0-9_]+$|MEMORY FOR|MEMCARD|NO MEMORY|SCRIPT|Wrong|::|cancel|sync|Sync|"
                    r"\.(DAT|DIR|STR|94|76)\b|^S?L?US|^BASLUS|Sony|Library|^wait|^TLB|^CD|CDROM|0123456789|NULL|"
                    r"^Jul |TASK|VBL|PLAYSTATION|no data on CD")
_TWO_BYTE = (0x80, 0x90, 0xB0, 0xC0, 0xD0)


def _string_end(data: bytes, start: int) -> int:
    """End (the NUL) of a text-shaped string at ``start``, or -1."""
    pos, n = start, len(data)
    while pos < n:
        byte = data[pos]
        if byte == 0:
            return pos
        if 0x20 <= byte < 0x7F:
            pos += 1
        elif byte in _TWO_BYTE and pos + 1 < n and data[pos + 1]:
            pos += 2
        else:
            return -1
    return -1


def is_program(data: bytes) -> bool:
    return data[:8] == PSX_EXE


def find(data: bytes) -> List[Tuple[int, int]]:
    """``(start, room)`` of every text string; ``room`` counts the NUL and the padding."""
    found = []
    pos = 4 if is_program(data) else 0
    n = len(data)
    while pos < n - 4:
        if data[pos] and (pos == 0 or data[pos - 1] == 0):
            end = _string_end(data, pos)
            if end - pos >= 3:
                raw = data[pos:end]
                text = codec.TAG_RE.sub(" ", codec.decode(raw, codec.SUB_LF, codec.PLAIN_QUOTE))
                if (re.search(r"[A-Za-z]{3}", text) and not _DEBUG.search(text)
                        and (" " in text.strip() or text.isupper() or len(text) > 12)):
                    room = (end + 4) // 4 * 4 - pos
                    found.append((pos, room))
                    pos += room
                    continue
        pos += 4
    return found
