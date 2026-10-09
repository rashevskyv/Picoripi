"""Dragon Quest VII (3DS) ``FPT0`` packs and the message text inside them.

A pack: ``FPT0``, u32 0, u32 count, u32 kind (1 text, 2 textures); ``count`` entries of 32 bytes (name[16],
u32 hash, u32 offset, u32 size, u32 flag); a block of 64 bytes (``TEMP/STEP1``, text packs) or 128 (texture packs);
the entries' data one after another. ``MESS/EN/#NNN000.fpt`` holds ``#NNNNNN.txt`` files, UTF-8 with CRLF:
a message is a header line ``#<window>[,<speaker>]`` and the lines up to the next header (CRLF is shown as a
line break, a lone LF as ``{LF}``). Texture packs hold
``texNNN.dmp`` (``core.texture_formats.dmp``) and a ``size.dat``.
"""
from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from core.containers.base_container import BaseArchiveContainer

MAGIC = b"FPT0"
CRLF = "\r\n"
LF_TAG = "{LF}"      # a lone LF inside a message (the game keeps both kinds of line break)


def decode_body(body: str) -> str:
    return body.replace(CRLF, "\0").replace("\n", LF_TAG).replace("\0", "\n")


def encode_body(text: str) -> str:
    return text.replace("\n", CRLF).replace(LF_TAG, "\n")


class FormatError(ValueError):
    pass


class Pack:
    """The entries of a pack, by name, in file order."""

    def __init__(self, raw: bytes) -> None:
        if raw[:4] != MAGIC or len(raw) < 16:
            raise FormatError("not an FPT0 pack")
        self.raw = raw
        count = struct.unpack_from("<I", raw, 8)[0]
        self.head = raw[:16]
        self.names: List[str] = []
        self.hashes: List[int] = []
        self.flags: List[int] = []
        self.data: Dict[str, bytes] = {}
        entries = []
        for i in range(count):
            at = 16 + i * 32
            name = raw[at:at + 16].rstrip(b"\0").decode("ascii", "replace")
            hash_, offset, size, flag = struct.unpack_from("<IIII", raw, at + 16)
            entries.append((name, hash_, offset, size, flag))
        kind = struct.unpack_from("<I", raw, 12)[0]
        block_size = 128 if kind == 2 else 64
        self.block = raw[16 + count * 32:16 + count * 32 + block_size]
        base = 16 + count * 32 + block_size
        end = 0
        for name, hash_, offset, size, flag in entries:
            self.names.append(name)
            self.hashes.append(hash_)
            self.flags.append(flag)
            self.data[name] = raw[base + offset:base + offset + size]
            end = max(end, offset + size)
        self.tail = raw[base + end:]      # padding after the last entry (texture packs)

    def build(self) -> bytes:
        out = bytearray(self.head)
        body = bytearray()
        for name, hash_, flag in zip(self.names, self.hashes, self.flags):
            data = self.data[name]
            out += name.encode("ascii").ljust(16, b"\0") + struct.pack("<IIII", hash_, len(body), len(data), flag)
            body += data
        return bytes(out + self.block + body + self.tail)


class FptContainer(BaseArchiveContainer):
    """A texture pack as an archive for Tools -> Textures (``member: *.dmp``)."""

    MAGIC = MAGIC

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return data[:4] == MAGIC and len(data) >= 16

    def __init__(self, data: bytes) -> None:
        self._pack = Pack(bytes(data))

    def list_files(self) -> List[str]:
        return list(self._pack.names)

    def read_file(self, path: str) -> bytes:
        return self._pack.data[path]

    def write_file(self, path: str, data: bytes) -> None:
        if path not in self._pack.data:
            raise KeyError(f"No {path} in the pack")
        self._pack.data[path] = bytes(data)

    def pack(self) -> bytes:
        return self._pack.build()


# ---------------------------------------------------------------- messages

Message = Tuple[str, str, str, bool]   # (entry name, header line, body with LF line breaks, body ended with CRLF)


def _segments(text: str) -> Tuple[str, List[Tuple[str, bool, str]]]:
    """``(lines before the first header, [(header, header has a line break, raw body)])`` of one txt entry."""
    starts = [0] if text.startswith("#") else []
    pos = 0
    while True:
        pos = text.find(CRLF + "#", pos)
        if pos < 0:
            break
        starts.append(pos + 2)
        pos += 2
    lead = text[:starts[0]] if starts else text
    segments = []
    for k, start in enumerate(starts):
        chunk = text[start:starts[k + 1] if k + 1 < len(starts) else len(text)]
        cut = chunk.find(CRLF)
        if cut < 0:
            segments.append((chunk, False, ""))
        else:
            segments.append((chunk[:cut], True, chunk[cut + 2:]))
    return lead, segments


def messages(pack: Pack) -> List[Message]:
    out: List[Message] = []
    for name in pack.names:
        _lead, segments = _segments(pack.data[name].decode("utf-8"))
        for header, _break, body in segments:
            newline = body.endswith(CRLF)
            out.append((name, header, decode_body(body[:-2] if newline else body), newline))
    return out


def texts(pack: Pack) -> List[str]:
    return [body for _name, _header, body, _nl in messages(pack)]


def rebuild(pack: Pack, new_texts: List[str]) -> bytes:
    """The pack with every message body replaced (headers, leading lines and line endings kept)."""
    found = messages(pack)
    if len(new_texts) != len(found):
        raise FormatError(f"{len(new_texts)} strings for {len(found)} messages")
    by_entry: Dict[str, List[str]] = {}
    for (name, _header, _body, _nl), text in zip(found, new_texts):
        by_entry.setdefault(name, []).append(str(text))
    for name, new in by_entry.items():
        lead, segments = _segments(pack.data[name].decode("utf-8"))
        parts = [lead]
        for (header, has_break, body), text in zip(segments, new):
            parts.append(header + (CRLF if has_break else ""))
            parts.append(encode_body(text) + (CRLF if body.endswith(CRLF) else ""))
        pack.data[name] = "".join(parts).encode("utf-8")
    return pack.build()
