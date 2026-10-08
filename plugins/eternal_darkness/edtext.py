r"""Eternal Darkness (GameCube) text files: ``0x6B5`` packs of ``0xFB90`` string tables, BPE messages.

A pack (big endian): u32 entry count, u32 ``0x6B5``, then per entry u32 offset (from the pack) and u32 size
(0 0 = empty); an entry is a nested pack, a string table or other data (TPL textures, font widths, models).
A string table: u32 message count, u32 ``0xFB90``, then per message u32 offset (from the table) and u32
size (0 0 = no message). Tables keep size 8 in their pack entry; their messages often sit together after
all tables of a pack. A message is four bytes (a copy of decoded bytes 16-19) and a Philip Gage byte-pair
block: pair table, u16 size, packed bytes. Decoded, it is a 24-byte header (scale float, RGBA colour, x,
y, flags, font), an alignment letter and a zero, the text and two zeros.

Text is single-byte (ASCII in the game; the plugin writes cp1251, so Ukrainian letters take the free font
cells 0x80-0xFF) with control codes: ``\aX`` colour, ``\iN`` icon, ``\sN.N`` scale, ``\n``, ``\r``, ``\\``
and ``~X`` (``~p`` the player's name). The editor shows them as ``{ay}``, ``{i21}``, ``{s0.6}``, ``{~p}``.

Saving changes only the messages: every run of messages that sit back to back is laid out again, padded
to keep 32-byte alignment, and every pack and table offset or size that spans the run moves with it.
Files the plugin opens: ``RmTxt*.cmp`` (room texts, decompressed by the workspace's unpack step),
``EBootPak.bin``, ``EBookPak.bin``, ``EMemcardText.bin``, ``Chars/cin*/cin*.bin`` (cinematic subtitles,
decompressed) and ``sys/main.dol`` (chapter titles, written in place).
"""
from __future__ import annotations

import re
import struct
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

PACK, TABLE = 0x6B5, 0xFB90
HEADER = 26                 # decoded message header (24 bytes + alignment letter + zero)
ALIGN = 0x20
MAX_DEPTH = 12              # pair nesting the game's 32-byte expansion stack takes with room to spare
ENCODING = "cp1251"

CODE_RE = re.compile(rb"\\(a[a-z]|i[0-9]+|s[0-9.]*|n|r|\\)|~(.)", re.S)
TAG_RE = re.compile(r"\{(a[a-z]|i[0-9]+|s[0-9.]*|n|r|\\|~.|x[0-9A-F]{2})\}", re.S)


class FormatError(ValueError):
    """Not an Eternal Darkness text file."""


def _u32(data: bytes, at: int) -> int:
    return struct.unpack_from(">I", data, at)[0]


# -- byte pair encoding ------------------------------------------------------------------------------


def bpe_decode(data: bytes, pos: int = 0) -> Tuple[bytes, int]:
    """One Gage BPE block at ``pos``: (decoded bytes, position after it)."""
    left = list(range(256))
    right = [0] * 256
    c = 0
    while True:
        count = data[pos]
        pos += 1
        if count > 127:
            c += count - 127
            count = 0
        if c == 256:
            break
        for _ in range(count + 1):
            left[c] = data[pos]
            pos += 1
            if c != left[c]:
                right[c] = data[pos]
                pos += 1
            c += 1
        if c == 256:
            break
    size = data[pos] << 8 | data[pos + 1]
    pos += 2
    end = pos + size
    if end > len(data):
        raise FormatError("BPE block runs past its message")
    out = bytearray()
    stack: List[int] = []
    while True:
        if stack:
            ch = stack.pop()
        elif pos < end:
            ch = data[pos]
            pos += 1
        else:
            break
        if ch == left[ch]:
            out.append(ch)
        else:
            stack.append(right[ch])
            stack.append(left[ch])
    return bytes(out), pos


