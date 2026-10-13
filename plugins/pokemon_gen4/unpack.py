"""The files the unpack step takes from the Pokémon Diamond, Pearl, Platinum, HeartGold and SoulSilver ROM (USA): the
same set as zt/pkgen4.py.

Text: every NARC member that is a Gen 4 message bank goes to ``text/<narc>/NNNN.msg``; ``<narc>`` is the NitroFS path
with "/" replaced by "+" (``msgdata/msg.narc`` -> ``msgdata+msg.narc``). A NARC with a Gen 4 font bin (fonts) or with
an NCGR or LZ10 member (pictures, up to ``TEXTURE_NARC_MAX`` bytes) is kept whole at its NitroFS path.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from core.containers.narc_members import narc_members
from core.font_formats.gen4_glyphs import is_font_bin
from core.project_library import images
from plugins.common import gen4msg

TEXTURE_NARC_MAX = 6_500_000


def is_bank(data: bytes) -> bool:
    try:
        gen4msg.decode_bank(data)
    except (gen4msg.BankError, ValueError):
        return False
    return True


def _is_picture(member: bytes) -> bool:
    return member[:4] == b"RGCN" or member[:1] == b"\x10"


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
            if entry.size < 4 or image.read_at(entry.offset, 4) != b"NARC":
                continue
            data = image.read(entry)
            try:
                members = narc_members(data)
            except ValueError:
                continue
            banks = [(index, member) for index, member in enumerate(members) if is_bank(member)]
            if banks:
                for index, bank in banks:
                    _put(target_dir, f"text/{entry.path.replace('/', '+')}/{index:04d}.msg", bank)
            elif any(is_font_bin(member) for member in members) or (
                    len(data) <= TEXTURE_NARC_MAX and any(_is_picture(member) for member in members)):
                _put(target_dir, entry.path, data)
    return str(target_dir)
