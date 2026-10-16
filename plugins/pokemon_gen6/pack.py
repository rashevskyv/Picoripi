"""Member helpers of the Pokémon X/Y and Omega Ruby/Alpha Sapphire GARCs (generation 6, 3DS).

A GARC file's English subfile (bit 2) is either a plain file or a "pack": a u32 count, that many 64-byte names, then a
DARC archive of pictures and layouts. ``english_members`` gives the English members of one GARC file as
``{relative name: bytes}``; a pack holds its DARC members, and a pack whose pictures equal the French ones is skipped.
Same rules as ``zt/pkgen6.py`` (``darc_files``, ``pack_darc_at``, ``member_ext``, ``_english_members``).
"""
from __future__ import annotations

import struct
from typing import Dict

from plugins.common.darc_pack import darc_files, pack_darc_at
from plugins.common.garc import Garc, unwrap

EN, FR = 2, 3


def member_ext(plain: bytes) -> str:
    if plain[:4] == b"CFNT":
        return ".bcfnt"
    if len(plain) >= 0x28 and plain[-0x28:-0x24] == b"CLIM":
        return ".bclim"
    if len(plain) >= 0x14 and struct.unpack_from("<HHIII", plain)[4] == 0x10:
        return ".dat"
    return ".bin"


def english_members(garc: Garc, index: int) -> Dict[str, bytes]:
    """``{relative path: bytes}`` of the English subfile of ``index``: the whole file, or the pack members that
    differ from the French ones (the same picture in every language is an icon, not text)."""
    bits = garc.bits(index)
    bit = EN if EN in bits else 0
    plain, _ = unwrap(garc.stored(index, bit))
    stem = f"{index:03d}" + (f".{bit}" if len(bits) > 1 else "")
    at = pack_darc_at(plain)
    if at is None:
        return {stem + member_ext(plain): plain}
    other: Dict[str, bytes] = {}
    if FR in bits and bit == EN:
        other_plain, _ = unwrap(garc.stored(index, FR))
        other_at = pack_darc_at(other_plain)
        if other_at is not None:
            other = {path: other_plain[other_at + off:other_at + off + size]
                     for path, (off, size) in darc_files(other_plain[other_at:]).items()}
    darc = plain[at:]
    return {f"{stem}/{path}": darc[off:off + size] for path, (off, size) in darc_files(darc).items()
            if darc[off:off + size] != other.get(path)}
