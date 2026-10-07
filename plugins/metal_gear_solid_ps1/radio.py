"""``RADIO.DAT``: every codec call of the game, one after another.

A call: ``u16 frequency, u32 face data (FACE.DAT), u16 flags`` (all big endian), then a block --
``0x80, u16 size`` (counted from the size field) and elements until a 0 byte -- then the call's own
12x12 glyphs (36 bytes each) for the codes ``0x96xx`` its text uses, then zero padding up to the
next call. An element is ``0xFF, code, u16 size, payload``:

- 1 talk: ``u16 character, u16 face, u16 animation`` and the line (NUL-terminated);
- 2 voice: ``u32`` VOX.DAT sector and a block (the lines said with that voice clip);
- 4 new contact: ``u16 frequency`` and the contact's name; 5 save: a value and GCL strings (save
  location names, each in hankaku and Shift-JIS form); 7 prompt: GCL strings (SAVE / DO NOT SAVE);
- 0x10 if (an expression, a block, then ``FF 11`` else-blocks or ``FF 12`` else-if expression + block),
  0x20 switch, 0x30 random switch: nested blocks; the rest carry no text.

The scripts in STAGE.DIR name a call by ``(sectors to read - 1) << 24 | byte offset``; the build
step moves the calls when one grows and fixes those codes (this module only lays out the file).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import codec
from .spans import Field, rewrite

HEADER = 8
GLYPH = 36
TALK, VOICE, CONTACT, SAVE, PROMPT = 1, 2, 4, 5, 7


class FormatError(ValueError):
    """Not a RADIO.DAT this plugin understands."""


@dataclass
class Text:
    start: int            # bytes of the string (without NUL) in the file
    end: int
    kind: str             # talk, contact, save, prompt
    speaker: int = 0      # talk: character code


@dataclass
class Call:
    offset: int
    block_end: int        # end of the call's block
    end: int              # end of its glyphs
    next: int             # where the next call starts (end of the padding)
    frequency: int
    texts: List[Text] = field(default_factory=list)
    fields: List[Field] = field(default_factory=list)
    voices: List[int] = field(default_factory=list)       # offsets of the u32 VOX codes


class _Parser:
    def __init__(self, data: bytes, call: Call):
        self.d, self.call = data, call

    def u16(self, at: int) -> int:
        return struct.unpack_from(">H", self.d, at)[0]

    def block(self, at: int) -> int:
        if self.d[at] != 0x80:
            raise FormatError(f"block expected at {at:#x}")
        end = at + 1 + self.u16(at + 1)
        if end > len(self.d):
            raise FormatError(f"block at {at:#x} runs past the file")
        self.call.fields.append(Field(at + 1, 2, at + 1, end))
        pos = at + 3
        while pos < end and self.d[pos]:
            pos = self.element(pos, end)
        if pos >= end:
            raise FormatError(f"block at {at:#x} has no end")
        return end

    def value(self, at: int) -> int:
        kind = self.d[at]
        if kind & 0xF0 == 0x30:
            return at + 1 + self.d[at + 1]
        if kind & 0xF0 == 0x10:
            return at + 4
        size = {1: 3, 2: 2, 3: 2, 4: 2, 6: 3, 8: 3, 9: 5, 10: 5}.get(kind)
        if size is None:
            raise FormatError(f"value {kind:#x} at {at:#x}")
        return at + size

    def string(self, at: int, end: int, kind: str, speaker: int = 0) -> None:
        stop = self.d.find(b"\0", at, end)
        if stop < 0:
            raise FormatError(f"string at {at:#x} has no end")
        self.call.texts.append(Text(at, stop, kind, speaker))

    def gcl_strings(self, at: int, end: int, kind: str, wide_only: bool) -> None:
        while at < end and self.d[at] == 0x07:
            length = self.d[at + 1]
            stop = at + 2 + length
            raw = self.d[at + 2:stop - 1]
            if stop > end or self.d[stop - 1]:
                raise FormatError(f"GCL string at {at:#x}")
            if not wide_only or codec.is_wide(raw):
                self.call.fields.append(Field(at + 1, 1, at + 2, stop))
                self.call.texts.append(Text(at + 2, stop - 1, kind))
            at = stop

    def element(self, at: int, outer: int) -> int:
        d = self.d
        if d[at] != 0xFF:
            raise FormatError(f"element expected at {at:#x}")
        code = d[at + 1]
        end = at + 2 + self.u16(at + 2)
        if end > outer:
            raise FormatError(f"element at {at:#x} runs past its block")
        self.call.fields.append(Field(at + 2, 2, at + 2, end))
        pos = at + 4
        if code == TALK:
            self.string(pos + 6, end, "talk", self.u16(pos))
        elif code == CONTACT:
            self.string(pos + 2, end, "contact")
        elif code == VOICE:
            self.call.voices.append(pos)
            self.block(pos + 4)
        elif code == SAVE:
            self.gcl_strings(self.value(pos), end, "save", True)
        elif code == PROMPT:
            self.gcl_strings(pos, end, "prompt", False)
        elif code == 0x10:
            pos = self.block(self.value(pos))
            while pos < end:
                if d[pos] == 0:
                    pos += 1
                    continue
                if d[pos] != 0xFF or d[pos + 1] not in (0x11, 0x12):
                    raise FormatError(f"if/else at {pos:#x}")
                pos += 2
                if d[pos - 1] == 0x12:
                    pos = self.value(pos)
                pos = self.block(pos)
        elif code in (0x20, 0x30):
            pos = self.value(pos) if code == 0x20 else pos + 2
            while True:
                case = d[pos]
                pos += 1
                if case == 0:
                    break
                if case in (0x21, 0x31):
                    pos = self.block(pos + 2)
                elif case == 0x22:
                    pos = self.block(pos)
                else:
                    raise FormatError(f"switch case {case:#x} at {pos:#x}")
        return end


def _glyphs(data: bytes, texts: Sequence[Text]) -> int:
    """How many of the call's own glyphs its text uses (the highest 0x96xx..0x99xx code)."""
    top = 0
    for text in texts:
        pos = text.start
        while pos < text.end:
            byte = data[pos]
            if byte < 0x80:
                pos += 1
                continue
            if 0x96 <= byte <= 0x99 and pos + 1 < text.end:
                top = max(top, (byte - 0x96) * 255 + data[pos + 1])
            pos += 2
    return top


