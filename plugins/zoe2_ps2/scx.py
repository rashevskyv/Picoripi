"""The stage script (``.scx``) of Zone of the Enders: The 2nd Runner, as text.

A script is a byte code whose code and strings share one file. A string is a NUL-terminated run of bytes, and the code
points at it with the instruction ``80 b0 c2 <u32 file offset>``. Text is found by those pointers, not by scanning the
bytes: the text strings of a script are the pointed-at runs that look like text (see ``is_text``), listed in the order
of their first reference, which does not change when a string moves.

Writing a string back: a string that fits its old place is written there (the rest of the old place becomes NUL); a
longer string is appended at the end of the file and every pointer to the old place is changed. The code itself is
never moved, so jump targets stay valid. The file stays a multiple of 16 bytes, as the game's packer keeps it.

In the editor a line break is ``\\n`` (the game's ``|``), and every other control byte is a tag: ``{80:7C}`` and
``{83:02}`` for the two-byte codes (a line break inside a subtitle, a button picture) and ``{0A}`` for one byte.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, NamedTuple, Tuple

from core.i18n import tr

POINTER = re.compile(rb"\x80\xb0\xc2(....)", re.S)
PAIRS = (b"\x80\x7c", b"\x83\x02", b"\x83\x04")          # the two-byte codes seen in text
TAG = re.compile(r"\{([0-9A-Fa-f]{2})(?::([0-9A-Fa-f]{2}))?\}")
IDENTIFIER = re.compile(rb"[A-Za-z0-9_\-]*[_0-9][A-Za-z0-9_.\-]*|[A-Za-z0-9_\-]+\.[A-Za-z0-9]+")   # a resource name or a label
ALIGN = 16


class Entry(NamedTuple):
    offset: int         # where the string starts
    end: int            # where its NUL is
    refs: Tuple[int, ...]   # positions of the pointers to it

    @property
    def raw_length(self) -> int:
        return self.end - self.offset


def _clean(raw: bytes) -> bytes:
    for pair in PAIRS:
        raw = raw.replace(pair, b"")
    return raw


def is_text(raw: bytes) -> bool:
    """True for a run that is text for the player, not a resource name, a label or a piece of code."""
    plain = _clean(raw)
    if not plain or not 0x20 <= plain[0] < 0x7F:
        return False
    if not all(0x20 <= b < 0x7F or b == 0x0A for b in plain):
        return False
    if not re.search(rb"[A-Za-z?]", plain):
        return False
    return not IDENTIFIER.fullmatch(plain)


def find_entries(data: bytes) -> List[Entry]:
    """The text strings of a script in the order of their first pointer."""
    refs: Dict[int, List[int]] = {}
    for match in POINTER.finditer(data):
        target = struct.unpack("<I", match.group(1))[0]
        if 0 < target < len(data):
            refs.setdefault(target, []).append(match.start(1))
    entries = []
    for target, positions in refs.items():
        end = data.find(b"\x00", target)
        if end > target and is_text(data[target:end]):
            entries.append(Entry(target, end, tuple(positions)))
    entries.sort(key=lambda e: e.refs[0])
    return entries


def decode(raw: bytes) -> str:
    out = []
    i = 0
    while i < len(raw):
        pair = raw[i:i + 2]
        if pair in PAIRS:
            out.append("{%02X:%02X}" % (pair[0], pair[1]))
            i += 2
            continue
        b = raw[i]
        out.append("\n" if b == 0x7C else chr(b) if 0x20 <= b < 0x7F else "{%02X}" % b)
        i += 1
    return "".join(out)


def encode(text: str) -> Tuple[bytes, List[str]]:
    """The bytes of an edited string and the characters the game's font cannot show (each written as ``?``)."""
    out = bytearray()
    lost: List[str] = []
    i = 0
    while i < len(text):
        tag = TAG.match(text, i)
        if tag:
            out.append(int(tag.group(1), 16))
            if tag.group(2):
                out.append(int(tag.group(2), 16))
            i = tag.end()
            continue
        c = text[i]
        if c == "\n":
            out.append(0x7C)
        elif 0x20 <= ord(c) < 0x7F:
            out.append(ord(c))
        else:
            lost.append(c)
            out.append(ord("?"))
        i += 1
    return bytes(out), lost


def apply(data: bytes, new_raw: Dict[int, bytes]) -> bytes:
    """``data`` with the strings that start at the keys replaced by the values (raw bytes, no NUL)."""
    entries = {e.offset: e for e in find_entries(data)}
    out = bytearray(data)
    tail = bytearray()
    for offset, raw in new_raw.items():
        entry = entries.get(offset)
        if entry is None:
            raise ValueError(tr("There is no text string at offset {0}.", offset))
        old = data[entry.offset:entry.end]
        if raw == old:
            continue
        if len(raw) <= entry.raw_length:
            out[entry.offset:entry.end + 1] = raw + b"\x00" * (entry.raw_length + 1 - len(raw))
            continue
        moved = len(data) + len(tail)
        tail += raw + b"\x00"
        for ref in entry.refs:
            struct.pack_into("<I", out, ref, moved)
    out += tail
    out += b"\x00" * (-len(out) % ALIGN)
    return bytes(out)


def read_texts(data: bytes) -> List[str]:
    return [decode(data[e.offset:e.end]) for e in find_entries(data)]


def write_texts(data: bytes, texts: List[str]) -> Tuple[bytes, List[str]]:
    """``data`` with its text strings replaced by ``texts`` (as ``read_texts`` returns them), and the problems found.

    A string is found again by its looks (``is_text``), so an edit that would make it look like a resource name or lose
    its letters gets one space at the end; a character the font cannot show is written as ``?``. Each problem is a line
    of text for the log.
    """
    entries = find_entries(data)
    if len(texts) != len(entries):
        raise ValueError(tr("The script has {0} strings, not {1}.", len(entries), len(texts)))
    changes: Dict[int, bytes] = {}
    problems: List[str] = []
    for entry, text in zip(entries, texts):
        raw, lost = encode(text)
        if lost:
            problems.append(f"no glyph for {''.join(sorted(set(lost)))} in {text[:40]!r}")
        if not is_text(raw):
            raw += b" "
            if not is_text(raw):
                problems.append(f"{text[:40]!r} is not recognised as text; it is not written")
                continue
        if raw != data[entry.offset:entry.end]:
            changes[entry.offset] = raw
    return (apply(data, changes) if changes else data), problems
