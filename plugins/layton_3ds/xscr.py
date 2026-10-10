"""One XSCR script of the Layton 3DS games (``*.xs``) as the rows the editor shows, and back.

An XSCR file (Level-5 ``lt5`` / ``lt6`` engine: Miracle Mask, Azran Legacy, vs. Phoenix Wright, Mystery Journey) is a
0x14-byte header --
``XSCR``, u16 command count, u16 version (5), u32 argument count, u32 offset / 4 of the argument table, u32
offset / 4 of the string table -- then three Level-5-compressed (LZ10) tables, each 4-aligned: commands (u16 opcode,
u16 argument count, u32 index of the first argument), arguments (u32 type, u32 value: 1 int, 2 float, 0x18 offset
into the string table) and the strings (NUL-terminated, every distinct string once in order of first use): Shift-JIS
in the first three games, UTF-8 in Mystery Journey (``encoding``: given by the caller, else UTF-8 when the table
decodes as UTF-8 and is not plain ASCII, else Shift-JIS). A third of Mystery Journey's scripts keep Shift-JIS
speaker labels next to their UTF-8 text: a string that does not decode in ``encoding`` is read as Shift-JIS, and
edited rows are always written in ``encoding``.

Text files (``txt/<lang>/**/*.xs``) hold one line per command 1001: (id, speaker label in Japanese, text). The
definitions file (``res/<lang>/*_def*.xs``) holds the names the game shows -- puzzle titles and types, minigame
names, the game title -- among Japanese labels and identifiers: in a script without command 1001 a string is a
row when it has a lowercase and an uppercase letter and no Japanese. Japanese leftovers and empty lines stay out of the editor and are
written back as they are. Accented letters are the game's ``{'e}`` escapes; the editor shows them as stored.

``build`` writes the file again with the changed rows: unchanged rows keep their bytes, a changed row is encoded
with the file's line ending (CRLF in vs. Phoenix Wright, LF in the others). An unedited file is returned as it is.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from core.containers import level5

HEADER = 0x14
MAGIC = b"XSCR"
INT, FLOAT, STRING = 1, 2, 0x18
DIALOGUE_OP = 1001          # (id, speaker label, text, ...)
TEXT_ARG = 2
ENCODING = "cp932"          # the older games; Mystery Journey is "utf-8"
_JAPANESE = re.compile(r"[぀-ヿ㐀-鿿｡-ﾟ]")


class FormatError(ValueError):
    """Not an XSCR file."""


@dataclass
class Row:
    command: int            # index of the command
    arg: int                # index of the argument (absolute, in the argument table)
    opcode: int
    kind: str               # "dialogue" or "name"
    line_id: int            # first argument of the command (the id the script asks for), 0 for names
    speaker: str            # the Japanese speaker label of a dialogue line, "" otherwise
    text: str               # as stored, with "\n" line breaks


def is_japanese(text: str) -> bool:
    return bool(_JAPANESE.search(text))


def _is_name(text: str) -> bool:
    """A displayed name has an uppercase and a lowercase letter (any script) and no Japanese: not ``dummy``, ``#OFF``."""
    return any(c.isupper() for c in text) and any(c.islower() for c in text) and not is_japanese(text)


