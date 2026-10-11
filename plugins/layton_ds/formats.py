"""The text files of Professor Layton on Nintendo DS as rows the editor shows, and back.

Curious Village (``LAYTON1``), Pandora's Box (``LAYTON2``), Lost Future (``LAYTON3``) and Spectre's Call
(``LAYTON4``) keep their dialogue, puzzle texts and names in these containers (the plugin works on the game's own
files, compressed as they are):

- packs (``.pcm``, ``.plz``, ``.cpck``): BIOS-compressed ``LPCK`` / ``PCK2`` / ``LPC2`` archives whose members are
  plain texts (``.txt``), scripts (``.gds``) or Level-5 script binaries (``.lbin``); see ``core.containers.layton_ds``;
- ``.gds``: a stream of typed operands (0 command, 1 int, 2 float, 3 string, 4 flags, 6 / 7 jump offset, 0xC end).
  Dialogue of Pandora's Box is one talk script per line; Curious Village keeps puzzle titles, hints and quiz
  texts in them. Jumps are byte positions after the 4-byte length: they are moved when a string changes size;
- ``.lbin`` / ``.cbin`` (``LSCR``): command table, operand table (5 bytes: type, value; type 2 is an offset into
  the string bank at the end of the file);
- ``.cb`` (``GSD1``, Spectre's Call, Level-5 compressed): header, command table, operands (type 0x18 is an
  offset into the file), then NUL-terminated strings;
- ``.txt``: one text.

Strings are bytes: ASCII with the game's own markup (``<T>``, ``<W>``, ``@p``, ``<'e>``), Shift-JIS (cp932) for the
Japanese speaker labels of Lost Future and Spectre's Call. Pandora's Box and Curious Village texts are read as
Latin-1 (one byte per letter, nothing is lost). A string that cannot be encoded in the file's encoding is refused.
"""
from __future__ import annotations

import contextvars
import re
import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.containers import layton_ds as pack_codec
from core.containers import level5

LATIN = "latin-1"
SJIS = "cp932"
UTF8 = "utf-8"
# The Android HD ports (``data-en`` ... folders) store every text as UTF-8; the DS games use Latin-1 / Shift-JIS.
# ``Document`` sets this while it reads or writes a file of an HD port: the codecs then take UTF-8.
_UTF8 = contextvars.ContextVar("layton_utf8", default=False)
_JAPANESE = re.compile(r"[぀-ヿ㐀-鿿｡-ﾟ-￯]")
_MARKUP = re.compile(r"<[^<>]*>|@[a-zA-Z0-9]")
_ASSET = re.compile(r"^[\w\-./\\%#:]+$")


class FormatError(ValueError):
    """Not a file of the kind it claims to be."""


class EncodeError(ValueError):
    """A string holds a letter the file's encoding cannot store."""


@dataclass
class Row:
    member: str           # name inside the pack ("" for a loose file)
    kind: str             # "dialogue" or "text"
    speaker: str          # the (Japanese) label of the speaker, "" when the file has none
    label: str            # opcode / expression, for the editor's info
    text: str             # as stored, with "\n" line breaks


def is_japanese(text: str) -> bool:
    return bool(_JAPANESE.search(text))


def looks_like_text(text: str) -> bool:
    """A script string a person reads (not a file name, an animation name or a flag)."""
    plain = _MARKUP.sub("", text).strip()
    if not plain or is_japanese(plain):
        return False
    if len(re.findall(r"[A-Za-z]", plain)) < 2:
        return False
    if re.search(r"[\s,.!?;:'\"]", plain):
        if not re.search(r"[A-Z.,!?;:'\"]", plain):          # "b1 normal", "talk": an expression, not a sentence
            return False
        return not re.search(r"\.(arc|arj|bgx|spr|sbj|gds|txt|pcm|plz|dlz|cpck|cbin|cimg|cani|lbin|SAD|swd)$", plain, re.I)
    if _ASSET.match(plain):
        return bool(re.match(r"[A-Z][a-z]{2,}", plain)) and "_" not in plain and "." not in plain
    return True


def _resolve(encoding: str) -> str:
    return UTF8 if _UTF8.get() and encoding in (SJIS, LATIN) else encoding


