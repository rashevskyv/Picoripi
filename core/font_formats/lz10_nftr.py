"""NFTR (DS) fonts stored LZ10 compressed: Spirit Tracks keeps its ``Font/*.nftr`` as LZ10 streams.

The plain font is the ``nftr`` model (``core.font_formats.nftr``); this wrapper decompresses it and compresses the
edited font again. A font with nothing changed is written back as the original bytes.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from core.containers import lz10
from core.font_formats import Metadata, Sheets, nftr

ADDS_GLYPHS = nftr.ADDS_GLYPHS


def is_font(data: bytes) -> bool:
    try:
        return nftr.is_nftr(lz10.decompress(data)[0])
    except (ValueError, IndexError):
        return False


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    return nftr.extract(lz10.decompress(data)[0], params)


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    plain = lz10.decompress(original)[0]
    new = nftr.pack(metadata, sheets, plain, params)
    if new == plain:
        return bytes(original)
    return lz10.compress(new)