class Script:
    """A parsed XSCR file: ``commands`` (opcode, [(type, value)...]), ``strings`` (offset -> bytes) and ``rows``."""

    def __init__(self, raw: bytes, encoding: Optional[str] = None):
        self.raw = bytes(raw)
        if self.raw[:4] != MAGIC or len(self.raw) < HEADER:
            raise FormatError("not an XSCR script")
        count, self.version, arg_count, args_at, strings_at = struct.unpack_from("<HHIII", self.raw, 4)
        commands = level5.decompress(self.raw[HEADER:])
        args = level5.decompress(self.raw[args_at * 4:])
        self.strings = level5.decompress(self.raw[strings_at * 4:])
        if len(commands) < count * 8 or len(args) < arg_count * 8:
            raise FormatError("XSCR tables shorter than the header says")
        self.args: List[Tuple[int, int]] = [struct.unpack_from("<II", args, i * 8) for i in range(arg_count)]
        self.commands: List[Tuple[int, int, int]] = [struct.unpack_from("<HHI", commands, i * 8) for i in range(count)]
        self.crlf = b"\r\n" in self.strings
        self.encoding = encoding or _detect(self.strings)
        definitions = not any(opcode == DIALOGUE_OP for opcode, _argc, _first in self.commands)
        self.rows: List[Row] = []
        for c, (opcode, argc, first) in enumerate(self.commands):
            values = self.args[first:first + argc]
            if not definitions:
                if opcode != DIALOGUE_OP or argc <= TEXT_ARG or values[TEXT_ARG][0] != STRING:
                    continue
                text = self.string(values[TEXT_ARG][1])
                if not text or is_japanese(text):
                    continue
                speaker = self.string(values[1][1]) if values[1][0] == STRING else ""
                line_id = values[0][1] if values[0][0] == INT else 0
                self.rows.append(Row(c, first + TEXT_ARG, opcode, "dialogue", line_id, speaker, text))
                continue
            for j, (typ, value) in enumerate(values):
                if typ == STRING and _is_name(self.string(value)):
                    self.rows.append(Row(c, first + j, opcode, "name", 0, "", self.string(value)))

    def string(self, offset: int) -> str:
        end = self.strings.index(b"\0", offset)
        blob = self.strings[offset:end]
        try:
            text = blob.decode(self.encoding)
        except UnicodeDecodeError:          # Mystery Journey: UTF-8 text, some files keep Shift-JIS speaker labels
            text = blob.decode(ENCODING)
        return text.replace("\r\n", "\n")

    def texts(self) -> List[str]:
        return [row.text for row in self.rows]

    def build(self, strings: Sequence[str]) -> bytes:
        """The file with the editor's ``strings`` (one per row; a missing or equal one keeps the stored text)."""
        changed: Dict[int, bytes] = {}
        newline = b"\r\n" if self.crlf else b"\n"
        for row, text in zip(self.rows, strings):
            if str(text) != row.text:
                changed[row.arg] = str(text).replace("\r\n", "\n").encode(self.encoding).replace(b"\n", newline)
        if not changed:
            return self.raw
        table, offsets, args = bytearray(), {}, bytearray()
        for i, (typ, value) in enumerate(self.args):
            if typ == STRING:
                blob = changed.get(i)
                if blob is None:
                    blob = self.strings[value:self.strings.index(b"\0", value)]
                if blob not in offsets:
                    offsets[blob] = len(table)
                    table += blob + b"\0"
                value = offsets[blob]
            args += struct.pack("<II", typ, value)
        commands = b"".join(struct.pack("<HHI", *c) for c in self.commands)
        parts = [level5.compress(commands), level5.compress(bytes(args)), level5.compress(bytes(table))]
        out = bytearray(self.raw[:HEADER])
        at = []
        for part in parts:
            at.append(len(out))
            out += part
            out += b"\0" * (-len(out) % 4)
        struct.pack_into("<II", out, 0x0C, at[1] // 4, at[2] // 4)
        return bytes(out)


def _detect(strings: bytes) -> str:
    if strings.isascii():
        return ENCODING
    try:
        strings.decode("utf-8")
    except UnicodeDecodeError:
        return ENCODING
    return "utf-8"


def parse(raw: bytes, encoding: Optional[str] = None) -> Script:
    return Script(raw, encoding)


def make(commands: Sequence[Tuple[int, Sequence[object]]], crlf: bool = False, encoding: str = ENCODING) -> bytes:
    """An XSCR file for tests: ``commands`` = [(opcode, [int | float | str, ...]), ...]."""
    args, table, offsets, cmd_bytes = bytearray(), bytearray(), {}, bytearray()
    for opcode, values in commands:
        cmd_bytes += struct.pack("<HHI", opcode, len(values), len(args) // 8)
        for value in values:
            if isinstance(value, str):
                blob = value.replace("\n", "\r\n" if crlf else "\n").encode(encoding)
                if blob not in offsets:
                    offsets[blob] = len(table)
                    table += blob + b"\0"
                args += struct.pack("<II", STRING, offsets[blob])
            elif isinstance(value, float):
                args += struct.pack("<If", FLOAT, value)
            else:
                args += struct.pack("<Ii", INT, value)
    out = bytearray(MAGIC + struct.pack("<HHIII", len(commands), 5, len(args) // 8, 0, 0))
    at = []
    for part in (level5.compress(bytes(cmd_bytes)), level5.compress(bytes(args)), level5.compress(bytes(table))):
        at.append(len(out))
        out += part
        out += b"\0" * (-len(out) % 4)
    struct.pack_into("<II", out, 0x0C, at[1] // 4, at[2] // 4)
    return bytes(out)