def _encode(text: str, encoding: str, where: str) -> bytes:
    encoding = _resolve(encoding)
    try:
        return text.encode(encoding, errors="surrogateescape" if encoding == SJIS else "strict")
    except UnicodeEncodeError as error:
        bad = text[error.start:error.end]
        raise EncodeError(f"{where}: {bad!r} cannot be stored in this game's text encoding ({encoding}); "
                          f"use the letters the game's font has") from None


def _decode(raw: bytes, encoding: str) -> str:
    resolved = _resolve(encoding)
    if resolved != encoding:                # an HD port: UTF-8; a file it took over from the DS may be Shift-JIS
        try:
            return raw.decode(resolved)
        except UnicodeDecodeError:
            pass
    return raw.decode(encoding, errors="surrogateescape" if encoding == SJIS else "strict")


# -- one member / file ----------------------------------------------------------------------------------

class Codec:
    """Rows of one file and the file again with other texts."""

    rows: List[Row]

    def texts(self) -> List[str]:
        return [row.text for row in self.rows]

    def build(self, texts: List[str]) -> bytes:
        raise NotImplementedError


_EVENT_HEADER = re.compile(rb"^\d+\|[^|\r\n]*\|[^|\r\n]*\|\d+\|")


def _text_encoding(raw: bytes, fallback: str) -> str:
    """``utf-8`` for text that has non-ASCII bytes and is valid UTF-8 (the Android HD ports store UTF-8), else
    the DS games' own encoding."""
    if _UTF8.get():
        try:
            raw.decode("utf-8")
            return UTF8
        except UnicodeDecodeError:
            return fallback
    if all(b < 0x80 for b in raw):
        return fallback
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return fallback
    return "utf-8"


class TxtCodec(Codec):
    """A plain text file. An event line starts with a ``50|NONE|NONE|3|`` header that is not text: it is the row's
    label and stays as it is."""

    def __init__(self, data: bytes, member: str = ""):
        self.data = data
        self.member = member
        match = _EVENT_HEADER.match(data)
        self.head = match.group() if match else b""
        body = data[len(self.head):]
        self.encoding = _text_encoding(body, LATIN)
        label = self.head.decode("ascii", "replace")
        self.rows = [Row(member, "text", "", label, body.decode(self.encoding))] if body.strip(b"\r\n \0") else []

    def build(self, texts: List[str]) -> bytes:
        if not self.rows:
            return self.data
        return self.head + _encode(texts[0], self.encoding, self.member or "txt")


class GdsCodec(Codec):
    """A ``.gds`` script: the operands of type 3 that read as text are the rows."""

    def __init__(self, data: bytes, member: str = "", talk: bool = False):
        self.data = data
        self.member = member
        self.talk = talk
        if len(data) < 6:
            raise FormatError("gds too short")
        length = struct.unpack_from("<I", data, 0)[0]
        if length + 4 != len(data):
            raise FormatError("gds length does not match")
        # (start, end, text, nul) of each string operand's payload; (position, type, value) of jump operands
        self.strings: List[Tuple[int, int, bytes]] = []
        self.jumps: List[Tuple[int, int]] = []
        self.commands: List[Tuple[int, bytes]] = []
        self._tokens(length)
        self.rows = []
        self._text_ids: List[int] = []
        opcode = b""
        position = 0
        for index, (start, end, raw) in enumerate(self.strings):
            text = _decode(raw.rstrip(b"\0"), LATIN)
            if looks_like_text(text):
                while position + 1 < len(self.commands) and self.commands[position + 1][0] <= start:
                    position += 1
                opcode = self.commands[position][1] if self.commands else b""
                self.rows.append(Row(member, "text", "", opcode.hex() or "talk", text))
                self._text_ids.append(index)

    def _tokens(self, length: int) -> None:
        data = self.data
        pos = 2 if self.talk else 4
        end = length + 4
        if self.talk:
            self.commands.append((4, b""))
        while pos < end:
            kind = struct.unpack_from("<H", data, pos)[0]
            at = pos
            pos += 2
            if kind == 0:
                opcode = b"" if self.talk else data[pos:pos + 2]
                if not self.talk:
                    pos += 2
                self.commands.append((at, opcode))
            elif kind in (1, 2):
                pos += 4
            elif kind in (3, 4):
                size = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                if kind == 3:
                    self.strings.append((pos, pos + size, data[pos:pos + size]))
                pos += size
            elif kind in (6, 7):
                self.jumps.append((pos, struct.unpack_from("<i", data, pos)[0]))
                pos += 4
            elif kind in (5, 8, 9, 10, 11, 12):
                pass
            else:
                raise FormatError(f"unknown gds operand type {kind}")
        if pos != end:
            raise FormatError("gds operands run past the end")

    def build(self, texts: List[str]) -> bytes:
        if list(texts) == self.texts():
            return self.data
        replace: Dict[int, bytes] = {}
        for index, text in zip(self._text_ids, texts):
            _start, _end, raw = self.strings[index]
            nul = raw.endswith(b"\0")
            replace[index] = _encode(text, LATIN, f"{self.member or 'gds'} string {index}") + (b"\0" if nul else b"")
        # growth before each old position, to move jump targets
        marks = []          # (old string start, delta)
        for index, (start, end, raw) in enumerate(self.strings):
            if index in replace:
                marks.append((end, len(replace[index]) - len(raw)))
        out = bytearray()
        last = 0
        for index, (start, end, raw) in enumerate(self.strings):
            if index not in replace:
                continue
            out += self.data[last:start - 2]
            out += struct.pack("<H", len(replace[index]))
            out += replace[index]
            last = end
        out += self.data[last:]

        def moved(old_abs: int) -> int:
            return old_abs + sum(change for end, change in marks if end <= old_abs)

        for position, value in self.jumps:
            new_value = moved(value + 4) - 4
            if new_value != value:
                at = position + sum(change for end, change in marks if end <= position)
                struct.pack_into("<i", out, at, new_value)
        struct.pack_into("<I", out, 0, len(out) - 4)
        return bytes(out)