def bpe_encode(data: bytes) -> bytes:
    """One Gage BPE block: the most frequent pair takes a byte the data does not use, again and again."""
    if len(data) > 0xFFFF:
        raise ValueError("message too long for one BPE block")
    buf = list(data)
    used = set(buf)
    left = list(range(256))
    right = [0] * 256
    depth = [0] * 256
    free = [c for c in range(256) if c not in used]
    while free and len(buf) > 3:
        pairs = Counter(zip(buf, buf[1:]))
        best = None
        for (a, b), n in pairs.most_common():
            if n < 3:
                break
            if max(depth[a], depth[b]) + 1 <= MAX_DEPTH:
                best = (a, b)
                break
        if best is None:
            break
        code = free.pop(0)
        a, b = best
        left[code], right[code], depth[code] = a, b, max(depth[a], depth[b]) + 1
        out, i = [], 0
        while i < len(buf):
            if i + 1 < len(buf) and buf[i] == a and buf[i + 1] == b:
                out.append(code)
                i += 2
            else:
                out.append(buf[i])
                i += 1
        buf = out
    table = bytearray()
    c = 0
    while c < 256:
        run = 0
        while c + run < 256 and left[c + run] == c + run and run < 128:
            run += 1
        if run:
            table.append(127 + run)
            c += run
            if c == 256:
                break
            count = 1                    # after a skip the game reads one entry
        else:
            count = 0
            while c + count < 256 and count < 128 and (left[c + count] != c + count or (
                    c + count + 1 < 256 and left[c + count + 1] != c + count + 1)):
                count += 1
            count = max(count, 1)
            table.append(count - 1)
        for k in range(c, c + count):
            table.append(left[k])
            if left[k] != k:
                table.append(right[k])
        c += count
    return bytes(table) + struct.pack(">H", len(buf)) + bytes(buf)


# -- text <-> editor -----------------------------------------------------------------------------------


def to_editor(raw: bytes) -> str:
    """Message text bytes as the editor shows them."""
    out, at = [], 0
    for match in CODE_RE.finditer(raw):
        out.append(raw[at:match.start()].decode(ENCODING, "replace"))
        code = match.group(1)
        out.append("{" + (code.decode("latin-1") if code is not None else "~" + match.group(2).decode("latin-1")) + "}")
        at = match.end()
    out.append(raw[at:].decode(ENCODING, "replace"))
    text = "".join(out)
    return text.replace("{", "\x00").replace("}", "\x01") if False else text


def from_editor(text: str, missing: Optional[Set[str]] = None) -> bytes:
    """Editor text back to message bytes; characters cp1251 lacks become ``?`` (and go to ``missing``)."""
    out = bytearray()
    at = 0
    for match in TAG_RE.finditer(text):
        out += _encode(text[at:match.start()], missing)
        tag = match.group(1)
        if tag.startswith("~"):
            out += tag.encode("latin-1")
        elif tag.startswith("x"):
            out.append(int(tag[1:], 16))
        else:
            out += b"\\" + tag.encode("latin-1")
        at = match.end()
    out += _encode(text[at:], missing)
    return bytes(out)


def _encode(text: str, missing: Optional[Set[str]]) -> bytes:
    out = bytearray()
    for char in text.replace("\r\n", "\n"):
        try:
            out += char.encode(ENCODING)
        except UnicodeEncodeError:
            if missing is not None:
                missing.add(char)
            out += b"?"
    return bytes(out)


# -- packs and tables --------------------------------------------------------------------------------


@dataclass
class Message:
    table: int              # absolute offset of the string table
    index: int              # entry in the table
    start: int              # absolute offset of the stored message
    size: int
    head: bytes = b""       # decoded header (HEADER bytes)
    text: bytes = b""       # text bytes (no terminator)
    tail: bytes = b""       # bytes after the text (the zeros)


@dataclass
class TextFile:
    data: bytes
    kind: str                                       # "pak" or "dol"
    tables: List[int] = field(default_factory=list)  # absolute offsets of tables with text
    messages: Dict[int, List[Message]] = field(default_factory=dict)   # table -> its text messages
    pointers: List[Tuple[int, int, int, bool]] = field(default_factory=list)  # (entry at, base, target, sized)
    sizes: List[Tuple[int, int, int]] = field(default_factory=list)    # (size at, start, end)
    names: Dict[int, str] = field(default_factory=dict)

    def blocks(self) -> List[List[Message]]:
        return [self.messages[t] for t in self.tables]


def _is_pack(data: bytes, at: int, end: int) -> bool:
    return at + 8 <= end and _u32(data, at + 4) == PACK and 0 < _u32(data, at) < 10000 \
        and at + 8 + 8 * _u32(data, at) <= end


