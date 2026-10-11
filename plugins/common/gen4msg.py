"""Gen 4 (Nintendo DS) message banks: the binary text file of one NARC member.

Layout (decomp tools/msgenc, engine arm9/src/msgdata.c):
  u16 count, u16 key                      the header
  count x (u32 offset, u32 length)        the allocation table, both fields XOR-ed with ((765 * i * key) & 0xFFFF) doubled
  the lines, back to back, each ``length`` units of u16 from ``offset`` (offsets run on from the table)
Here ``i`` is the 1-based line number. Each unit is XOR-ed with a seed that starts at ``i * 596947`` and grows by
18749 per unit. A line ends with 0xFFFF. Control codes start with 0xFFFE: code, argument count, arguments.

Text form (the same tags as the decomp's GMM files): one line per message, control codes as ``{NAME args}``,
``{STRVAR_xx n}`` for variables. A line that starts with 0xF100 (compressed trainer name) is kept as raw units.

``decode_bank`` and ``encode_bank`` are exact inverses for the raw units, so an untouched line is written
from its raw units (``Bank.lines``) and the file stays byte-identical.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

END = 0xFFFF
ESC = 0xFFFE
COMPRESSED = 0xF100


class BankError(ValueError):
    """The bytes are not a Gen 4 message bank."""


def _line_seed(i: int) -> int:
    return (i * 596947) & 0xFFFF


def _alloc_key(i: int, key: int) -> int:
    k = (765 * i * key) & 0xFFFF
    return k | (k << 16)


@dataclass
class Bank:
    key: int
    lines: List[List[int]] = field(default_factory=list)   # raw decrypted units per line (END included)


def decode_bank(data: bytes) -> Bank:
    """Parse and decrypt a bank. Raises BankError when ``data`` is not one."""
    if len(data) < 4:
        raise BankError("message bank too short")
    count, key = struct.unpack_from("<HH", data, 0)
    if count == 0 or key == 0 or 4 + 8 * count > len(data):
        raise BankError("bad message bank header")
    pos = 4 + 8 * count
    bank = Bank(key=key)
    for n in range(count):
        i = n + 1
        off, ln = struct.unpack_from("<II", data, 4 + 8 * n)
        mask = _alloc_key(i, key)
        off ^= mask
        ln ^= mask
        if off != pos or ln == 0 or off + 2 * ln > len(data):
            raise BankError("bad allocation entry")
        seed = _line_seed(i)
        units = list(struct.unpack_from(f"<{ln}H", data, off))
        for j in range(ln):
            units[j] ^= seed
            seed = (seed + 18749) & 0xFFFF
        if units[-1] != END:
            raise BankError("line without terminator")
        bank.lines.append(units)
        pos = off + 2 * ln
    if pos != len(data):
        raise BankError("trailing bytes after the last line")
    return bank


def encode_bank(bank: Bank) -> bytes:
    """The bank bytes for ``bank``: the header, the allocation table and the encrypted lines."""
    count = len(bank.lines)
    table = bytearray()
    body = bytearray()
    pos = 4 + 8 * count
    for n, units in enumerate(bank.lines):
        i = n + 1
        mask = _alloc_key(i, bank.key)
        table += struct.pack("<II", pos ^ mask, len(units) ^ mask)
        seed = _line_seed(i)
        out = []
        for unit in units:
            out.append((unit ^ seed) & 0xFFFF)
            seed = (seed + 18749) & 0xFFFF
        body += struct.pack(f"<{len(out)}H", *out)
        pos += 2 * len(units)
    return struct.pack("<HH", count, bank.key) + bytes(table) + bytes(body)


# ---------------------------------------------------------------- text form

def load_charmap(path: str) -> Tuple[Dict[int, str], Dict[int, str]]:
    """``(characters, commands)`` of a decomp charmap.txt: code -> text; ``{NAME}`` entries go to commands."""
    chars: Dict[int, str] = {}
    cmds: Dict[int, str] = {}
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            # trailing spaces are part of the entry: "01DE= " is the plain space
            line = raw.split("//", 1)[0].rstrip("\r\n").lstrip(" \t")
            if not line or "=" not in line:
                continue
            code_s, text = line.split("=", 1)
            code = int(code_s, 16)
            if text.startswith("{") and text.endswith("}"):
                cmds[code] = text[1:-1]
            else:
                chars.setdefault(code, text)
    return chars, cmds


class Codec:
    """Text <-> units for one charmap. ``decode_line`` never loses data; ``encode_line`` inverts it."""

    def __init__(self, charmap_path: str):
        self.chars, self.cmds = load_charmap(charmap_path)
        self.cmd_codes = {name: code for code, name in self.cmds.items()}
        self.char_codes: Dict[str, int] = {}
        for code, text in sorted(self.chars.items()):
            self.char_codes.setdefault(text, code)
        self.strvar = {code & 0xFF00 for code, name in self.cmds.items() if name.startswith("STRVAR_")}

    def decode_line(self, units: List[int]) -> str:
        if units and units[0] == COMPRESSED:
            return "{RAW " + " ".join(f"{u:04X}" for u in units) + "}"
        out: List[str] = []
        j = 0
        while j < len(units):
            code = units[j]
            if code == END:
                break
            if code == ESC:
                ctl = units[j + 1]
                nargs = units[j + 2]
                args = units[j + 3:j + 3 + nargs]
                j += 3 + nargs
                if (ctl & 0xFF00) in self.strvar:
                    name = f"STRVAR_{ctl >> 8:02X}"
                    head = f"{name} {ctl & 0xFF}"
                    rest = ",".join(str(a) for a in args)
                    out.append("{" + head + ("," + rest if rest else "") + "}")
                    continue
                name = self.cmds.get(ctl)
                if name is None:
                    raise BankError(f"unknown control code {ctl:04X}")
                rest = ",".join(str(a) for a in args)
                out.append("{" + name + (" " + rest if rest else "") + "}")
                continue
            text = self.chars.get(code)
            if text is None:
                raise BankError(f"character {code:04X} not in charmap")
            out.append(text)
            j += 1
        return "".join(out)

    _TAG = re.compile(r"\{([^{}]*)\}")

    def encode_line(self, text: str) -> List[int]:
        if text.startswith("{RAW ") and text.endswith("}"):
            return [int(x, 16) for x in text[5:-1].split()]
        units: List[int] = []
        pos = 0
        while pos < len(text):
            if text[pos] == "{":
                m = self._TAG.match(text, pos)
                if not m:
                    raise ValueError("unclosed tag")
                body = m.group(1)
                name, _, rest = body.partition(" ")
                if name.startswith("STRVAR_"):
                    parts = rest.split(",") if rest else []
                    low = int(parts[0]) if parts else 0
                    args = [int(x) for x in parts[1:] if x.strip()]
                    ctl = (int(name[7:], 16) << 8) | low
                else:
                    if name not in self.cmd_codes:
                        raise ValueError(f"unknown tag {{{name}}}")
                    ctl = self.cmd_codes[name]
                    args = [int(x) for x in rest.replace(",", " ").split()] if rest else []
                units += [ESC, ctl, len(args)] + args
                pos = m.end()
                continue
            # longest charmap text first (some codes are multi-character, such as the literal "\x0000")
            for length in (6, 5, 4, 3, 2, 1):
                chunk = text[pos:pos + length]
                if chunk in self.char_codes:
                    units.append(self.char_codes[chunk])
                    pos += length
                    break
            else:
                raise ValueError(f"no charmap code for {text[pos]!r}")
        units.append(END)
        return units


def decode_all(bank: Bank, codec: Codec) -> List[str]:
    return [codec.decode_line(units) for units in bank.lines]


def encode_all(texts: List[str], codec: Codec, base: Optional[Bank] = None) -> Bank:
    """A bank from ``texts``. A text equal to the decoded base line keeps the base's raw units."""
    key = base.key if base is not None else 0
    lines = []
    for n, text in enumerate(texts):
        if base is not None and n < len(base.lines) and codec.decode_line(base.lines[n]) == text:
            lines.append(list(base.lines[n]))
        else:
            lines.append(codec.encode_line(text))
    return Bank(key=key, lines=lines)


def open_bank(data: bytes, codecs: List["Codec"]) -> Tuple["Codec", Bank]:
    """The first codec that decodes every line of ``data`` (the charmaps agree wherever they all decode)."""
    bank = decode_bank(data)
    for codec in codecs:
        try:
            for units in bank.lines:
                codec.decode_line(units)
        except BankError:
            continue
        return codec, bank
    raise BankError("no charmap decodes this bank")
