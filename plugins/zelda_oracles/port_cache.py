"""Apply a translated ROM to the Oracles PC port's cache.

The port does not read the ROM after its first start. It keeps a per-game cache: ``rom.bin`` holds
the ROM with its code bytes set to zero, plus a manifest. A ROM with other bytes fails the port's
USA SHA-1 check, so the translated data goes into ``rom.bin`` directly.

Only data bytes can change. A code byte is zero in the cache but not in the clean ROM. So a byte
that differs between the clean ROM and the cache is code, and an edit there is refused.
Code bytes that were already zero in the clean ROM cannot be seen this way. The port's code map
would be needed to catch them, so this check is a safety net, not a proof.
"""
from __future__ import annotations


class CacheConflict(ValueError):
    """A translated byte sits on a code byte of the port cache."""


def _diff_offsets(a: bytes, b: bytes):
    if len(a) != len(b):
        raise CacheConflict(f"sizes differ: {len(a)} and {len(b)}")
    # Compare in chunks; most of a ROM is equal, so this keeps the loop short.
    chunk = 4096
    for start in range(0, len(a), chunk):
        if a[start:start + chunk] == b[start:start + chunk]:
            continue
        for offset in range(start, min(start + chunk, len(a))):
            if a[offset] != b[offset]:
                yield offset


def check_cache(clean_rom: bytes, cache_rom: bytes) -> int:
    """Return how many bytes the cache zeroed. Every other byte must equal the clean ROM."""
    zeroed = 0
    for offset in _diff_offsets(clean_rom, cache_rom):
        if cache_rom[offset] != 0:
            raise CacheConflict(f"cache byte 0x{offset:x} differs from the clean ROM and is not zero")
        zeroed += 1
    return zeroed


def apply_translation(clean_rom: bytes, translated_rom: bytes, cache_rom: bytes) -> bytes:
    """Return the cache's rom.bin with the translated data bytes written in.

    Raises CacheConflict when a changed byte is a zeroed code byte of the cache.
    """
    if not (len(clean_rom) == len(translated_rom) == len(cache_rom)):
        raise CacheConflict("clean ROM, translated ROM and cache must have the same size")
    out = bytearray(cache_rom)
    for offset in _diff_offsets(clean_rom, translated_rom):
        if cache_rom[offset] != clean_rom[offset]:
            raise CacheConflict(f"byte 0x{offset:x} is code in the port cache; the edit cannot be kept")
        out[offset] = translated_rom[offset]
    return bytes(out)


def changed_offsets(clean_rom: bytes, translated_rom: bytes):
    """Offsets where the translated ROM differs from the clean ROM (for reports)."""
    return list(_diff_offsets(clean_rom, translated_rom))
