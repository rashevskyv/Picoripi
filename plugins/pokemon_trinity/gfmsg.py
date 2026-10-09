"""Game Freak message files (``.dat``) of Pokémon Scarlet/Violet and Legends: Z-A (the same since Sword/Shield).

Layout: u16 sections (1), u16 line count, u32 section size, u32 initial key (0), u32 section offset (0x10);
the section: u32 size, then per line {i32 offset, u16 length in UTF-16 units with the terminator, u16 flags},
then the lines, each padded to 4 bytes. A line is XOR-encrypted: key ``0x7C89 + 0x2983 * index``, rotated
left by 3 after every unit.

Editor text: ``\\n`` is a line break; a variable (``0x0010``, count, code, arguments) is a tag:
``{SCROLL}`` (BE00, the window scrolls), ``{PAGE}`` (BE01, a new window), ``{WAIT 0010}``, ``{NULL 0018}``,
``{COLOR 0001}``, and ``{VAR 0102 0000}`` for the rest (hex). Grammar branches carry their two texts, whose lengths
the game reads from the last argument: ``M{GENDER 00FF|aster|iss}`` (the player's gender), ``point{PLURAL 0001||s}``,
``{VERSION 00FF|Ko|Mi}raidon`` (Scarlet | Violet); the lengths are written again on save.
"""
from __future__ import annotations

import re
import struct
from typing import List, Tuple

NAMES = {0xBE00: "SCROLL", 0xBE01: "PAGE", 0xBE02: "WAIT", 0xBDFF: "NULL", 0xFF00: "COLOR"}
BRANCHES = {0x1100: "GENDER", 0x1101: "PLURAL", 0x1107: "VERSION"}
CODES = {name: code for code, name in {**NAMES, **BRANCHES}.items()}
TAG_RE = re.compile(r"\{(?:[A-Z]+(?: [0-9A-F]{4})*(?:\|[^{}|]*\|[^{}|]*)?)\}")


def is_gfmsg(data: bytes) -> bool:
    if len(data) < 0x14:
        return False
    sections, count, size, key, offset = struct.unpack_from("<HHIII", data)
    return sections == 1 and key == 0 and offset == 0x10 and size + 0x10 == len(data) and \
        struct.unpack_from("<I", data, 0x10)[0] == size and 4 + 8 * count <= size


def _crypt(units, index: int) -> List[int]:
    key = (0x7C89 + index * 0x2983) & 0xFFFF
    out = []
    for unit in units:
        out.append(unit ^ key)
        key = ((key << 3) | (key >> 13)) & 0xFFFF
    return out


def read(data: bytes) -> List[Tuple[List[int], int]]:
    """``[(UTF-16 units without the terminator, flags)]`` of every line."""
    if not is_gfmsg(data):
        raise ValueError("not a Game Freak message file")
    count = struct.unpack_from("<H", data, 2)[0]
    lines = []
    for i in range(count):
        offset, length, flags = struct.unpack_from("<iHH", data, 0x14 + 8 * i)
        units = _crypt(struct.unpack_from(f"<{length}H", data, 0x10 + offset), i)
        if not units or units[-1] != 0:
            raise ValueError(f"line {i} has no terminator")
        lines.append((units[:-1], flags))
    return lines


def write(lines: List[Tuple[List[int], int]]) -> bytes:
    """The file of ``[(units, flags)]`` (the inverse of ``read``)."""
    table, body = bytearray(), bytearray()
    start = 4 + 8 * len(lines)
    for i, (units, flags) in enumerate(lines):
        coded = _crypt(list(units) + [0], i)
        table += struct.pack("<iHH", start + len(body), len(coded), flags)
        body += struct.pack(f"<{len(coded)}H", *coded)
        body += b"\0" * (-len(body) % 4)
    size = 4 + len(table) + len(body)
    return struct.pack("<HHIIII", 1, len(lines), size, 0, 0x10, size) + bytes(table) + bytes(body)


def to_editor(units: List[int]) -> str:
    out, k = [], 0
    while k < len(units):
        unit = units[k]
        if unit == 0x10 and k + 2 < len(units):
            count = units[k + 1]
            code, args = units[k + 2], units[k + 3:k + 2 + count]
            k += 2 + count
            if code in BRANCHES and len(args) == 2:
                first, second = args[-1] & 0xFF, args[-1] >> 8
                texts = units[k:k + first], units[k + first:k + first + second]
                plain = all(u >= 0x20 and chr(u) not in "{}|" for u in texts[0] + texts[1])
                if plain and len(texts[0]) + len(texts[1]) == first + second:
                    out.append("{%s %04X|%s|%s}" % (BRANCHES[code], args[0], "".join(map(chr, texts[0])),
                                                    "".join(map(chr, texts[1]))))
                    k += first + second
                    continue
            name = NAMES.get(code)
            out.append("{" + " ".join([name] if name else ["VAR", f"{code:04X}"]) +
                       "".join(f" {a:04X}" for a in args) + "}")
            continue
        out.append(chr(unit))
        k += 1
    return "".join(out)


def from_editor(text: str) -> List[int]:
    units: List[int] = []
    pos = 0
    for m in TAG_RE.finditer(text):
        units += _chars(text[pos:m.start()])
        pos = m.end()
        body, *texts = m.group(0)[1:-1].split("|")
        words = body.split()
        if words[0] == "VAR":
            code, args = int(words[1], 16), [int(w, 16) for w in words[2:]]
        else:
            code, args = CODES[words[0]], [int(w, 16) for w in words[1:]]
        if texts:
            first, second = _chars(texts[0]), _chars(texts[1])
            if len(first) > 0xFF or len(second) > 0xFF:
                raise ValueError(f"branch text too long: {m.group(0)}")
            units += [0x10, len(args) + 2, code, *args, len(second) << 8 | len(first), *first, *second]
        else:
            units += [0x10, len(args) + 1, code, *args]
    return units + _chars(text[pos:])


def _chars(text: str) -> List[int]:
    data = text.replace("\r\n", "\n").encode("utf-16-le", "surrogatepass")
    return list(struct.unpack(f"<{len(data) // 2}H", data))