class LscrCodec(Codec):
    """Level-5 ``LSCR``: dialogue lines (opcode 6001: id, speaker, text) and other strings that read as text."""

    DIALOGUE = 0x1771

    def __init__(self, data: bytes, member: str = ""):
        if data[:4] != b"LSCR":
            raise FormatError("not LSCR")
        self.data = data
        self.member = member
        count, self.cmd_at, self.ops_at, self.bank_at = struct.unpack_from("<HHII", data, 4)
        self.commands = [struct.unpack_from("<HHI", data, self.cmd_at + 8 * i) for i in range(count)]
        n_ops = max((first + n for _op, n, first in self.commands), default=0)
        self.op_values = [(data[self.ops_at + 5 * i], struct.unpack_from("<I", data, self.ops_at + 5 * i + 1)[0])
                          for i in range(n_ops)]
        self.bank = data[self.bank_at:]
        self.rows = []
        self._slots: List[int] = []             # operand index of each row's text
        for opcode, n, first in self.commands:
            speaker = ""
            if opcode == self.DIALOGUE and n >= 3 and self.op_values[first + 2][0] == 2:
                speaker = self._string(first + 1)
                self.rows.append(Row(member, "dialogue", speaker if is_japanese(speaker) or speaker else "", "6001",
                                     self._string(first + 2)))
                self._slots.append(first + 2)
                continue
            for k in range(n):
                if self.op_values[first + k][0] == 2:
                    text = self._string(first + k)
                    if looks_like_text(text):
                        self.rows.append(Row(member, "text", "", hex(opcode), text))
                        self._slots.append(first + k)

    def _string(self, op_index: int) -> str:
        offset = self.op_values[op_index][1]
        end = self.bank.find(b"\0", offset)
        return _decode(self.bank[offset:end if end >= 0 else len(self.bank)], SJIS)

    def build(self, texts: List[str]) -> bytes:
        if list(texts) == self.texts():
            return self.data
        bank = bytearray(self.bank)
        out = bytearray(self.data)
        changed: Dict[int, int] = {}
        for slot, text, row in zip(self._slots, texts, self.rows):
            if text == row.text:
                continue
            raw = _encode(text, SJIS, f"{self.member or 'lbin'} operand {slot}")
            offset = len(bank)
            bank += raw + b"\0"
            changed[slot] = offset
        for slot, offset in changed.items():
            struct.pack_into("<I", out, self.ops_at + 5 * slot + 1, offset)
        return bytes(out[:self.bank_at]) + bytes(bank)


