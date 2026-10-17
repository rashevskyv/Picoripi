"""The members of a NARC archive (Nintendo DS) as bytes, in table order: the BTAF spans over the GMIF body.

Both Pokémon generation IV and V keep their message banks and pictures in NARCs. A member past the end of the GMIF
block is cut at the block end, as the zt scripts do.
"""
from __future__ import annotations

from core.i18n import tr
import struct
from typing import List


def narc_members(data: bytes) -> List[bytes]:
    """Every member of the NARC ``data``; ValueError when it has no BTAF or no GMIF block."""
    if data[:4] != b"NARC" or len(data) < 16:
        raise ValueError(tr("not a NARC archive"))
    spans, body, body_end = None, None, 0
    at = struct.unpack_from("<H", data, 12)[0]
    while at + 8 <= len(data):
        magic, size = struct.unpack_from("<4sI", data, at)
        if magic == b"BTAF":
            count = struct.unpack_from("<I", data, at + 8)[0]
            spans = [struct.unpack_from("<II", data, at + 12 + 8 * n) for n in range(count)]
        elif magic == b"GMIF":
            body, body_end = at + 8, at + size
        if size < 8:
            break
        at += size
    if spans is None or body is None:
        raise ValueError(tr("NARC without a BTAF or a GMIF block"))
    block = data[body:body_end]
    return [bytes(block[start:end]) for start, end in spans]