def _is_table(data: bytes, at: int, end: int) -> bool:
    return at + 8 <= end and _u32(data, at + 4) == TABLE and _u32(data, at) < 10000 \
        and at + 8 + 8 * _u32(data, at) <= end


def is_pack(data: bytes) -> bool:
    return _is_pack(data, 0, len(data))


def pack_members(data: bytes, magic: bytes, suffix: str, at: int = 0, end: Optional[int] = None,
                 prefix: str = "") -> List[Tuple[str, Tuple[int, int]]]:
    """``(name, (start, end))`` of every entry that starts with ``magic``, nested packs walked."""
    end = len(data) if end is None else end
    count = _u32(data, at)
    spans = sorted((_u32(data, at + 8 + 8 * i), i) for i in range(count) if _u32(data, at + 8 + 8 * i))
    bounds = [off for off, _i in spans] + [end - at]
    out = []
    for k, (off, i) in enumerate(spans):
        start, stop = at + off, at + bounds[k + 1]
        if data[start:start + len(magic)] == magic:
            out.append((f"{prefix}{i}{suffix}", (start, stop)))
        elif _is_pack(data, start, stop):
            out += pack_members(data, magic, suffix, start, stop, f"{prefix}{i}/")
    return out


def parse(data: bytes) -> TextFile:
    """A pack file (``EBootPak.bin``, a decompressed ``RmTxt*.cmp`` ...) with its text messages."""
    if not _is_pack(data, 0, len(data)):
        raise FormatError("not an Eternal Darkness pack (0x6B5)")
    tf = TextFile(bytes(data), "pak")
    _walk(tf, 0, len(data), "")
    return tf


def _walk(tf: TextFile, at: int, end: int, name: str) -> None:
    data = tf.data
    if _is_pack(data, at, end):
        count = _u32(data, at)
        spans = sorted((_u32(data, at + 8 + 8 * i), i) for i in range(count) if _u32(data, at + 8 + 8 * i))
        bounds = [off for off, _i in spans] + [end - at]
        for k, (off, i) in enumerate(spans):
            size = _u32(data, at + 12 + 8 * i)
            sized = size != 8 or not _is_table(data, at + off, end)
            tf.pointers.append((at + 8 + 8 * i, at, at + off, False))
            if sized:
                tf.sizes.append((at + 12 + 8 * i, at + off, at + off + size))
            _walk(tf, at + off, at + bounds[k + 1], f"{name}/{i}" if name else str(i))
        return
    if not _is_table(data, at, end):
        return
    count = _u32(data, at)
    texts = []
    for k in range(count):
        off, size = _u32(data, at + 8 + 8 * k), _u32(data, at + 12 + 8 * k)
        if not size:
            continue
        tf.pointers.append((at + 8 + 8 * k, at, at + off, True))
        blob = data[at + off:at + off + size]
        try:
            plain, used = bpe_decode(blob, 4)
        except (IndexError, FormatError):
            continue
        if used != size or len(plain) < HEADER + 1 or plain[16:20] != blob[:4]:
            continue
        body = plain[HEADER:]
        stop = body.find(b"\0")
        stop = len(body) if stop < 0 else stop
        texts.append(Message(at, k, at + off, size, plain[:HEADER], body[:stop], body[stop:]))
    if texts:
        tf.tables.append(at)
        tf.messages[at] = texts
        tf.names[at] = name


def encode_message(msg: Message, text: bytes) -> bytes:
    plain = msg.head + text + (msg.tail or b"\0\0")
    return plain[16:20] + bpe_encode(plain)


