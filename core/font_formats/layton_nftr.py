"""Professor Layton (Lost Future): an NFTR font stored BIOS compressed (``fnt/font_en1.cfnt``).

The plain font is the DS ``NFTR`` that ``core.font_formats.nftr`` reads; this wrapper decompresses it and
compresses the edited font again (LZ10, the original bytes when nothing changed).
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from core.containers import layton_ds
from core.font_formats import Metadata, Sheets, nftr

ADDS_GLYPHS = nftr.ADDS_GLYPHS


def is_font(data: bytes) -> bool:
    try:
        return nftr.is_nftr(layton_ds.decompress(data)[0])
    except (ValueError, IndexError):
        return False


def extract(data: bytes, params: Dict[str, Any]) -> Tuple[Metadata, Sheets]:
    return nftr.extract(layton_ds.decompress(data)[0], params)


def pack(metadata: Metadata, sheets: Sheets, original: bytes, params: Dict[str, Any]) -> bytes:
    plain, _prefix = layton_ds.decompress(original)
    new = nftr.pack(metadata, sheets, plain, params)
    return layton_ds.recompress(original, new)
