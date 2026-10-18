"""Text of Rock N' Roll Racing (SNES, USA ROM): the one text table, a codec and the patched ROM.

The table runs from ``TEXT_START`` to ``TEXT_END``: 223 strings, each ending with a 0x00 byte. A 0x0D byte is a line
break inside a string. The game keeps a pointer table in front of the table, so every string keeps its ROM length
(its *budget*): a translation fills at most the budget and the rest is spaces. Nothing moves, no pointer changes.

Codec: printable ASCII is itself, 0x0D is a new line, every other byte (and a literal ``[``) is a tag ``[XX]`` with its
hex value. A string without any tag and with the same length as its budget round-trips to its own bytes.
"""
import re
from typing import Any, Dict, List, Tuple

TEXT_FORMAT = "rrr-text-1"
TEXT_START = 0xE180
TEXT_END = 0xF454            # the last terminator is at 0xF453
ROM_SIZE = 1 << 20
HEADER = 0x7FC0              # LoROM internal header
TITLE = b"ROCK N' ROLL RACING  "
REGION_OFFSET = 0x7FD9
REGION_USA = 0x01
CHECKSUM_OFFSET = 0x7FDC     # complement, then checksum (little endian)
PAD = 0x20
NEW_LINE = 0x0D
TERMINATOR = 0x00

# Blocks of the editor: first string offset of each block, and its name (the strings are in ROM order).
GROUPS = ((TEXT_START, "Race, menus and garage"), (0xEE9E, "Story and intro"), (0xF052, "Credits"))

_TAG = re.compile(r"\[([0-9A-F]{2})\]")


class EncodeError(ValueError):
    def __init__(self, message: str, char: str = ""):
        super().__init__(message)
        self.char = char


def is_usa_rom(data: bytes) -> bool:
    return (len(data) == ROM_SIZE and data[HEADER:HEADER + len(TITLE)] == TITLE
            and data[REGION_OFFSET] == REGION_USA)


def string_slots(data: bytes) -> List[Tuple[int, int]]:
    """(offset, budget) of every string of the table: budget is the number of bytes before its terminator."""
    slots, start = [], TEXT_START
    for offset in range(TEXT_START, TEXT_END):
        if data[offset] == TERMINATOR:
            slots.append((start, offset - start))
            start = offset + 1
    if start != TEXT_END:
        raise ValueError(f"text table does not end at 0x{TEXT_END:X}")
    return slots


def decode(raw: bytes) -> str:
    out = []
    for byte in raw:
        if byte == NEW_LINE:
            out.append("\n")
        elif 0x20 <= byte <= 0x7E and byte != 0x5B:
            out.append(chr(byte))
        else:
            out.append(f"[{byte:02X}]")
    return "".join(out)


def encode(text: str) -> bytes:
    out, i = bytearray(), 0
    while i < len(text):
        char = text[i]
        if char == "\n":
            out.append(NEW_LINE)
        elif char == "[":
            tag = _TAG.match(text, i)
            if tag is None:
                raise EncodeError(f"tag at {i} is not [XX]", char)
            value = int(tag.group(1), 16)
            if value == TERMINATOR:
                raise EncodeError("[00] would end the string", char)
            out.append(value)
            i = tag.end()
            continue
        elif 0x20 <= ord(char) <= 0x7E:
            out.append(ord(char))
        else:
            raise EncodeError(f"character {char!r} has no code in the game's font", char)
        i += 1
    return bytes(out)


def extract(data: bytes) -> Dict[str, Any]:
    """The text bank of a ROM: blocks of strings, each with its offset, budget and ROM bytes (hex)."""
    slots = string_slots(data)
    blocks: List[Dict[str, Any]] = []
    for group_index, (group_start, name) in enumerate(GROUPS):
        strings = []
        for offset, budget in slots:
            if offset < group_start or (group_index + 1 < len(GROUPS) and offset >= GROUPS[group_index + 1][0]):
                continue
            strings.append({"id": f"{offset:04X}", "offset": offset, "budget": budget,
                            "raw": data[offset:offset + budget].hex()})
        blocks.append({"id": f"text{group_index + 1}", "name": name, "strings": strings})
    return {"format": TEXT_FORMAT, "blocks": blocks}


def strings_of(bank: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [string for block in bank.get("blocks") or [] for string in block.get("strings") or []]


def build(data: bytes, bank: Dict[str, Any]) -> bytes:
    """The ROM with each string written in place (padded with spaces to its budget) and a fixed checksum."""
    if len(data) != ROM_SIZE:
        raise ValueError("not a 1 MB Rock N' Roll Racing ROM")
    rom = bytearray(data)
    for string in strings_of(bank):
        offset, budget = int(string["offset"]), int(string["budget"])
        raw = bytes.fromhex(string["raw"])
        if TERMINATOR in raw:
            raise ValueError(f"string 0x{offset:04X} contains a 00 byte")
        if len(raw) > budget:
            raise ValueError(f"string 0x{offset:04X} is {len(raw)} bytes; the room is {budget}")
        rom[offset:offset + budget] = raw + bytes([PAD]) * (budget - len(raw))
    fix_checksum(rom)
    return bytes(rom)


def _field_sum(checksum: int) -> int:
    """Byte sum of the complement and checksum fields that hold ``checksum``."""
    complement = checksum ^ 0xFFFF
    return (complement & 0xFF) + (complement >> 8) + (checksum & 0xFF) + (checksum >> 8)


def fix_checksum(rom: bytearray) -> None:
    """Set the header complement and checksum so that the byte sum of the whole ROM equals the checksum.

    The fields keep their values when those already fit (an unchanged ROM stays unchanged); otherwise the first
    checksum that fits is written. Tool-made ROMs fit: the original USA ROM has checksum 0x5F55 and complement 0xA0AA.
    """
    base = (sum(rom) - sum(rom[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4])) & 0xFFFF
    current = int.from_bytes(rom[CHECKSUM_OFFSET + 2:CHECKSUM_OFFSET + 4], "little")
    if (base + _field_sum(current)) & 0xFFFF == current:
        return
    for checksum in range(0x10000):
        if (base + _field_sum(checksum)) & 0xFFFF == checksum:
            complement = checksum ^ 0xFFFF
            rom[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 4] = (complement | (checksum << 16)).to_bytes(4, "little")
            return
    raise ValueError("no checksum fits the header fields")


def create_ips(original: bytes, patched: bytes) -> bytes:
    """An IPS patch that turns ``original`` into ``patched`` (same size, changed runs as records)."""
    if len(original) != len(patched):
        raise ValueError("IPS needs two images of one size")
    out = bytearray(b"PATCH")
    i, size = 0, len(patched)
    while i < size:
        if original[i] == patched[i]:
            i += 1
            continue
        j = i
        while j < size and original[j] != patched[j] and j - i < 0xFFFF:
            j += 1
        if i == 0x454F46:
            raise ValueError("IPS offset 0x454F46 is the end marker")
        out += i.to_bytes(3, "big") + (j - i).to_bytes(2, "big") + patched[i:j]
        i = j
    out += b"EOF"
    return bytes(out)
