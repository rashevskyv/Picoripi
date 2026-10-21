"""Data-driven patches of the US code (decoded code chunks) and the archive that stores them.

Each patch names a decoded code chunk, an offset inside it, the bytes that must be there (checked first) and the new
bytes. An empty list leaves the ROM unchanged. Patches keep the decoded length; the archive is rebuilt by
``code_archive.build``, which keeps the chunk slots, even starts and the header of the loader.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from . import code_archive as ca, n64_archive as na


@dataclass(frozen=True)
class CodePatch:
    chunk: int
    offset: int
    expected: bytes
    new: bytes
    note: str


PATCHES: Tuple[CodePatch, ...] = ()


@dataclass(frozen=True)
class RomPatch:
    """A patch of raw ROM bytes (boot code outside the compressed archive), checked before the write."""
    offset: int
    expected: bytes
    new: bytes
    note: str


def apply_raw(rom: bytes, patches: Tuple[RomPatch, ...]) -> bytes:
    """Return the ROM with the raw patches applied. The same object comes back when there are none."""
    if not patches:
        return rom
    out = bytearray(rom)
    for patch in patches:
        if len(patch.expected) != len(patch.new):
            raise na.RomError(f"raw patch at {patch.offset:#x} changes its length")
        end = patch.offset + len(patch.expected)
        if end > len(out):
            raise na.RomError(f"raw patch at {patch.offset:#x} lies outside the ROM")
        if bytes(out[patch.offset:end]) != patch.expected:
            raise na.RomError(f"raw patch at {patch.offset:#x}: bytes differ ({patch.note})")
        out[patch.offset:end] = patch.new
    return bytes(out)


def apply_to_archive(archive: ca.Archive, patches: Tuple[CodePatch, ...] = PATCHES) -> int:
    """Apply the patches to the archive's decoded chunks. Raises ``RomError`` when expected bytes differ."""
    applied = 0
    for patch in patches:
        if not 0 <= patch.chunk < archive.chunk_count:
            raise na.RomError(f"code patch names chunk {patch.chunk}, outside the archive")
        if len(patch.expected) != len(patch.new):
            raise na.RomError(f"code patch at chunk {patch.chunk} changes its length")
        payload = bytearray(archive.decoded(patch.chunk))
        end = patch.offset + len(patch.expected)
        if end > len(payload):
            raise na.RomError(f"code patch at chunk {patch.chunk} runs past the chunk")
        if bytes(payload[patch.offset:end]) != patch.expected:
            raise na.RomError(f"code patch at chunk {patch.chunk} offset {patch.offset:#x}: bytes differ ({patch.note})")
        payload[patch.offset:end] = patch.new
        archive.set_chunk(patch.chunk, bytes(payload))
        applied += 1
    return applied


def apply_to_rom(rom: bytes, patches: Tuple[CodePatch, ...] = PATCHES) -> bytes:
    """Return the ROM with the code patches applied. The same object comes back when there are none."""
    if not patches:
        return rom
    archive = ca.parse(rom)
    apply_to_archive(archive, patches)
    out = bytearray(rom)
    out[ca.ARCHIVE_START:ca.ARCHIVE_END] = ca.build(archive)
    return bytes(out)