class Gsd1Codec(Codec):
    """Spectre's Call ``GSD1`` script (decompressed): strings after the operand table, referenced by type 0x18."""

    STRING_OP = 0x18

    def __init__(self, data: bytes, member: str = ""):
        if data[:4] != b"GSD1":
            raise FormatError("not GSD1")
        self.data = data
        self.member = member
        entries, _b, ops, _d, _e, _f = struct.unpack_from("<6H", data, 4)
        self.ops_at = 0x10 + entries * 6 + 2
        self.ops_end = self.ops_at + ops * 5
        if self.ops_end > len(data):
            raise FormatError("GSD1 operand table runs past the end")
        self.table_at = (self.ops_end + 3) & ~3
        self.refs: Dict[int, List[int]] = {}
        order: List[int] = []                  # string offsets in the order the script first uses them
        for at in range(self.ops_at, self.ops_end, 5):
            if data[at] == self.STRING_OP:
                value = struct.unpack_from("<I", data, at + 1)[0]
                if value not in self.refs:
                    order.append(value)
                self.refs.setdefault(value, []).append(at)
        self.rows = []
        self._starts: List[int] = []
        self._ends: List[int] = []
        speaker = ""
        for pos in order:
            if not self.table_at <= pos < len(data):
                continue
            end = data.find(b"\0", pos)
            end = len(data) if end < 0 else end
            text = _decode(data[pos:end], SJIS)
            if not text:
                continue
            if is_japanese(text):
                speaker = text
            else:
                self.rows.append(Row(member, "dialogue" if "<T>" in text else "text", speaker, "", text))
                self._starts.append(pos)
                self._ends.append(end)

    def build(self, texts: List[str]) -> bytes:
        if list(texts) == self.texts():
            return self.data
        out = bytearray(self.data)
        for start, end, text, row in zip(self._starts, self._ends, texts, self.rows):
            if text == row.text:
                continue
            raw = _encode(text, SJIS, f"{self.member or 'cb'} string at {start}")
            if len(raw) <= end - start:
                out[start:end] = raw + bytes(end - start - len(raw))      # shorter or equal: in place
            else:
                new = len(out)
                out += raw + b"\0"                                          # longer: moved to the end
                for at in self.refs.get(start, []):
                    struct.pack_into("<I", out, at + 1, new)
        return bytes(out)


# -- documents ------------------------------------------------------------------------------------------

PACK_SUFFIXES = (".pcm", ".plz", ".cpck", ".dlz", ".cbin", ".lbin")


class NazoCodec(Codec):
    """Pandora's Box puzzle record (``n<id>.dat``): title (48 bytes), then the prompt, the two answers and the
    three hints in a string bank at 112 whose six u32 offsets follow the flags (at 0x40)."""

    HEADER, NAME_AT, NAME_WIDTH, OFFSETS_AT, BANK_MAX = 112, 4, 48, 0x40, 2560
    LABELS = ("Prompt", "Correct", "Wrong", "Hint 1", "Hint 2", "Hint 3")

    def __init__(self, data: bytes, member: str = ""):
        if len(data) < self.HEADER or struct.unpack_from("<H", data, 2)[0] != self.HEADER:
            raise FormatError("not a puzzle record")
        self.data = data
        self.member = member
        self.offsets = list(struct.unpack_from("<6I", data, self.OFFSETS_AT))
        if any(self.HEADER + o >= len(data) for o in self.offsets):
            raise FormatError("puzzle string offsets run past the end")
        name = data[self.NAME_AT:self.NAME_AT + self.NAME_WIDTH].split(b"\0")[0]
        strings = [name]
        for offset in self.offsets:
            strings.append(data[self.HEADER + offset:data.index(b"\0", self.HEADER + offset)])
        self.encoding = _text_encoding(b"".join(strings), SJIS)
        self.rows = [Row(member, "text", "", "Title" if i == 0 else self.LABELS[i - 1], _decode(raw, self.encoding))
                     for i, raw in enumerate(strings)]

    def build(self, texts: List[str]) -> bytes:
        name = _encode(texts[0], self.encoding, f"{self.member} title")
        if len(name) >= self.NAME_WIDTH:
            raise EncodeError(f"{self.member}: the title is {len(name)} bytes, {self.NAME_WIDTH - 1} fit")
        bank, offsets, seen = bytearray(), [], {}
        for label, text in zip(self.LABELS, texts[1:]):
            raw = _encode(text, self.encoding, f"{self.member} {label}")
            if raw not in seen:
                seen[raw] = len(bank)
                bank += raw + b"\0"
            offsets.append(seen[raw])
        if len(bank) > self.BANK_MAX:
            raise EncodeError(f"{self.member}: the puzzle text is {len(bank)} bytes, {self.BANK_MAX} fit")
        out = bytearray(self.data[:self.HEADER])
        out[self.NAME_AT:self.NAME_AT + self.NAME_WIDTH] = name + bytes(self.NAME_WIDTH - len(name))
        struct.pack_into("<6I", out, self.OFFSETS_AT, *offsets)
        return bytes(out + bank)


