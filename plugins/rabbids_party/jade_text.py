r"""Text of Rayman Raving Rabbids 1 and 2 (Jade engine, Montpellier): a ``.jtxt`` file of English text lists.

The workspace's ``1_unpack.bat`` collects every English text list (``.txl``) of the game's text bins into one
file: ``JTXT``, u32 count, then per list u32 key, u32 size and the list. A list (little endian) is u32 count,
then per text u32 id key, u32 object key, s32 offset in the string buffer (-1: no text), u16 priority, u16
version, 4 bytes (facial, lips, animation, dummy) when the version is 1 or more, u32 comment length; then the
NUL-terminated strings. Strings are single bytes (cp1252) with ``\n`` (0x0A) breaks and backslash codes:
``\cFF7FFF\`` colour, ``\p16\a`` a button icon, ``\m1\`` a number, ``\h0.18\`` size, ``\jxy\`` alignment,
``\n`` a break. Rebuilding lays the strings out again in text order; unchanged lists keep their bytes.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Optional, Set, Tuple

MAGIC = b"JTXT"
TAG_PATTERN = r"\\p\d+\\.|\\[cChjmPpwxyADJb][^\\\n]*\\|\\d.|\\[nFfu]"
TAG_RE = re.compile(TAG_PATTERN)


def is_jtxt(raw: bytes) -> bool:
    return bytes(raw[:4]) == MAGIC


def read(raw: bytes) -> Dict[int, bytes]:
    """``{list key: list bytes}`` in file order."""
    out, at = {}, 8
    for _ in range(struct.unpack_from("<I", raw, 4)[0]):
        key, size = struct.unpack_from("<II", raw, at)
        out[key] = bytes(raw[at + 8:at + 8 + size])
        at += 8 + size
    return out


def write(lists: Dict[int, bytes]) -> bytes:
    return MAGIC + struct.pack("<I", len(lists)) + b"".join(
        struct.pack("<II", key, len(item)) + item for key, item in lists.items())


def parse(item: bytes) -> Tuple[List[Tuple[int, int]], List[Optional[bytes]], int]:
    """``(entries [(entry start, size)], strings, buffer start)``; a string is None where the text has none."""
    count, at, entries = struct.unpack_from("<I", item)[0], 4, []
    for _ in range(count):
        version = struct.unpack_from("<I", item, at + 12)[0] >> 16
        size = 16 + (4 if version >= 1 else 0) + 4
        entries.append((at, size))
        at += size
    buf = item[at:]
    strings = []
    for start, _size in entries:
        offset = struct.unpack_from("<i", item, start + 8)[0]
        strings.append(bytes(buf[offset:buf.index(b"\0", offset)]) if offset >= 0 else None)
    return entries, strings, at


def build(item: bytes, strings: List[Optional[bytes]]) -> bytes:
    """``item`` with its strings replaced (None keeps a text without a string)."""
    entries, old, at = parse(item)
    if list(strings) == old:
        return bytes(item)
    head, buf = bytearray(item[:at]), bytearray()
    for (start, _size), text in zip(entries, strings):
        if struct.unpack_from("<i", item, start + 8)[0] >= 0:
            struct.pack_into("<i", head, start + 8, len(buf))
            buf += (text or b"") + b"\0"
    return bytes(head + buf)


def decode(raw: bytes, shown: Dict[str, str]) -> str:
    """Editor text of game bytes: cp1252 (latin-1 for its five holes); a translation-map slot shows its letter."""
    text = "".join(bytes([b]).decode("cp1252", errors="ignore") or chr(b) for b in raw)
    return "".join(shown.get(ch, ch) for ch in text)


def encode(text: str, translation_map: Dict[str, str], missing: Set[str]) -> bytes:
    """Game bytes of editor text: a letter of the translation map becomes its font slot; a character with no
    byte becomes ``?`` and goes to ``missing``."""
    out = bytearray()
    for ch in text:
        ch = translation_map.get(ch, ch)
        try:
            out += ch.encode("cp1252")
        except UnicodeEncodeError:
            if ord(ch) < 256:
                out.append(ord(ch))
            else:
                missing.add(ch)
                out += b"?"
    return bytes(out)
