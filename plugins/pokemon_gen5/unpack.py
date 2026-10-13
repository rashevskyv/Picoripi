"""The files the unpack step takes from the Pokémon Black, White, Black 2 and White 2 ROM (USA): the same set as
zt/pkgen5.py.

Text: every NARC member that is a Gen 5 message file with lines goes to ``text/<narc>/NNNN.msg``; ``<narc>`` is the
NitroFS path with "/" replaced by "_" (``a/0/0/2`` -> ``a_0_0_2``). A NARC with NFTR fonts (an ``RTFN`` member) or with
NCGR pictures (an ``RGCN`` member, up to ``TEXTURE_NARC_MAX`` bytes) is kept whole at its NitroFS path, and so is
``gfl_font.dat`` at the root.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Callable, Optional

from core.containers.narc_members import narc_members
from core.project_library import images
from plugins.common import gen5msg

TEXTURE_NARC_MAX = 6_500_000
ROOT_FILES = ("gfl_font.dat",)


def line_count(data: bytes) -> int:
    """The lines of a Gen 5 message file; 0 when ``data`` is not one or has no lines."""
    if not gen5msg.is_gen5msg(data):
        return 0
    try:
        return len(gen5msg.read(data))
    except (ValueError, struct.error):
        return 0


def _put(target_dir: str, rel: str, data: bytes) -> None:
    out = Path(target_dir).joinpath(*rel.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    with images.open_image(base) as image:
        entries = image.entries()
        for number, entry in enumerate(entries, 1):
            if is_cancelled():
                return None
            progress(100 * number // len(entries), entry.path)
            if entry.path in ROOT_FILES:
                _put(target_dir, entry.path, image.read(entry))
                continue
            if entry.size < 4 or image.read_at(entry.offset, 4) != b"NARC":
                continue
            data = image.read(entry)
            try:
                members = narc_members(data)
            except ValueError:
                continue
            banks = [(index, member) for index, member in enumerate(members) if line_count(member) > 0]
            if banks:
                for index, bank in banks:
                    _put(target_dir, f"text/{entry.path.replace('/', '_')}/{index:04d}.msg", bank)
            elif any(member[:4] == b"RTFN" for member in members) or (
                    len(data) <= TEXTURE_NARC_MAX and any(member[:4] == b"RGCN" for member in members)):
                _put(target_dir, entry.path, data)
    return str(target_dir)