# entry length -> text fields (offset, width) of Pandora's Box database files (.dlz)
DLZ_FIELDS = {60: ((4, 48),), 52: ((4, 48),), 90: ((0, 32),), 54: ((4, 48),), 48: ((2, 46),), 224: ((4, 28), (32, 192))}


class DlzCodec(Codec):
    """A ``.dlz`` database: ``u16 count, u16 8, u32 entry length`` and the entries; the text fields are fixed width,
    NUL padded (which fields: ``DLZ_FIELDS``, by entry length)."""

    def __init__(self, data: bytes, member: str = ""):
        if len(data) < 8:
            raise FormatError("dlz too short")
        count, header, length = struct.unpack_from("<HHI", data, 0)
        if header != 8 or length not in DLZ_FIELDS or 8 + count * length != len(data) or count == 0:
            raise FormatError("not a text database")
        self.data = data
        self.member = member
        self.length = length
        self.fields = DLZ_FIELDS[length]
        self.rows = []
        self._places: List[Tuple[int, int, int]] = []     # (entry start, field offset, width)
        printable = 0
        for index in range(count):
            for offset, width in self.fields:
                at = 8 + index * length + offset
                raw = data[at:at + width].split(b"\0")[0]
                if raw:
                    printable += sum(1 for b in raw if b >= 32)
                    self.rows.append(Row(member, "text", "", f"{index}:{offset}", _decode(raw, SJIS)))
                    self._places.append((8 + index * length, offset, width))
        if self.rows and printable < len(self.rows):
            raise FormatError("not a text database")

    def build(self, texts: List[str]) -> bytes:
        out = bytearray(self.data)
        for (start, offset, width), text, row in zip(self._places, texts, self.rows):
            if text == row.text:
                continue
            raw = _encode(text, SJIS, f"{self.member or 'dlz'} {row.label}")
            if len(raw) >= width:
                raise EncodeError(f"{self.member or 'dlz'} {row.label}: {len(raw)} bytes, {width - 1} fit")
            out[start + offset:start + offset + width] = raw + bytes(width - len(raw))
        return bytes(out)


def _member_codec(name: str, data: bytes, talk: bool) -> Optional[Codec]:
    lower = name.lower()
    try:
        if lower.endswith(".txt"):
            return TxtCodec(data, name)
        if lower.endswith(".gds"):
            return GdsCodec(data, name, talk)
        if lower.endswith((".lbin", ".cbin")) and data[:4] == b"LSCR":
            return LscrCodec(data, name)
        if lower.endswith(".dat"):
            return NazoCodec(data, name)
        if lower.endswith(".dlz"):
            return DlzCodec(data, name)
    except (FormatError, struct.error, UnicodeDecodeError):
        return None
    return None


def _is_dlz(data: bytes) -> bool:
    if len(data) < 8:
        return False
    count, header, length = struct.unpack_from("<HHI", data, 0)
    return header == 8 and length in DLZ_FIELDS and count > 0 and 8 + count * length == len(data)


def _is_nazo(data: bytes) -> bool:
    """A puzzle record (``n<id>.dat``): the header size 112 at 2 and string offsets that stay inside the file."""
    try:
        NazoCodec(data)
    except (FormatError, ValueError, struct.error):
        return False
    return True


def _is_gds(data: bytes) -> bool:
    return len(data) >= 8 and struct.unpack_from("<I", data, 0)[0] + 4 == len(data)


