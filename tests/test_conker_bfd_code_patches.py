"""Data-driven code patches on the synthetic game archive: identity, applied patch, expected-byte check. Synthetic bytes."""
import struct

import pytest

from plugins.conker_bfd import code_archive as ca, code_patches as cp, n64_archive as na

ROM_SIZE = 0x4000000
CHUNKS = [b"A" * 64 + b"tail-of-chunk-zero", bytes(range(200)) * 2, b"C" * 32]
DATA = b"synthetic data section, not game data" * 3


def _archive_bytes():
    stored = []
    for chunk in CHUNKS:
        blob = na.encode_rzip(chunk)
        stored.append(blob + b"\x00" * (len(blob) & 1))
    header = bytearray(0x800)
    starts, cursor = [], 0x800
    for blob in stored:
        starts.append(cursor)
        cursor += len(blob)
    code_end = cursor
    data_start = code_end + 16
    words = [data_start] + [s ^ ca.OFFSET_KEY for s in starts] + [code_end ^ ca.OFFSET_KEY]
    header[:len(words) * 4] = b"".join(struct.pack(">I", w) for w in words)
    body = bytearray(header)
    for blob in stored:
        body += blob
    body += b"\x00" * 16 + na.encode_rzip(DATA)
    return bytes(body)


def _rom():
    rom = bytearray(b"\xff") * ROM_SIZE
    span = _archive_bytes()
    rom[ca.ARCHIVE_START:ca.ARCHIVE_START + len(span)] = span
    return bytes(rom)


def test_no_patches_returns_the_same_rom_object():
    rom = _rom()
    assert cp.apply_to_rom(rom, ()) is rom


def test_a_matching_patch_changes_only_its_chunk_bytes():
    rom = _rom()
    old = CHUNKS[1][10:14]
    patch = cp.CodePatch(chunk=1, offset=10, expected=old, new=b"\x01\x02\x03\x04", note="synthetic")
    patched = cp.apply_to_rom(rom, (patch,))
    back = ca.parse(patched)
    assert back.decoded(1)[10:14] == b"\x01\x02\x03\x04"
    assert back.decoded(0) == CHUNKS[0] and back.decoded(2) == CHUNKS[2]
    assert back.data() == DATA


def test_expected_bytes_that_differ_are_refused():
    rom = _rom()
    patch = cp.CodePatch(chunk=1, offset=10, expected=b"\xee\xee\xee\xee", new=b"\x01\x02\x03\x04", note="synthetic")
    with pytest.raises(na.RomError):
        cp.apply_to_rom(rom, (patch,))


def test_a_patch_outside_the_archive_is_refused():
    archive = ca.parse(_rom())
    patch = cp.CodePatch(chunk=9, offset=0, expected=b"A", new=b"B", note="synthetic")
    with pytest.raises(na.RomError):
        cp.apply_to_archive(archive, (patch,))
