"""Guardian Heroes (Xbox 360, 2011) script files ``media/script_<lang>.mrg``: read the text and write it back.

File layout (all numbers big-endian):
- 0x00: u32 entry count, then zero padding up to 0x20;
- 0x20: one 32-byte record per entry: ``u32 offset, u32 size``, the other 24 bytes are zero (kept as they are);
- the entries follow, each starting on a 4-byte boundary (zero padding between them).

One entry is one scene: ``u32 N``, ``N`` u32 offsets of the strings (from the entry start), then the strings. A string
is a run of UTF-16BE code units that ends with 0xFFFF; it ends where the next offset starts (the last one at the
entry's end). Besides text a string holds control words. Words from 0xE000 up are codes, not letters:
- 0xE000, 0xE100, 0xE200 are followed by one parameter word (a speaker or window id);
- 0xF0xx..0xF6xx carry a value in the low byte (an expression and a pause, for example 0xF078);
- 0xF700 is a line break, 0xF800 a page break, 0xF900 starts a line of text;
- 0xFF0C is the comma the game's font draws (the plain comma 0x002C never occurs in text).

Editor text: the words as characters, ``\\n`` for 0xF700, ``,`` for 0xFF0C, and ``{XXXX}`` (four hex digits) for any
other control word; a code with a parameter is ``{E100:0039}``. The closing 0xFFFF is implied. The conversion is
lossless: ``encode(decode(words)) == words`` for every string of the game (a word that has no text form, such as a plain
comma or a bracket, is written as a ``{XXXX}`` tag too).
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import List, Sequence

END = 0xFFFF
NEWLINE = 0xF700
COMMA = 0xFF0C
PARAMETER_CODES = (0xE000, 0xE100, 0xE200)
HEADER_SIZE = 0x20
RECORD_SIZE = 32
ALIGN = 4
_TAG = re.compile(r"\{([0-9A-Fa-f]{4})(?::([0-9A-Fa-f]{4}))?\}")


class ScriptError(ValueError):
    """The bytes are not a script file this plugin reads, or a text cannot be written."""


def decode(words: Sequence[int]) -> str:
    """The editor text of one string (the closing 0xFFFF is dropped)."""
    if not words or words[-1] != END:
        raise ScriptError("a string does not end with 0xFFFF")
    out: List[str] = []
    body = words[:-1]
    i = 0
    while i < len(body):
        word = body[i]
        i += 1
        if word in PARAMETER_CODES and i < len(body):
            out.append("{%04X:%04X}" % (word, body[i]))
            i += 1
        elif word == NEWLINE:
            out.append("\n")
        elif word == COMMA:
            out.append(",")
        elif 0x20 <= word < 0xD800 and chr(word) not in "{},":
            out.append(chr(word))
        else:
            out.append("{%04X}" % word)
    return "".join(out)


def encode(text: str) -> List[int]:
    """The code units of one editor text, with the closing 0xFFFF."""
    words: List[int] = []
    pos = 0
    text = text.replace("\r", "")
    while pos < len(text):
        tag = _TAG.match(text, pos)
        if tag:
            words.append(int(tag.group(1), 16))
            if tag.group(2):
                words.append(int(tag.group(2), 16))
            pos = tag.end()
            continue
        char = text[pos]
        pos += 1
        if char == "\n":
            words.append(NEWLINE)
        elif char == ",":
            words.append(COMMA)
        elif char in "{}":
            raise ScriptError("a bracket that is not a {XXXX} tag: " + text[max(0, pos - 12):pos + 12])
        elif 0x20 <= ord(char) < 0xD800:
            words.append(ord(char))
        else:
            raise ScriptError("the character %r cannot be written (UTF-16 code unit above 0xD7FF)" % char)
    words.append(END)
    return words


def _pack(words: Sequence[int]) -> bytes:
    return struct.pack(">%dH" % len(words), *words)


@dataclass
class Script:
    """A parsed script file: the entries' strings, and what is needed to write the file back like the original."""

    header_rest: bytes          # bytes 4..0x20
    record_rest: List[bytes]    # the 24 reserved bytes of each record
    strings: List[List[str]]    # editor text of every string, per entry
    tail: bytes                 # bytes after the last entry's padding (empty in the shipped files)