class Document:
    """Rows of a game file, found by what the file holds (the name is only a hint).

    ``build`` writes the file again in the form the game stores it: compressed as it was.
    """

    def __init__(self, raw: bytes, name: str = "", utf8: Optional[bool] = None):
        if utf8 is None:                    # a file of an Android HD port: its folder is data-en, data-EU ...
            utf8 = name.replace("\\", "/").split("/")[0].startswith("data-")
        self.utf8 = utf8
        token = _UTF8.set(self.utf8)
        try:
            self._parse(raw, name)
        finally:
            _UTF8.reset(token)

    def _parse(self, raw: bytes, name: str) -> None:
        self.raw = bytes(raw)
        self.name = name
        self.pack: Optional[pack_codec.Pack] = None
        self.codecs: List[Tuple[int, Codec]] = []      # (member index, codec)
        self.single: Optional[Codec] = None
        self.compression = ""                          # "", "level5" or "bios"
        self.rows: List[Row] = []
        plain = self.raw
        gsd1 = self._level5_gsd1()
        if gsd1 is not None:
            self.compression, plain = "level5", gsd1
        elif self.raw[:4] not in (b"GSD1", b"LSCR", b"LPC2") and not _is_gds(self.raw):
            try:
                plain, _prefix = pack_codec.decompress(self.raw)
                self.compression = "bios"
            except (ValueError, IndexError, struct.error):
                plain = self.raw
        self.plain = plain
        kind = pack_codec.Pack.detect(plain)
        unix = name.replace("\\", "/")
        if kind is not None:
            self.pack = pack_codec.Pack.parse(plain)
            talk = kind == pack_codec.PCK2
            # a picture pack (``.cani``): its script only names the pictures and the animation frames
            pictures = any(m.name.lower().endswith(".limg") for m in self.pack.members)
            for index, member in enumerate(self.pack.members):
                if pictures:
                    break
                codec = _member_codec(member.name, member.data, talk and not _normal_gds(member.data))
                if codec is not None and codec.rows:
                    self.codecs.append((index, codec))
        elif plain[:4] == b"GSD1":
            self.single = Gsd1Codec(plain)
        elif plain[:4] == b"LSCR":
            self.single = LscrCodec(plain)
        elif _is_dlz(plain):
            self.single = DlzCodec(plain)
        elif _is_gds(plain) or unix.lower().endswith(".gds"):
            self.single = GdsCodec(plain, "", not _normal_gds(plain))
        elif _is_nazo(plain):
            self.single = NazoCodec(plain)
        elif unix.lower().endswith(".txt") or _printable(plain) or (self.utf8 and _utf8_text(plain)):
            self.single = TxtCodec(plain)
        else:
            raise FormatError("not a Layton DS text file")
        if self.single is not None:
            self.rows = list(self.single.rows)
        for _index, codec in self.codecs:
            self.rows.extend(codec.rows)

    def _level5_gsd1(self) -> Optional[bytes]:
        if self.raw[:4] == b"GSD1" or len(self.raw) < 8:
            return None
        try:
            if (self.raw[0] & 7) > 5:
                return None
            plain = level5.decompress(self.raw)
        except Exception:                   # noqa: BLE001 - any failure means "not Level-5 data"
            return None
        return plain if plain[:4] == b"GSD1" else None

    def texts(self) -> List[str]:
        return [row.text for row in self.rows]

    def build(self, texts: List[str]) -> bytes:
        token = _UTF8.set(self.utf8)
        try:
            return self._build(texts)
        finally:
            _UTF8.reset(token)

    def _build(self, texts: List[str]) -> bytes:
        if len(texts) != len(self.rows):
            raise ValueError("the number of strings changed")
        if list(texts) == self.texts():
            return self.raw
        position = 0
        if self.single is not None:
            plain = self.single.build(list(texts))
        else:
            assert self.pack is not None
            members = [pack_codec.Member(m.name, m.data, m.field) for m in self.pack.members]
            for index, codec in self.codecs:
                count = len(codec.rows)
                members[index].data = codec.build(list(texts[position:position + count]))
                position += count
            plain = pack_codec.Pack(self.pack.kind, members, self.pack.tail, self.pack.align).build()
        if self.compression == "level5":
            return level5.recompress(self.raw, plain)
        if self.compression == "bios":
            return pack_codec.recompress(self.raw, plain)
        return plain


def _normal_gds(data: bytes) -> bool:
    """A script that starts with a command (type 0) after the length; a talk script starts with an operand."""
    return len(data) >= 8 and struct.unpack_from("<H", data, 4)[0] == 0


def _utf8_text(data: bytes) -> bool:
    """UTF-8 text without control characters but tab and line breaks (an HD port's text file: the app gives no name)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return bool(text.strip()) and all(c >= " " or c in "\t\r\n" for c in text)


def _printable(data: bytes) -> bool:
    return bool(data) and all(b in (9, 10, 13) or 32 <= b < 127 for b in data)
