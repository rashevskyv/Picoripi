"""Split a decoded text entry into text and binary segments. Joining the segments restores the entry exactly.

Text is what a translator reads. Inside a text segment, printable ASCII and the newline are plain characters.
Every other byte of a text run (inline codes such as 0xAF, 0xBA, 0x80-0xFF) is written as a tag ``[@hh]``, and a
literal ``[`` is written as ``[@5B]``. Tags map back to their bytes on save, so the round trip is exact.

A run is text when it holds at least one space and is at least ``MIN_TEXT_LENGTH`` bytes long, or when it is a
NUL-bounded string with at least three ASCII letters (menu and chapter names are often one word).
"""
from __future__ import annotations

import binascii
import re
from typing import Any, Dict, List, Tuple

MIN_TEXT_LENGTH = 8
NEWLINE = 0x0A
_TEXT_BYTES = frozenset(range(0x20, 0x7F)) | {NEWLINE} | frozenset(range(0x80, 0x100))
_TAG = re.compile(r"\[@([0-9A-Fa-f]{2})\]")

Segment = Tuple[str, bytes]  # ("text" | "bin", raw bytes)


def _is_letter(byte: int) -> bool:
    return 0x41 <= byte <= 0x5A or 0x61 <= byte <= 0x7A


def _qualifies(run: bytes, bounded: bool) -> bool:
    """A run is text when it has three letters, at least half plain characters, and either a space
    (eight bytes or more) or NUL bounds on both sides."""
    letters = sum(1 for byte in run if _is_letter(byte))
    plain = sum(1 for byte in run if 0x20 <= byte <= 0x7E or byte == NEWLINE)
    if letters < 3 or 2 * plain < len(run):
        return False
    return bounded or (len(run) >= MIN_TEXT_LENGTH and b" " in run)


def split_segments(data: bytes) -> List[Segment]:
    """Return the segments of ``data`` in order. ``b"".join(raw for _, raw in result) == data``."""
    segments: List[Segment] = []
    binary_start = 0
    pos = 0
    size = len(data)
    while pos < size:
        if data[pos] not in _TEXT_BYTES:
            pos += 1
            continue
        end = pos
        while end < size and data[end] in _TEXT_BYTES:
            end += 1
        run = data[pos:end]
        bounded = (pos == 0 or data[pos - 1] == 0) and (end == size or data[end] == 0)
        if _qualifies(run, bounded):
            if pos > binary_start:
                segments.append(("bin", data[binary_start:pos]))
            segments.append(("text", run))
            binary_start = end
        pos = end
    if binary_start < size:
        segments.append(("bin", data[binary_start:]))
    return segments


def join_segments(segments: List[Segment]) -> bytes:
    return b"".join(raw for _, raw in segments)


def bytes_to_string(raw: bytes) -> str:
    """Editor form of a text run: newline kept, every other byte not plain ASCII as a [@hh] tag."""
    out = []
    for byte in raw:
        if byte == NEWLINE:
            out.append("\n")
        elif 0x20 <= byte <= 0x7E and byte not in (0x5B,):
            out.append(chr(byte))
        else:
            out.append(f"[@{byte:02X}]")
    return "".join(out)


def string_to_bytes(text: str) -> bytes:
    """Inverse of bytes_to_string. Raises ValueError for a character the text form cannot carry."""
    out = bytearray()
    pos = 0
    while pos < len(text):
        match = _TAG.match(text, pos)
        if match:
            out.append(int(match.group(1), 16))
            pos = match.end()
            continue
        char = text[pos]
        if char == "\n":
            out.append(NEWLINE)
        elif 0x20 <= ord(char) <= 0x7E and char != "[":
            out.append(ord(char))
        else:
            raise ValueError(f"character {char!r} is not plain ASCII; write it as a [@hh] tag")
        pos += 1
    return bytes(out)


def to_json_segments(segments: List[Segment]) -> List[Dict[str, Any]]:
    """Editor-facing form: text as a string with tags, binary as hex."""
    out: List[Dict[str, Any]] = []
    for kind, raw in segments:
        if kind == "text":
            out.append({"kind": "text", "text": bytes_to_string(raw)})
        else:
            out.append({"kind": "bin", "hex": binascii.hexlify(raw).decode("ascii")})
    return out


def from_json_segments(items: List[Dict[str, Any]]) -> List[Segment]:
    segments: List[Segment] = []
    for item in items:
        if item["kind"] == "text":
            segments.append(("text", string_to_bytes(item["text"])))
        elif item["kind"] == "bin":
            segments.append(("bin", binascii.unhexlify(item["hex"])))
        else:
            raise ValueError(f"unknown segment kind {item['kind']!r}")
    return segments