def build(tf: TextFile, new_texts: Dict[Tuple[int, int], bytes]) -> bytes:
    """The file with the messages ``(table, index) -> text bytes`` replaced; unchanged ones keep their bytes."""
    data = tf.data
    blobs: Dict[int, bytes] = {}           # message start -> new stored bytes
    every: Dict[int, Tuple[int, int]] = {}  # message start -> (start, size), every table entry
    for entry_at, base, target, is_message in tf.pointers:
        if is_message:
            every[target] = (target, _u32(data, entry_at + 4))
    for table, msgs in tf.messages.items():
        for msg in msgs:
            text = new_texts.get((table, msg.index))
            if text is not None and text != msg.text:
                blobs[msg.start] = encode_message(msg, text)
    if not blobs:
        return data
    # runs of messages stored back to back
    starts = sorted(every)
    runs: List[List[int]] = []
    for start in starts:
        if runs and every[runs[-1][-1]][0] + every[runs[-1][-1]][1] == start:
            runs[-1].append(start)
        else:
            runs.append([start])
    moves: List[Tuple[int, int]] = []       # (old end of run, delta)
    pieces: List[bytes] = []
    new_pos: Dict[int, int] = {}            # old message start -> new absolute start
    at = 0
    shift = 0
    for run in runs:
        if not any(s in blobs for s in run):
            continue
        run_start = run[0]
        run_end = every[run[-1]][0] + every[run[-1]][1]
        pieces.append(data[at:run_start])
        body = bytearray()
        for s in run:
            new_pos[s] = run_start + shift + len(body)
            body += blobs.get(s, data[s:s + every[s][1]])
        old_len = run_end - run_start
        delta = len(body) - old_len
        if delta % ALIGN:
            pad = ALIGN - delta % ALIGN
            body += bytes(pad)
            delta += pad
        pieces.append(bytes(body))
        moves.append((run_end, delta))
        shift += delta
        at = run_end
    pieces.append(data[at:])
    out = bytearray(b"".join(pieces))

    def moved(pos: int) -> int:
        return pos + sum(d for end, d in moves if end <= pos)

    def message_at(pos: int) -> Optional[int]:
        return new_pos.get(pos)

    for entry_at, base, target, is_message in tf.pointers:
        new_entry = moved(entry_at)
        new_base = moved(base)
        if is_message and target in new_pos:
            new_target = new_pos[target]
            struct.pack_into(">II", out, new_entry, new_target - new_base,
                             len(blobs.get(target, b"")) or every[target][1])
        else:
            struct.pack_into(">I", out, new_entry, moved(target) - new_base)
    for size_at, start, end in tf.sizes:
        struct.pack_into(">I", out, moved(size_at), moved(end) - moved(start))
    return bytes(out)


# -- main.dol ------------------------------------------------------------------------------------------

# Address ranges of main.dol (USA, GEDE01) with menu text: the cinematic list (chapter titles) and the
# "Eternal Mode" / record prompts. Each string keeps its slot (up to the next string), written in place.
DOL_RANGES = ((0x8023DCB4, 0x8023DD68), (0x8024BB00, 0x8024C0D0))
_DOL_TEXT_RE = re.compile(rb"[\x20-\x7e\n]{3,}")


def _dol_sections(dol: bytes):
    offs = struct.unpack_from(">18I", dol, 0)
    addrs = struct.unpack_from(">18I", dol, 0x48)
    sizes = struct.unpack_from(">18I", dol, 0x90)
    return [(o, a, s) for o, a, s in zip(offs, addrs, sizes) if s]


def dol_strings(dol: bytes) -> List[Tuple[int, int, bytes]]:
    """(file offset, slot size, text) of the menu strings in main.dol."""
    out = []
    for lo, hi in DOL_RANGES:
        for off, addr, size in _dol_sections(dol):
            if addr <= lo < addr + size:
                start, end = off + lo - addr, off + hi - addr
                for match in _DOL_TEXT_RE.finditer(dol, start, end):
                    begin = match.start()
                    if dol[begin - 1]:                  # strings start on 4 bytes after other data
                        begin = (begin + 3) & ~3
                    text = dol[begin:match.end()]
                    if len(text) < 3 or not re.search(rb"[a-z]{2}|[A-Z]{3}", text) or b"%" in text                             or b".c" in text or text.endswith((b".bin", b".tpl")):
                        continue
                    slot = len(text)
                    while begin + slot < end and dol[begin + slot] == 0:
                        slot += 1
                    out.append((begin, slot - 1, text))
    return out


def is_dol(data: bytes) -> bool:
    return len(data) > 0x100 and _u32(data, 0) == 0x100 and b"Eternal Mode" in data


def build_dol(dol: bytes, texts: List[bytes]) -> bytes:
    out = bytearray(dol)
    for (off, slot, old), new in zip(dol_strings(dol), texts):
        if new == old:
            continue
        if len(new) > slot:
            raise ValueError(f"main.dol string at 0x{off:x} has room for {slot} bytes, the text needs {len(new)}: "
                             f"{new.decode(ENCODING, 'replace')!r}")
        out[off:off + slot + 1] = new + bytes(slot + 1 - len(new))
    return bytes(out)
