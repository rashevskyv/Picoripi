r"""The text written into a Wii 2D layout (``.brlyt``): the initial string of each text box (``txt1`` section).

A layout is a header (``RLYT``, byte order mark, version, u32 file size, u16 header size, u16 section count) and
a flat list of sections (magic, u32 size). A ``txt1`` section is a pane (0x4C bytes: name at 0x0C) and then
u16 buffer size, u16 string size (bytes, with the 0000 end), ..., u32 string offset at 0x58 (from the section
start); the UTF-16 string comes last, padded to 4 bytes. Nothing points across sections, so a longer string only
grows its own section (the buffer grows with it).

Most boxes hold placeholders the game overwrites at run time (``iiii…``, ``あああ``, ``99999999``); those are not
shown. The rest are words the screen shows as they are (``Screen``, ``追加された！``).
"""
from __future__ import annotations

import struct
from typing import List, Tuple

MAGIC = b"RLYT"
_PLACEHOLDER = "iあ9\n"                     # a text box of only these characters is filled at run time


def is_brlyt(raw: bytes) -> bool:
    return bytes(raw[:4]) == MAGIC


def _sections(raw: bytes) -> List[Tuple[int, int]]:
    if not is_brlyt(raw):
        raise ValueError("Not a Wii layout (RLYT)")
    head, count = struct.unpack_from(">HH", raw, 0x0C)
    out, at = [], head
    for _ in range(count):
        size = struct.unpack_from(">I", raw, at + 4)[0]
        out.append((at, size))
        at += size
    return out


def _string(raw: bytes, at: int) -> str:
    size = struct.unpack_from(">H", raw, at + 0x4E)[0]
    start = at + struct.unpack_from(">I", raw, at + 0x58)[0]
    return raw[start:start + size].decode("utf-16-be").rstrip("\0") if size else ""


def boxes(raw: bytes) -> List[Tuple[str, str]]:
    """``[(pane name, text)]`` of every text box whose text the screen shows (placeholders left out)."""
    out = []
    for at, _size in _sections(raw):
        if raw[at:at + 4] == b"txt1":
            text = _string(raw, at)
            if text.strip(_PLACEHOLDER):
                out.append((raw[at + 0x0C:at + 0x1C].split(b"\0")[0].decode("ascii", "replace"), text))
    return out


def build(raw: bytes, texts: List[str]) -> bytes:
    """``raw`` with the shown boxes (in ``boxes`` order) set to ``texts``; unchanged boxes keep their bytes."""
    out = bytearray(raw[:struct.unpack_from(">H", raw, 0x0C)[0]])
    pending = list(texts)
    for at, size in _sections(raw):
        section = raw[at:at + size]
        if section[:4] == b"txt1":
            old = _string(raw, at)
            if old.strip(_PLACEHOLDER):
                new = pending.pop(0)
                if new != old:
                    section = _text_box(section, new)
        out += section
    if pending:
        raise ValueError(f"The layout has fewer text boxes than {len(texts)}")
    struct.pack_into(">I", out, 0x08, len(out))
    return bytes(out)


def _text_box(section: bytes, text: str) -> bytes:
    data = text.replace("\r\n", "\n").encode("utf-16-be") + b"\0\0"
    start = struct.unpack_from(">I", section, 0x58)[0]
    box = bytearray(section[:start]) + data
    box += bytes(-len(box) % 4)
    buffer = struct.unpack_from(">H", box, 0x4C)[0]
    struct.pack_into(">HH", box, 0x4C, max(buffer, len(data)), len(data))
    struct.pack_into(">I", box, 4, len(box))
    return bytes(box)
