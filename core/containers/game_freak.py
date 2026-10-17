"""Game Freak path hashes: FNV-1a 64 with Game Freak's offset basis, used by GFLXPACK packs and Trinity indexes."""

_BASIS = 0xCBF29CE484222645    # Game Freak's offset basis (not the standard FNV-1a basis)
_PRIME = 0x100000001B3


def path_hash(path: str) -> int:
    """The hash of ``path`` (e.g. ``bin/appli/<folder>/bin/<layout>_eng.arc``)."""
    value = _BASIS
    for byte in path.encode("utf-8"):
        value = ((value ^ byte) * _PRIME) & 0xFFFFFFFFFFFFFFFF
    return value
