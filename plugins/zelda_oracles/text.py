"""Oracle of Ages and Oracle of Seasons text: index tables, string spans and a plain encoder.

Layout (USA ROMs; facts from the public disassembly's text/info.txt and tools/dump/dumpText.py):

- 0x64 high indices. Each high index holds a 16-bit offset to a group table, relative to the text
  index table. A group table holds 16-bit offsets to strings.
- A string address = text base + group entry. Base 1 serves high indices below
  ``text_base2_index_start``; base 2 serves the rest.
- Text index = (high index << 8) | group entry. Indices below 0x400 are dictionary strings:
  bytes 0x02-0x05 followed by one byte refer to dictionary index ((b - 2) << 8) | next byte.
- A string ends with 0x00. Some strings have no terminator and run into the next string.
- Bytes 0x06-0x0F take one operand byte.

Editing rule: a string is replaced in place. A replacement must end with 0x00 and fit inside the
old span, because the pointer tables hold start addresses only. Unchanged strings keep their
original bytes, so a ROM without edits rebuilds byte for byte.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .rom import GameLayout, read16, read_bank_pointer, read_reversed_bank_pointer

HIGH_INDEX_COUNT = 0x64
DICTIONARY_LIMIT = 0x400
TEXT_INDEX_BASE = 0x400


class TextError(ValueError):
    """A text edit that cannot be written into the ROM."""


@dataclass(frozen=True)
class TextSpan:
    """One string in the ROM: its index, where it starts and where its bytes end (exclusive)."""

    index: int
    start: int
    end: int
    terminated: bool

    @property
    def length(self) -> int:
        return self.end - self.start

    @property
    def is_dictionary(self) -> bool:
        return self.index < DICTIONARY_LIMIT

    @property
    def name(self) -> str:
        if self.is_dictionary:
            return f"DICT{self.index >> 8}_{self.index & 0xFF:02x}"
        return f"TX_{self.index - TEXT_INDEX_BASE:04x}"


class TextTables:
    """Reads every string span of one USA Oracle ROM. Pure functions over the ROM bytes."""

    def __init__(self, rom: bytes, layout: GameLayout, language: int = 0):
        self.rom = rom
        self.layout = layout
        self.language = language
        self._table = read_reversed_bank_pointer(rom, layout.language_table + 3 * language)
        self._base1 = read_bank_pointer(rom, layout.text_base1_table + 4 * language)
        self._base2 = read_bank_pointer(rom, layout.text_base2_table + 4 * language)
        self._base3 = None
        if layout.text_base3_table is not None:
            self._base3 = read_bank_pointer(rom, layout.text_base3_table + 4 * language)
        self._starts = self._collect_starts()
        self.spans: List[TextSpan] = self._walk()
        self.by_index: Dict[int, TextSpan] = {span.index: span for span in self.spans}
        self.by_start: Dict[int, TextSpan] = {span.start: span for span in self.spans}

    def _base_for(self, high: int) -> int:
        if self._base3 is not None and high >= self.layout.text_base3_index_start:
            return self._base3
        return self._base2 if high >= self.layout.text_base2_index_start else self._base1

    def _collect_starts(self) -> Dict[int, int]:
        """String start address -> text index, for every entry of every group table."""
        rom = self.rom
        groups: Dict[int, List[int]] = {}
        for high in range(HIGH_INDEX_COUNT):
            address = self._table + read16(rom, self._table + 2 * high)
            groups.setdefault(address, []).append(high)
        addresses = sorted(groups)
        starts: Dict[int, int] = {}
        for position, address in enumerate(addresses):
            if position + 1 < len(addresses):
                size = (addresses[position + 1] - address) // 2
            else:
                size = self.layout.last_group_size
            high = groups[address][0]
            base = self._base_for(high)
            for entry in range(size):
                start = base + read16(rom, address + 2 * entry)
                starts.setdefault(start, (high << 8) | entry)
        return starts

    def _scan_end(self, address: int) -> Tuple[int, bool]:
        """Find where the string at ``address`` ends. Same walk as the disassembly's dumper.

        A string without a terminator stops where the next string starts, so the flag is read from
        the last byte of the span instead of from the loop exit.
        """
        rom = self.rom
        starts = self._starts
        pos = address
        while rom[pos] != 0:
            c = rom[pos]
            pos += 1
            if (pos + 1) in starts:
                break
            if 2 <= c < 0x10:
                pos += 1
            if (pos + 1) in starts:
                break
        end = pos + 1
        return end, rom[end - 1] == 0

    def _walk(self) -> List[TextSpan]:
        if not self._starts:
            return []
        spans: List[TextSpan] = []
        address = min(self._starts)
        limit = max(self._starts) + 1
        while address < limit:
            end, terminated = self._scan_end(address)
            index = self._starts.get(address)
            if index is not None:
                spans.append(TextSpan(index=index, start=address, end=end, terminated=terminated))
            address = end
        return spans

    def span(self, index: int) -> TextSpan:
        try:
            return self.by_index[index]
        except KeyError:
            raise TextError(f"no string with index 0x{index:04x}") from None

    def is_isolated(self, span: TextSpan) -> bool:
        """True when no other string starts inside this span, so an in-place edit cannot hit it."""
        return not any(start in self._starts for start in range(span.start + 1, span.end))

    def raw(self, span: TextSpan) -> bytes:
        return bytes(self.rom[span.start:span.end])

    def expand(self, span: TextSpan) -> bytes:
        """The bytes the game shows: dictionary references replaced by their strings."""
        out = bytearray()
        self._expand_into(out, span.start, None, False)
        return bytes(out)

    def _expand_into(self, out: bytearray, address: int, end: Optional[int], dict_lookup: bool) -> None:
        rom = self.rom
        i = address
        limit = end if end is not None else 0x100000000
        while i < limit:
            b = rom[i]
            if 2 <= b < 6 and limit - i >= 2:
                dictionary = self.by_index.get(((b - 2) << 8) | rom[i + 1])
                if dictionary is None:
                    raise TextError(f"dictionary reference 0x{b:02x} 0x{rom[i + 1]:02x} at 0x{i:x} is unknown")
                self._expand_into(out, dictionary.start, None, True)
                i += 1
            elif 6 <= b < 0x10:
                out.append(b)
                out.append(rom[i + 1])
                i += 1
            else:
                if b == 0:
                    if not dict_lookup:
                        out.append(b)
                    break
                out.append(b)
            i += 1


# Markup: the editor shows bytes as text. Printable ASCII is plain. Known control codes get a tag;
# any other byte is written as \xNN, so every byte sequence survives a round trip.
# Opcode 0x0C takes a sub-command in its high bits and a 2-bit value in its low bits (as in the
# disassembly): 0 speed(c), 1 num1, 2 opt(), 3 stop, 4 pos(c), 5 heartpiece, 6 num2, 7 slow().
_CMD0C_NAMED = {1: "num1", 2: "opt()", 3: "stop", 5: "heartpiece", 6: "num2", 7: "slow()"}
# Single-byte symbols of the US font (disassembly text/info.txt names).
_SYMBOL_BYTES = {
    0x10: "\\circle", 0x11: "\\club", 0x12: "\\diamond", 0x13: "\\spade", 0x14: "\\heart",
    0x15: "\\up", 0x16: "\\down", 0x17: "\\left", 0x18: "\\right", 0x19: "\\times",
    0x7E: "\\triangle", 0x7F: "\\rectangle",
}
_SYMBOL_NAMES = {text: byte for byte, text in _SYMBOL_BYTES.items()}


def _tag_for_0c(operand: int) -> Optional[str]:
    sub, value = operand >> 3, operand & 3
    if sub == 0:
        return f"\\speed({value})"
    if sub == 4:
        return f"\\pos({value})"
    if value == 0 and sub in _CMD0C_NAMED:
        return "\\" + _CMD0C_NAMED[sub]
    return None


def text_name(index: int) -> str:
    """Name of a text index as the disassembly writes it: TX_xxxx, or DICTn_xx for dictionaries."""
    if index < DICTIONARY_LIMIT:
        return f"DICT{index >> 8}_{index & 0xFF:02x}"
    return f"TX_{index - TEXT_INDEX_BASE:04x}"


def to_markup(data: bytes, index: int = 0, special: Optional[Callable[[int], Optional[str]]] = None) -> str:
    """Render expanded game bytes as editor text (the inverse of ``from_markup``).

    ``index`` is the text index of the string; \\jump and \\call targets are written relative to it.
    ``special`` maps bytes from 0x80 up to a character for reference display only (never written back).
    """
    out: List[str] = []
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0:
            break
        operand = data[i + 1] if i + 1 < len(data) else None
        if b == 0x01:
            out.append("\n")
        elif b == 0x07 and operand is not None:
            out.append(f"\\jump({text_name((index & 0xFF00) | operand)})")
            i += 1
        elif b == 0x0F and operand is not None:
            out.append(f"\\call({text_name((index & 0xFF00) | operand)})" if operand < 0xFC
                       else f"\\call(0x{operand:02x})")
            i += 1
        elif b == 0xB8 and operand == 0xB9:
            out.append("\\abtn")
            i += 1
        elif b == 0xBA and operand == 0xBB:
            out.append("\\bbtn")
            i += 1
        elif b in _SYMBOL_BYTES:
            out.append(_SYMBOL_BYTES[b])
        elif b == 0x06 and operand is not None:
            kind = "item" if operand & 0x80 else "sym"
            out.append(f"\\{kind}(0x{operand & 0x7F:02x})")
            i += 1
        elif b == 0x09 and operand is not None:
            out.append(f"\\col({operand})" if operand < 0x80 else f"\\col(0x{operand:02x})")
            i += 1
        elif b == 0x0D and operand is not None:
            out.append(f"\\wait({operand})")
            i += 1
        elif b == 0x0A and operand in (0, 1, 2, 3):
            out.append("\\" + {0: "Link", 1: "Child", 2: "secret1", 3: "secret2"}[operand])
            i += 1
        elif b == 0x0C and operand is not None and _tag_for_0c(operand) is not None:
            out.append(_tag_for_0c(operand))
            i += 1
        elif 0x20 <= b < 0x7F and chr(b) != "\\":
            out.append(chr(b))
        elif b >= 0x80 and special is not None and special(b) is not None:
            out.append(special(b))
        else:
            out.append(f"\\x{b:02x}")
        i += 1
    return "".join(out)


_TAG_RE = re.compile(
    r"\\(?:"
    r"(col|wait|speed|pos|item|sym|jump|call)\((0x[0-9a-fA-F]+|\d+|TX_[0-9a-fA-F]+|DICT\d_[0-9a-fA-F]{2})\)"
    r"|(opt\(\)|stop|num1|num2|heartpiece|slow\(\))"
    r"|(Link|Child|secret1|secret2)"
    r"|(abtn|bbtn|circle|club|diamond|spade|heart|up|down|left|right|times|triangle|rectangle)"
    r"|x([0-9a-fA-F]{2})"
    r")"
)
_NAMED_TWO_BYTE = {"abtn": b"\xB8\xB9", "bbtn": b"\xBA\xBB"}
TAG_PATTERN = _TAG_RE.pattern  # the control codes of the markup, for the editor's tag manager
_SIMPLE_0C = {"opt()": 2, "stop": 3, "num1": 1, "num2": 6, "heartpiece": 5, "slow()": 7}
_SIMPLE_0A = {"Link": 0, "Child": 1, "secret1": 2, "secret2": 3}


def _target_low_byte(name: str, index: int) -> int:
    """Low byte of a \\jump or \\call target. The target must share the string's index group."""
    if name.startswith("TX_"):
        target = int(name[3:], 16) + TEXT_INDEX_BASE
    elif name.startswith("DICT"):
        target = (int(name[4], 16) << 8) | int(name[6:], 16)
    else:
        return _number(name, 0xFF)
    if (target & 0xFF00) != (index & 0xFF00):
        raise TextError(f"{name} is in another group than this string")
    return target & 0xFF


