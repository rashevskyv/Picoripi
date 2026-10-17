"""Game text of Pokemon Red, Blue and Yellow as pret text macros, read from the ROM and written back.

A text body is the bytes of one label. ``decode`` turns them into macro lines (``text "..."``, ``line "..."``,
``done``, ``text_ram wStringBuffer``...). ``encode`` turns macro lines into bytes. ``encode(decode(b)) == b``.
RAM names, banked labels and the charmap come from the facts file of the ROM (``rom_facts/``).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

from core.i18n import tr
from plugins.pokemon_gen1.asm_text import escape, split_comment, unescape

Line = Tuple[str, str]        # (keyword, arguments as written in the asm)

FLOW_CODE = {"text": 0x00, "next": 0x4E, "line": 0x4F, "para": 0x51, "cont": 0x55, "page": 0x49}
FLOW_BY_CODE = {code: word for word, code in FLOW_CODE.items()}
TERMINATOR = {"done": b"\x57", "prompt": b"\x58", "text_end": b"\x50", "dex": b"\x5f\x50"}
TERMINATOR_BY_CODE = {0x57: "done", 0x58: "prompt"}
TEXT_ASM = 0x08
TX_END = 0x50
TX_FAR = 0x17
TX_DEXEND = 0x5F

# code -> (macro, argument kind). Kinds: "" none, "ram" RAM address (2 bytes), "n" one byte decimal,
# "dn" one byte of two digits, "far" address and bank (3 bytes), "ram_n", "ram_nn", "ram_dn" a RAM address and
# the rest. Values are the TX_* codes of pret's text macros.
COMMANDS: Dict[int, Tuple[str, str]] = {
    0x00: ("text_start", ""),
    0x01: ("text_ram", "ram"),
    0x02: ("text_bcd", "ram_f"),
    0x03: ("text_move", "ram"),
    0x04: ("text_box", "ram_nn"),
    0x05: ("text_low", ""),
    0x06: ("text_promptbutton", ""),
    0x07: ("text_scroll", ""),
    0x09: ("text_decimal", "ram_dn"),
    0x0A: ("text_pause", ""),
    0x0B: ("sound_get_item_1", ""),
    0x0C: ("text_dots", "n"),
    0x0D: ("text_waitbutton", ""),
    0x0E: ("sound_pokedex_rating", ""),
    0x0F: ("sound_get_item_1_duplicate", ""),
    0x10: ("sound_get_item_2", ""),
    0x11: ("sound_get_key_item", ""),
    0x12: ("sound_caught_mon", ""),
    0x13: ("sound_dex_page_added", ""),
    0x14: ("sound_cry_nidorina", ""),
    0x15: ("sound_cry_pidgeot", ""),
    0x16: ("sound_cry_dewgong", ""),
    TX_FAR: ("text_far", "far"),
}
COMMAND_BY_NAME = {name: code for code, (name, _kind) in COMMANDS.items()}
# Generation II (Gold, Silver, Crystal): the same macros with other codes; TX_FAR is 0x16 and the sounds differ.
GEN2_TX_FAR = 0x16
GEN2_COMMANDS: Dict[int, Tuple[str, str]] = {
    0x00: ("text_start", ""),
    0x01: ("text_ram", "ram"),
    0x02: ("text_bcd", "ram_f"),
    0x03: ("text_move", "ram"),
    0x04: ("text_box", "ram_nn"),
    0x05: ("text_low", ""),
    0x06: ("text_promptbutton", ""),
    0x07: ("text_scroll", ""),
    0x09: ("text_decimal", "ram_dn"),
    0x0A: ("text_pause", ""),
    0x0B: ("sound_dex_fanfare_50_79", ""),
    0x0C: ("text_dots", "n"),
    0x0D: ("text_waitbutton", ""),
    0x0E: ("sound_dex_fanfare_20_49", ""),
    0x0F: ("sound_item", ""),
    0x10: ("sound_caught_mon", ""),
    0x11: ("sound_dex_fanfare_80_109", ""),
    0x12: ("sound_fanfare", ""),
    0x13: ("sound_slot_machine_start", ""),
    0x14: ("text_buffer", "n"),
    0x15: ("text_today", ""),
    GEN2_TX_FAR: ("text_far", "far"),
}
GEN2_COMMAND_BY_NAME = {name: code for code, (name, _kind) in GEN2_COMMANDS.items()}
_ARG_KINDS = {"ram_f": ["ram", "f"], "ram_nn": ["ram", "n", "n"], "ram_dn": ["ram", "dn"]}
# Flags of text_bcd (constants/text_constants.asm): a count and any of these, joined with "|".
FLAGS = {"LEADING_ZEROES": 0x80, "LEFT_ALIGN": 0x40, "MONEY_SIGN": 0x20}
_LABEL = re.compile(r"([A-Za-z_.][\w.]*)::?\s*$")
_INLINE_LABEL = re.compile(r"([A-Za-z_.][\w.]*)::?\s+(\S.*)$")
_LITERAL = re.compile(r'^"(.*)"$', re.S)
_RAW_CELL = re.compile(r"<\$([0-9A-Fa-f]{2})>")


class CodecError(ValueError):
    """Text the codec cannot turn into bytes (an unknown macro, a character with no cell, a bad argument)."""


class Names:
    """What the codec needs from the facts: the charmap, RAM names and banked labels (name <-> bank, CPU address)."""

    def __init__(self, charmap: Sequence[Sequence[object]], ram: Dict[str, int],
                 far: Dict[str, Sequence[int]], gen2: bool = False) -> None:
        self.commands = GEN2_COMMANDS if gen2 else COMMANDS
        self.command_by_name = GEN2_COMMAND_BY_NAME if gen2 else COMMAND_BY_NAME
        self.tx_far = GEN2_TX_FAR if gen2 else TX_FAR
        self.byte_of: Dict[str, int] = {}
        self.char_of: Dict[int, str] = {}
        for token, code in charmap:
            self.byte_of.setdefault(str(token), int(code))
            self.char_of.setdefault(int(code), str(token))
        self.tokens = sorted((t for t in self.byte_of if t), key=len, reverse=True)
        self.ram = {name: int(addr) for name, addr in ram.items()}
        self.ram_name = {}
        for name, addr in self.ram.items():
            self.ram_name.setdefault(addr, name)
        self.far = {name: (int(bank), int(cpu)) for name, (bank, cpu) in far.items()}
        self.far_name = {}
        for name, place in self.far.items():
            self.far_name.setdefault(place, name)


# ----- ROM bytes -> macro lines -----

def _show_byte(names: Names, code: int) -> str:
    return names.char_of.get(code, f"<${code:02X}>")


def _number(value: str) -> int:
    """A number as the asm writes it: decimal, ``$hex``, or flags joined with ``|``."""
    total = 0
    for term in value.split("|"):
        term = term.strip()
        if term in FLAGS:
            total |= FLAGS[term]
        else:
            total |= int(term[1:], 16) if term.startswith("$") else int(term, 0)
    return total


def _flags_text(value: int) -> str:
    parts = [str(value & 0x1F)]
    parts += [name for name, bit in FLAGS.items() if value & bit]
    return " | ".join(parts)


def _ram_text(names: Names, addr: int) -> str:
    return names.ram_name.get(addr, f"${addr:04X}")


def _far_text(names: Names, bank: int, cpu: int) -> str:
    return names.far_name.get((bank, cpu), f"${bank:02X}:${cpu:04X}")


def _args(names: Names, kind: str, data: bytes, at: int, hexed: bool = False,
          ram_name: Optional[str] = None) -> Tuple[str, int]:
    """The asm arguments of a command at ``at`` (the byte after the command code) and their size in bytes."""
    kinds = _ARG_KINDS.get(kind, [kind] if kind else [])
    parts: List[str] = []
    size = 0
    for item in kinds:
        if item == "ram":
            addr = data[at + size] | data[at + size + 1] << 8
            parts.append(ram_name if ram_name is not None else _ram_text(names, addr))
            size += 2
        elif item == "far":
            cpu = data[at + size] | data[at + size + 1] << 8
            parts.append(_far_text(names, data[at + size + 2], cpu))
            size += 3
        elif item == "dn":
            value = data[at + size]
            parts.append(f"{value >> 4}, {value & 0x0F}")
            size += 1
        elif item == "f":
            value = data[at + size]
            parts.append(f"${value:02x}" if hexed else _flags_text(value))
            size += 1
        else:
            parts.append(str(data[at + size]))
            size += 1
    return ", ".join(parts), size


def decode(region: bytes, names: Names, bcd_hex: Sequence[int] = (), ram_args: Sequence[str] = (),
           end_char: bool = False) -> List[Line]:
    """The macro lines of a text body. Stops at ``text_asm`` (the bytes after it are code, not text).

    ``bcd_hex`` lists the text_bcd commands (counted from 0 in the body) whose flags the decompilation wrote as a
    hex literal; the others are written as ``3 | LEADING_ZEROES``. The bytes do not tell which form was used.
    """
    out: List[Line] = []
    word: Optional[str] = None
    chars: List[str] = []
    bcd_seen = 0
    ram_seen = 0

    def flush() -> None:
        nonlocal word
        if word is None and not chars:
            return
        out.append((word or "db", '"' + escape("".join(chars)) + '"'))
        word = None
        chars.clear()

    # A 0x50 byte is the text_end terminator only as the last byte of the body; inside the text it is the "@"
    # character (the game's line "an @" is followed by a text_ram command, not by an end).
    end = len(region) - 1 if region[-1:] == bytes([TEXT_ASM]) else len(region)
    at = 0
    while at < end:
        code = region[at]
        follow = region[at + 1] if at + 1 < end else None
        if code == 0x00 and (follow is None or follow in FLOW_BY_CODE or follow in TERMINATOR_BY_CODE
                             or (follow in names.commands and follow != 0x00)):
            flush()
            out.append(("text_start", ""))
            at += 1
        elif code in FLOW_BY_CODE:
            flush()
            word = FLOW_BY_CODE[code]
            at += 1
        elif code in TERMINATOR_BY_CODE:
            flush()
            out.append((TERMINATOR_BY_CODE[code], ""))
            at += 1
        elif code == TX_END and at == end - 1 and not end_char:
            flush()
            out.append(("text_end", ""))
            at += 1
        elif code == TX_DEXEND and at + 2 == end and region[at + 1] == TX_END:
            flush()
            out.append(("dex", ""))
            at += 2
        elif code == TX_END and word is None and at < end - 1:
            # In a db body each "@" ends one string: ``db "CUT@"`` then ``db "FLY@"`` (a menu's list of names).
            chars.append("@")
            flush()
            at += 1
        elif code == TEXT_ASM:
            flush()
            out.append(("text_asm", ""))
            break
        elif code in names.commands and code not in (0x00,):
            flush()
            name, kind = names.commands[code]
            hexed = False
            if code == 0x02:
                hexed = bcd_seen in bcd_hex
                bcd_seen += 1
            ram_name = None
            if "ram" in kind:
                ram_name = ram_args[ram_seen] if ram_seen < len(ram_args) else None
                ram_seen += 1
            args, size = _args(names, kind, region, at + 1, hexed, ram_name)
            out.append((name, args))
            at += 1 + size
        else:
            chars.append(_show_byte(names, code))
            at += 1
    flush()
    if end < len(region):
        out.append(("text_asm", ""))
    return out


# ----- macro lines -> ROM bytes -----

def _string_bytes(names: Names, literal: str) -> bytes:
    match = _LITERAL.match(literal.strip())
    if match is None:
        raise CodecError(tr("A string literal is expected, got {0}.", literal))
    text = unescape(match.group(1))
    out = bytearray()
    at = 0
    while at < len(text):
        raw = _RAW_CELL.match(text, at)
        if raw is not None:
            out.append(int(raw.group(1), 16))
            at = raw.end()
            continue
        for token in names.tokens:
            if text.startswith(token, at):
                out.append(names.byte_of[token])
                at += len(token)
                break
        else:
            char = text[at]
            if char not in names.byte_of:
                raise CodecError(tr("No cell for {0} in this game's charmap.", repr(char)))
            out.append(names.byte_of[char])
            at += 1
    return bytes(out)


def _ram_addr(names: Names, value: str) -> int:
    if value in names.ram:
        return names.ram[value]
    if value.startswith("$"):
        return int(value[1:], 16)
    raise CodecError(tr("Unknown RAM name {0}.", value))


def _db_bytes(names: Names, args: str) -> bytes:
    """The bytes of a ``db`` line: strings and numbers in turn (``db -6, "NAME@"``, ``db $76, "BADGES"``)."""
    out = bytearray()
    rest = args.strip()
    while rest:
        if rest.startswith('"'):
            end = rest.find('"', 1)
            if end < 0:
                raise CodecError(tr("A string literal is expected, got {0}.", args))
            out += _string_bytes(names, rest[:end + 1])
            rest = rest[end + 1:]
        else:
            item, comma, after = rest.partition(",")
            try:
                value = int(item.strip()[1:], 16) if item.strip().startswith("$") else int(item.strip(), 0)
            except ValueError:
                raise CodecError(tr("A string literal is expected, got {0}.", args))
            out.append(value & 0xFF)
            rest = comma + after          # the comma stays for the separator check below
        rest = rest.lstrip()
        if rest:
            if not rest.startswith(","):
                raise CodecError(tr("A string literal is expected, got {0}.", args))
            rest = rest[1:].lstrip()
    return bytes(out)


def _far_bytes(names: Names, value: str) -> bytes:
    if value in names.far:
        bank, cpu = names.far[value]
    elif re.fullmatch(r"\$[0-9A-Fa-f]{2}:\$[0-9A-Fa-f]{4}", value.strip()):
        bank_text, cpu_text = value.strip().split(":")
        bank, cpu = int(bank_text[1:], 16), int(cpu_text[1:], 16)
    else:
        raise CodecError(tr("Unknown label {0} for text_far.", value))
    return bytes([cpu & 0xFF, cpu >> 8, bank])


def _command_bytes(names: Names, name: str, args: str) -> bytes:
    code = names.command_by_name[name]
    kind = names.commands[code][1]
    if not kind:
        return bytes([code])
    values = [part.strip() for part in args.split(",")] if args.strip() else []
    kinds = _ARG_KINDS.get(kind, [kind])
    if len(values) != sum(2 if item == "dn" else 1 for item in kinds):
        raise CodecError(tr("{0} takes the wrong number of arguments.", name))
    out = bytearray([code])
    at = 0
    for item in kinds:
        value = values[at]
        at += 1
        if item == "ram":
            addr = _ram_addr(names, value)
            out += bytes([addr & 0xFF, addr >> 8])
        elif item == "far":
            out += _far_bytes(names, value)
        elif item == "dn":
            out.append((_number(value) << 4) | _number(values[at]))
            at += 1
        else:
            out.append(_number(value) & 0xFF)
    return bytes(out)


def encode(lines: Sequence[Line], names: Names, width: int = 0) -> bytes:
    """The bytes of a text body from its macro lines. Lines after ``text_asm`` are code and are not encoded.

    ``width`` is the field width of a ``dname`` table (the table_width of the decompilation); a ``dname`` that does
    not fit the field raises, as pret's own assert does. ``li`` entries are "@"-terminated and any length.
    """
    out = bytearray()
    for word, args in lines:
        if word == "dname":
            if not width:
                raise CodecError(tr("A fixed-width name needs the width of its table."))
            data = _string_bytes(names, args)
            if len(data) > width:
                raise CodecError(tr("Name longer than {0} characters: {1}", str(width), args))
            out += data + bytes([TX_END]) * (width - len(data))
        elif word == "li":
            out += _string_bytes(names, args) + bytes([TX_END])
        elif word in ("table_width", "list_start", "vc_patch", "vc_patch_end") or word.startswith("assert"):
            continue
        elif word in FLOW_CODE:
            out.append(FLOW_CODE[word])
            out += _string_bytes(names, args) if args.strip() else b""
        elif word == "db":
            out += _db_bytes(names, args)
        elif word in TERMINATOR:
            out += TERMINATOR[word]
        elif word == "text_asm":
            out.append(TEXT_ASM)
            break
        elif word in names.command_by_name:
            out += _command_bytes(names, word, args)
        else:
            raise CodecError(tr("Unknown text macro {0}.", word))
    return bytes(out)


def decode_names(region: bytes, names: Names, mode: str, width: int = 0) -> List[Line]:
    """The lines of a name table: ``dname`` fields of ``width`` bytes, or ``li`` entries ending at "@"."""
    def quoted(chunk: bytes) -> str:
        return '"' + escape("".join(_show_byte(names, code) for code in chunk)) + '"'

    out: List[Line] = []
    if mode == "dname":
        for start in range(0, len(region), width):
            chunk = region[start:start + width]
            out.append(("dname", quoted(chunk.split(bytes([TX_END]))[0])))
        return out
    at = 0
    while at < len(region):
        end = region.find(bytes([TX_END]), at)
        end = len(region) if end < 0 else end
        out.append(("li", quoted(region[at:end])))
        at = end + 1
    return out


# ----- asm files -----

def read_labels(source: str) -> List[Tuple[str, List[Line]]]:
    """``[(label, lines)]`` of an asm file of text. Lines before the first label get the label ``""``."""
    groups: List[Tuple[str, List[Line]]] = []
    for raw in source.splitlines():
        code = split_comment(raw)[0]
        stripped = code.strip()
        if not stripped:
            continue
        if not code[0].isspace():
            label = _LABEL.match(stripped)
            if label:
                groups.append((label.group(1), []))
                continue
            inline = _INLINE_LABEL.match(stripped)     # ``name: db "..."``: the label starts the body
            if inline:
                groups.append((inline.group(1), []))
                stripped = inline.group(2).strip()
        if not groups:
            groups.append(("", []))
        word, _, args = stripped.partition(" ")
        groups[-1][1].append((word, args.strip()))
    return groups


def format_body(label: str, lines: Sequence[Line]) -> str:
    """The asm text of one body: its label at column 0 and its macro lines indented."""
    out = [f"{label}::"]
    for word, args in lines:
        out.append(f"\t{word} {args}".rstrip())
    return "\n".join(out) + "\n"
