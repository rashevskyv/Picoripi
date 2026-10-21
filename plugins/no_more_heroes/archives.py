"""The U8 archives of No More Heroes: the HOME Menu's ``homeBtn_ENG.arc`` and the channel banner ``opening.bnr``.

An archive is taken apart into a folder named like the file. Its LZ77 (type 0x10), IMET (channel banner) and IMD5
wrappers are taken off first, and only the picture members are kept. ``replace`` puts one member back and wraps the
archive again. The U8 reading and writing is core's ``U8Container``; the wrappers are core's LZ77.
"""
from __future__ import annotations

import hashlib
import struct
from typing import Callable, Optional, Tuple

from core.containers import lz10
from core.containers.u8_container import U8Container
from core.i18n import tr

U8_MAGIC = b"\x55\xaa\x38\x2d"
MEMBERS = (".tpl", ".brfnt", ".csv")


def unwrap(raw: bytes) -> Optional[Tuple[bytes, Callable[[bytes], bytes]]]:
    """``(inner U8, inner -> stored bytes)`` for a U8, a channel banner (IMET header), an IMD5 member or an LZ77
    stream of a U8; None when ``raw`` is none of them."""
    if raw[:4] == U8_MAGIC:
        return raw, lambda new: new
    if raw[0x40:0x44] == b"IMET" and raw[0x600:0x604] == U8_MAGIC:
        head = raw[:0x600]
        return raw[0x600:], lambda new: head + new
    if raw[:4] == b"IMD5" and raw[32:36] == b"LZ77":
        def imd5(new: bytes) -> bytes:
            payload = b"LZ77" + lz10.compress(new)
            return b"IMD5" + struct.pack(">I", len(payload)) + bytes(8) + hashlib.md5(payload).digest() + payload
        return lz10.decompress(raw, 36)[0], imd5
    if raw[:1] == b"\x10" and len(raw) > 8:
        try:
            inner = lz10.decompress(raw)[0]
        except ValueError:
            return None
        if inner[:4] == U8_MAGIC:
            return inner, lz10.compress
    return None


def explode(raw: bytes, prefix: str, put: Callable[[str, bytes], None]) -> None:
    """Hand every picture member of the archive ``raw`` (nested archives included) to ``put(path, data)``."""
    found = unwrap(raw)
    if found is None:
        raise ValueError(tr("{0} is not an archive", prefix))
    arc = U8Container(found[0])
    for member in arc.list_files():
        data = arc.read_file(member)
        inner = unwrap(data)
        if inner is not None and inner[0][:4] == U8_MAGIC:      # an IMD5 member may hold sound, not an archive
            explode(data, f"{prefix}/{member}", put)
        elif member.lower().endswith(MEMBERS):
            put(f"{prefix}/{member}", data)


def replace(raw: bytes, path: str, new: bytes) -> bytes:
    """``raw`` (an archive, maybe wrapped) with member ``path`` (maybe inside nested archives) set to ``new``."""
    inner, wrap = unwrap(raw)
    arc = U8Container(inner)
    parts = path.split("/")
    for cut in range(len(parts), 0, -1):
        member = "/".join(parts[:cut])
        if member in arc.list_files():
            rest = "/".join(parts[cut:])
            if rest:
                arc.write_file(member, replace(arc.read_file(member), rest, new))
            else:
                arc.write_file(member, new)
            return wrap(arc.pack())
    raise ValueError(tr("{0} is not a member of the archive", path))
