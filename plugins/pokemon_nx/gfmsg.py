"""Game Freak message files of the Switch Pokémon games (Sword/Shield, Legends: Arceus): ``.dat`` + ``.tbl``.

``.dat`` (one section): u16 section count (1), u16 line count, u32 section length, u32 initial key (0),
u32 section offset (0x10); the section starts with its u32 length, then one 8-byte entry per line (s32
offset from the section start, u16 length in UTF-16 units with the terminator, u16 flags), then the
lines, each padded to 4 bytes. Every line is XOR-scrambled word by word: the key starts at
``0x7C89 + 0x2983 * line`` and turns left by 3 bits after each word.

In a line, ``0x0010 n code args...`` is a game command (``n`` words follow: the code and its
arguments); everything else is UTF-16 text ending with ``0x0000``. The editor shows a command as
``[VAR XXXX]`` / ``[VAR XXXX(AAAA,BBBB)]`` (hex, as pkNX prints them), and a word that is not plain
text (a button icon in the private-use area, a control character, a literal bracket, a zero before the
terminator) as ``[XXXX]``.

``.tbl`` (``AHTB``): u32 count, then per line a u64 FNV-1a hash, a u16 name length and the
zero-terminated label (``msg_ui_bag_category``).
"""
from __future__ import annotations

import re
import struct
from typing import List, Tuple

KEY_BASE, KEY_ADVANCE = 0x7C89, 0x2983
VAR = 0x0010
TAG_RE = re.compile(r"\[VAR ([0-9A-Fa-f]{4})(?:\(([0-9A-Fa-f]{4}(?:,[0-9A-Fa-f]{4})*)\))?\]|\[([0-9A-Fa-f]{4})\]")


class FormatError(ValueError):
    """Not a message file of this format."""


def _crypt(words: List[int], key: int) -> List[int]:
    out = []
    for word in words:
        out.append(word ^ key)
        key = ((key << 3) | (key >> 13)) & 0xFFFF
    return out


def _plain(word: int) -> bool:
    return word >= 0x20 and word not in (0x5B, 0x5D) and not 0xE000 <= word <= 0xF8FF


def decode(words: List[int]) -> str:
    """Editor text of one line (its words without the terminator)."""
    out, run, i = [], [], 0

    def flush():
        if run:
            out.append(struct.pack(f"<{len(run)}H", *run).decode("utf-16-le", "surrogatepass"))
            run.clear()

    while i < len(words):
        word = words[i]
        if word == VAR and i + 2 < len(words) and words[i + 1] >= 1 and i + 2 + words[i + 1] <= len(words):
            flush()
            code, *args = words[i + 2:i + 2 + words[i + 1]]
            out.append(f"[VAR {code:04X}" + (f"({','.join(f'{a:04X}' for a in args)})" if args else "") + "]")
            i += 2 + words[i + 1]
            continue
        if word == 0x0A or _plain(word):
            run.append(word)
        else:
            flush()
            out.append(f"[{word:04X}]")
        i += 1
    flush()
    return "".join(out)


def encode(text: str) -> List[int]:
    """Words of one line (without the terminator) from editor text."""
    words: List[int] = []
    at = 0
    for match in TAG_RE.finditer(text):
        words += _utf16(text[at:match.start()])
        if match.group(1):
            args = [int(a, 16) for a in match.group(2).split(",")] if match.group(2) else []
            words += [VAR, 1 + len(args), int(match.group(1), 16), *args]
        else:
            words.append(int(match.group(3), 16))
        at = match.end()
    return words + _utf16(text[at:])


def _utf16(text: str) -> List[int]:
    raw = text.encode("utf-16-le", "surrogatepass")
    return list(struct.unpack(f"<{len(raw) // 2}H", raw))


class MessageFile:
    """One ``.dat``: its lines as editor text; ``build`` writes it back (the original bytes when unchanged)."""

    def __init__(self, data: bytes):
        if len(data) < 0x14:
            raise FormatError("too short")
        sections, count, total, key, at = struct.unpack_from("<HHIII", data, 0)
        if sections != 1 or key != 0 or at != 0x10 or struct.unpack_from("<I", data, at)[0] != total \
                or at + total > len(data) or at + 4 + 8 * count > len(data):
            raise FormatError("not a Game Freak message file")
        self.raw = bytes(data)
        self.flags: List[int] = []
        self.words: List[Tuple[int, ...]] = []
        for line in range(count):
            offset, length, flags = struct.unpack_from("<iHH", data, at + 4 + 8 * line)
            if length < 1 or at + offset + 2 * length > len(data):
                raise FormatError(f"line {line} is outside the file")
            words = _crypt(list(struct.unpack_from(f"<{length}H", data, at + offset)),
                           (KEY_BASE + KEY_ADVANCE * line) & 0xFFFF)
            if words[-1] != 0:
                raise FormatError(f"line {line} has no terminator")
            self.flags.append(flags)
            self.words.append(tuple(words[:-1]))

    def texts(self) -> List[str]:
        return [decode(list(words)) for words in self.words]

    def build(self, texts: List[str]) -> bytes:
        if len(texts) != len(self.words):
            raise ValueError(f"{len(texts)} lines for a file of {len(self.words)}")
        lines = [tuple(encode(text)) for text in texts]
        return self.raw if lines == self.words else self.pack(lines)

    def pack(self, lines: List[Tuple[int, ...]]) -> bytes:
        """The file of these lines (words without terminators), laid out as the game's own files are."""
        table = bytearray()
        body = bytearray()
        start = 4 + 8 * len(lines)
        for index, (words, flags) in enumerate(zip(lines, self.flags)):
            table += struct.pack("<iHH", start + len(body), len(words) + 1, flags)
            body += struct.pack(f"<{len(words) + 1}H", *_crypt([*words, 0], (KEY_BASE + KEY_ADVANCE * index) & 0xFFFF))
            body += b"\0" * (-len(body) % 4)
        section = struct.pack("<I", start + len(body)) + table + body
        return struct.pack("<HHIII", 1, len(lines), len(section), 0, 0x10) + section


def read_labels(data: bytes) -> List[str]:
    """Labels of a ``.tbl`` (``AHTB``), one per line; empty when the data is not one."""
    if data[:4] != b"AHTB":
        return []
    count = struct.unpack_from("<I", data, 4)[0]
    out, at = [], 8
    for _ in range(count):
        if at + 10 > len(data):
            break
        length = struct.unpack_from("<H", data, at + 8)[0]
        out.append(data[at + 10:at + 10 + length].split(b"\0", 1)[0].decode("utf-8", "replace"))
        at += 10 + length
    return out