def parse_call(data: bytes, offset: int) -> Call:
    if offset + HEADER + 3 > len(data) or data[offset + HEADER] != 0x80:
        raise FormatError(f"no codec call at {offset:#x}")
    frequency = struct.unpack_from(">H", data, offset)[0]
    call = Call(offset, 0, 0, 0, frequency)
    call.block_end = _Parser(data, call).block(offset + HEADER)
    call.end = call.block_end + GLYPH * _glyphs(data, call.texts)
    if call.end > len(data):
        raise FormatError(f"glyphs of the call at {offset:#x} run past the file")
    return call


def read(data: bytes) -> List[Call]:
    """Every call of a RADIO.DAT, in file order."""
    calls: List[Call] = []
    pos = 0
    while pos < len(data):
        if not data[pos]:
            pos += 1
            continue
        call = parse_call(data, pos)
        calls.append(call)
        pos = call.end
        while pos < len(data) and not data[pos]:
            pos += 1
        call.next = pos
    if not calls:
        raise FormatError("no codec call")
    return calls


def looks_like(data: bytes) -> bool:
    """A RADIO.DAT: a call at offset 0 on a codec frequency (140.00 - 141.99 MHz)."""
    if len(data) < 64 or data[HEADER] != 0x80:
        return False
    if not 14000 <= struct.unpack_from(">H", data, 0)[0] < 14200:
        return False
    try:
        parse_call(data, 0)
    except (FormatError, IndexError, struct.error):
        return False
    return True


def build(data: bytes, calls: Sequence[Call], new_texts: Dict[Tuple[int, int], bytes]) -> Tuple[bytes, List[int]]:
    """The file with ``new_texts`` (``(call index, text index) -> bytes``), and each call's new offset.

    Calls keep their order, their glyphs and their padding; a call that grows moves the ones after it.
    """
    out = bytearray(data[:calls[0].offset])
    offsets = []
    for number, call in enumerate(calls):
        offsets.append(len(out))
        base = call.offset
        edits = [(text.start - base, text.end - base, new_texts[(number, index)])
                 for index, text in enumerate(call.texts) if (number, index) in new_texts]
        body = data[base:call.block_end]
        if edits:
            fields = [Field(f.pos - base, f.width, f.start - base, f.end - base) for f in call.fields]
            body = rewrite(body, fields, edits)
        out += body
        out += data[call.block_end:call.next]
    return bytes(out), offsets


def sectors_code(offset: int, length: int) -> int:
    """The code a script uses for a call at ``offset`` of ``length`` bytes (with its glyphs)."""
    sectors = (offset % 0x800 + length + 0x7FF) // 0x800
    return (sectors - 1) << 24 | offset


def texts_of(data: bytes, calls: Optional[Sequence[Call]] = None) -> List[List[bytes]]:
    """The raw strings of every call."""
    return [[data[t.start:t.end] for t in call.texts] for call in (calls or read(data))]