def from_markup(text: str, index: int = 0, letters: Optional[Dict[str, int]] = None) -> bytes:
    """Encode editor text to game bytes, terminated by 0x00. ``index`` is the string's text index.

    ``letters`` maps the extra characters (Ukrainian letters) to their font cell codes.
    """
    out = bytearray()
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            out.append(0x01)
            i += 1
            continue
        if letters and ch in letters:
            out.append(letters[ch])
            i += 1
            continue
        if ch == "\\":
            match = _TAG_RE.match(text, i)
            if match is None:
                raise TextError(f"unknown tag at {i}: {text[i:i + 12]!r}")
            kind, number, simple, named, symbol, hexcode = match.groups()
            if kind == "jump":
                out += bytes((0x07, _target_low_byte(number, index)))
            elif kind == "call":
                out += bytes((0x0F, _target_low_byte(number, index)))
            elif kind == "col":
                out += bytes((0x09, _number(number, 0xFF)))
            elif kind == "wait":
                out += bytes((0x0D, _number(number, 0xFF)))
            elif kind == "speed":
                out += bytes((0x0C, _number(number, 3)))
            elif kind == "pos":
                out += bytes((0x0C, (4 << 3) | _number(number, 3)))
            elif kind == "item":
                out += bytes((0x06, 0x80 | _number(number, 0x7F)))
            elif kind == "sym":
                out += bytes((0x06, _number(number, 0x7F)))
            elif simple is not None:
                out += bytes((0x0C, _SIMPLE_0C[simple] << 3))
            elif named is not None:
                out += bytes((0x0A, _SIMPLE_0A[named]))
            elif symbol is not None:
                out += _NAMED_TWO_BYTE.get(symbol) or bytes((_SYMBOL_NAMES["\\" + symbol],))
            else:
                out.append(int(hexcode, 16))
            i = match.end()
            continue
        code = ord(ch)
        if not (0x20 <= code < 0x7F):
            raise TextError(f"character {ch!r} is not in the Oracles font")
        out.append(code)
        i += 1
    out.append(0x00)
    return bytes(out)


def _number(text: str, limit: int) -> int:
    value = int(text, 16) if text.lower().startswith("0x") else int(text)
    if not 0 <= value <= limit:
        raise TextError(f"number {value} out of range")
    return value


def replace_text(rom: bytearray, span: TextSpan, new_bytes: bytes) -> None:
    """Write ``new_bytes`` (which ends with 0x00) over ``span`` in place.

    Bytes after the new terminator keep their old values, so the diff against the clean ROM shows
    only the changed string.
    """
    if not span.terminated:
        raise TextError(f"{span.name} has no terminator and cannot be edited in place")
    if not new_bytes or new_bytes[-1] != 0:
        raise TextError("replacement must end with 0x00")
    if len(new_bytes) > span.length:
        raise TextError(f"{span.name} needs {len(new_bytes)} bytes, the old string has {span.length}")
    rom[span.start:span.start + len(new_bytes)] = new_bytes