def parse(data: bytes) -> Script:
    """Read a script file. Raises ``ScriptError`` for a layout this reader does not know."""
    if len(data) < HEADER_SIZE:
        raise ScriptError("the file is too short")
    count = struct.unpack_from(">I", data, 0)[0]
    table_end = HEADER_SIZE + count * RECORD_SIZE
    if count == 0 or count > 4096 or table_end > len(data):
        raise ScriptError("the entry table does not fit the file")
    records = [struct.unpack_from(">2I", data, HEADER_SIZE + i * RECORD_SIZE) for i in range(count)]
    position = table_end
    strings: List[List[str]] = []
    for index, (offset, size) in enumerate(records):
        if offset != position or offset + size > len(data):
            raise ScriptError("entry %d does not follow the previous one" % index)
        strings.append(_parse_entry(data[offset:offset + size], index))
        position = (offset + size + ALIGN - 1) // ALIGN * ALIGN
    parsed = Script(data[4:HEADER_SIZE], [data[HEADER_SIZE + i * RECORD_SIZE + 8:HEADER_SIZE + (i + 1) * RECORD_SIZE]
                                          for i in range(count)], strings, data[position:])
    if build(parsed) != data:
        raise ScriptError("the file does not rebuild byte for byte; its layout has a part this reader does not know")
    return parsed


def _parse_entry(entry: bytes, index: int) -> List[str]:
    if len(entry) < 4:
        raise ScriptError("entry %d is too short" % index)
    count = struct.unpack_from(">I", entry, 0)[0]
    if 4 + count * 4 > len(entry):
        raise ScriptError("entry %d: the offset table does not fit" % index)
    offsets = list(struct.unpack_from(">%dI" % count, entry, 4)) + [len(entry)]
    texts: List[str] = []
    for k in range(count):
        start, end = offsets[k], offsets[k + 1]
        if start > end or end > len(entry) or (end - start) % 2:
            raise ScriptError("entry %d, string %d: bad offsets" % (index, k))
        words = struct.unpack_from(">%dH" % ((end - start) // 2), entry, start)
        try:
            texts.append(decode(words))
        except ScriptError as exc:
            raise ScriptError("entry %d, string %d: %s" % (index, k, exc)) from exc
    return texts


def _build_entry(texts: Sequence[str]) -> bytes:
    bodies = [_pack(encode(text)) for text in texts]
    offsets, position = [], 4 + 4 * len(bodies)
    for body in bodies:
        offsets.append(position)
        position += len(body)
    return struct.pack(">I", len(bodies)) + struct.pack(">%dI" % len(offsets), *offsets) + b"".join(bodies)


def build(script: Script) -> bytes:
    """The bytes of a script file with the strings of ``script`` (offsets and sizes recomputed)."""
    count = len(script.strings)
    entries = [_build_entry(texts) for texts in script.strings]
    position = HEADER_SIZE + count * RECORD_SIZE
    table, body = [], bytearray()
    for index, entry in enumerate(entries):
        table.append(struct.pack(">2I", position, len(entry)) + script.record_rest[index])
        padding = -len(entry) % ALIGN
        body += entry + b"\0" * padding
        position += len(entry) + padding
    return struct.pack(">I", count) + script.header_rest + b"".join(table) + bytes(body) + script.tail


def with_strings(script: Script, strings: Sequence[Sequence[str]]) -> Script:
    """A copy of ``script`` that holds ``strings``. The game looks strings up by number, so the counts must match."""
    if len(strings) != len(script.strings):
        raise ScriptError("the translation has %d scenes, the game file has %d" % (len(strings), len(script.strings)))
    for index, (new, old) in enumerate(zip(strings, script.strings)):
        if len(new) != len(old):
            raise ScriptError("scene %d has %d strings, the game file has %d" % (index, len(new), len(old)))
    return Script(script.header_rest, script.record_rest, [list(texts) for texts in strings], script.tail)
