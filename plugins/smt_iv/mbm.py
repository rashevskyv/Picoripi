"""Atlus ``MSG2`` text tables (``.mbm``, Shin Megami Tensei IV / Apocalypse): Shift-JIS strings with control codes.

Header (little endian): u32 0, ``MSG2``, u32 version, u32 used size, u32 entry count, u32 table offset (0x20),
8 zero bytes. An entry (16 bytes): u32 id, u32 byte size, u32 offset, u32 0; a size of 0 is an empty entry.
A string is a run of 2-byte units: Shift-JIS characters (the English game writes full-width letters, shown
here as ASCII), ``F8xx`` control codes with 2-byte arguments, and ``FFFF`` at the end.

Editor text: ``\\n`` for ``F801``, ``{F8xx}`` / ``{F8xx 0001 ...}`` for a code with its arguments (hex numbers),
``{XXXX}`` for a unit that is no character. Decoding and encoding are exact inverses, so an unedited string
writes back byte for byte. The eight Ukrainian letters use the free Shift-JIS codes of ``core.font_formats.sjis``.
"""
from __future__ import annotations

import re
import struct
from typing import Dict, List, Sequence

from core.font_formats import sjis

NEWLINE = 0xF801
END = 0xFFFF
_TAG = re.compile(r"\{([0-9A-Fa-f]{4}(?: [0-9A-Fa-f]{4})*)\}")
# full-width ASCII (U+FF01..U+FF5E) and the ideographic space are shown as ASCII
_TO_ASCII = {chr(0xFF01 + i): chr(0x21 + i) for i in range(0x5E)}
_TO_ASCII["　"] = " "
_TO_WIDE = {ascii_char: wide for wide, ascii_char in _TO_ASCII.items()}


class FormatError(ValueError):
    pass


def _is_text(unit: int) -> bool:
    lead = unit >> 8
    if lead == 0xF8 or unit == END or not (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xEF):
        return False
    char = sjis.decode(unit)
    return ord(char) < 0xF0000


def decode(raw: bytes) -> str:
    """Editor text of a stored string (without its ``FFFF`` end)."""
    if len(raw) % 2:
        raise FormatError("odd string length")
    units = list(struct.unpack(f"<{len(raw) // 2}H", raw))
    units = [u >> 8 | (u & 0xFF) << 8 for u in units]   # big-endian pairs
    if units and units[-1] == END:
        units.pop()
    out: List[str] = []
    i = 0
    while i < len(units):
        unit = units[i]
        i += 1
        if unit == NEWLINE:
            out.append("\n")
        elif unit >> 8 == 0xF8:
            args = []
            while i < len(units) and not _is_text(units[i]) and units[i] >> 8 != 0xF8 and units[i] != END:
                args.append((units[i] & 0xFF) << 8 | units[i] >> 8)   # arguments are little-endian numbers
                i += 1
            out.append("{" + " ".join(f"{u:04X}" for u in [unit] + args) + "}")
        elif _is_text(unit):
            char = sjis.decode(unit)
            out.append(_TO_ASCII.get(char, char))
        else:
            out.append(f"{{{unit:04X}}}")
    return "".join(out)


def encode(text: str) -> bytes:
    """The stored bytes of editor text (with ``FFFF``). ``Table.build`` keeps an unchanged entry as it is, so an
    entry without bytes stays one."""
    units: List[int] = []
    at = 0
    for match in _TAG.finditer(text):
        units += [_code(c) for c in text[at:match.start()]]
        parts = [int(part, 16) for part in match.group(1).split()]
        units += parts[:1] + [(p & 0xFF) << 8 | p >> 8 for p in parts[1:]]   # arguments are little-endian numbers
        at = match.end()
    units += [_code(c) for c in text[at:]]
    units.append(END)
    return b"".join(u.to_bytes(2, "big") for u in units)


def _code(char: str) -> int:
    if char == "\n":
        return NEWLINE
    try:
        code = sjis.encode(_TO_WIDE.get(char, char))
    except UnicodeEncodeError:
        raise FormatError(f"{char!r} has no Shift-JIS code") from None
    if code < 0x100:
        raise FormatError(f"{char!r} is a one-byte character")
    return code


class Table:
    """A parsed ``.mbm``: ``ids`` and the raw ``entries`` in table order."""

    def __init__(self, raw: bytes):
        if raw[4:8] != b"MSG2" or len(raw) < 0x20:
            raise FormatError("not an MSG2 table")
        self.raw = bytes(raw)
        self.count, self.table = struct.unpack_from("<II", raw, 0x10)
        self.ids: List[int] = []
        self.entries: List[bytes] = []
        for i in range(self.count):
            ident, size, offset, _pad = struct.unpack_from("<4I", raw, self.table + i * 16)
            self.ids.append(ident)
            self.entries.append(raw[offset:offset + size] if size else b"")
        spans = [(offset, offset + size) for _i, size, offset in
                 ((i, *struct.unpack_from("<II", raw, self.table + i * 16 + 4)) for i in range(self.count)) if size]
        self.strings_at = min(s[0] for s in spans) if spans else self.table + self.count * 16
        self.end = max(s[1] for s in spans) if spans else self.strings_at

    def texts(self) -> List[str]:
        return [decode(entry) for entry in self.entries]

    def build(self, texts: Sequence[str]) -> bytes:
        """The table with texts; the strings are written again between the first and the last one, the bytes
        before (header, table, whatever lies between) and after stay."""
        if len(texts) != self.count:
            raise FormatError(f"{len(texts)} strings for {self.count} entries")
        blobs = [encode(str(t)) if str(t) != decode(e) else e for t, e in zip(texts, self.entries)]
        out = bytearray(self.raw[:self.strings_at])
        at = self.strings_at
        for i, blob in enumerate(blobs):
            if blob:
                struct.pack_into("<II", out, self.table + i * 16 + 4, len(blob), at)
                at += len(blob)
        out += b"".join(blobs)
        out += self.raw[self.end:]
        struct.pack_into("<I", out, 0x0C, struct.unpack_from("<I", self.raw, 0x0C)[0] + len(out) - len(self.raw))
        return bytes(out)


def table_or_none(raw: bytes):
    try:
        return Table(raw)
    except (FormatError, struct.error, ValueError):
        return None


def roles(path: str) -> Dict[str, str]:
    """``content_role`` and instruction by the file's folder."""
    p = path.replace("\\", "/").lower()
    if "/event/" in p or "/evt/" in p or "/quest/" in p or "/npc" in p or "mikado" in p:
        return {"content_role": "Dialogue", "role_instruction": "A line of story, quest or NPC dialogue in the message window."}
    if "/battle/" in p or "/btl" in p or "devilmsg" in p or "/talk/" in p:
        return {"content_role": "Battle text", "role_instruction": "A battle message, demon negotiation line or battle UI text."}
    if "/name/" in p or "bible" in p or "profile" in p or "item" in p or "skill" in p:
        return {"content_role": "Name or description", "role_instruction": "A demon, item, skill or place name or its description; short."}
    return {"content_role": "Menu or system text", "role_instruction": "A menu label, help text or system message."}
