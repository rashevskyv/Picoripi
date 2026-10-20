"""Conker's Bad Fur Day game archive: parse, identity rebuild, a grown code chunk that shifts the data section.

Synthetic chunks only (made-up bytes). The archive is placed in a blank cartridge image at its real ROM offset.
"""
import struct

import pytest

from plugins.conker_bfd import code_archive as ca, n64_archive as na

ROM_SIZE = 0x4000000


def _archive_bytes(chunks, data, gap=16):
    stored = [na.encode_rzip(c) for c in chunks]
    header = bytearray(0x800)
    starts, cursor = [], 0x800
    for blob in stored:
        starts.append(cursor)
        cursor += len(blob)
    code_end = cursor
    data_start = code_end + gap
    words = [data_start] + [s ^ ca.OFFSET_KEY for s in starts] + [code_end ^ ca.OFFSET_KEY]
    header[:len(words) * 4] = b"".join(struct.pack(">I", w) for w in words)
    body = bytearray(header)
    for blob in stored:
        body += blob
    body += b"\x00" * gap
    body += na.encode_rzip(data)
    return bytes(body)


def _rom_with(span):
    rom = bytearray(b"\xff") * ROM_SIZE
    rom[ca.ARCHIVE_START:ca.ARCHIVE_START + len(span)] = span
    return bytes(rom)


CHUNKS = [b"A" * 64 + b"tail-of-chunk-zero", bytes(range(200)) * 2, b"C" * 32]
DATA = b"synthetic data section, not game data" * 3


def test_identity_rebuild_is_byte_exact_and_decodes_the_same():
    rom = _rom_with(_archive_bytes(CHUNKS, DATA))
    archive = ca.parse(rom)
    assert archive.chunk_count == 3
    assert archive.decoded_code() == b"".join(CHUNKS)
    assert archive.data() == DATA
    assert ca.build(archive) == rom[ca.ARCHIVE_START:ca.ARCHIVE_END]


def test_a_grown_chunk_moves_the_data_section_and_keeps_every_chunk():
    rom = _rom_with(_archive_bytes(CHUNKS, DATA))
    archive = ca.parse(rom)
    payload = archive.decoded(1)
    archive.set_chunk(1, payload, level=0)           # stored deflate blocks: the stored chunk grows
    assert len(archive.changed[1]) != len(archive.stored[1])
    grown = _rom_with(ca.build(archive))
    back = ca.parse(grown)
    assert back.decoded_code() == b"".join(CHUNKS)
    assert back.data() == DATA
    assert back.data_start != ca.parse(rom).data_start    # the data section moved with the growth


def test_a_code_chunk_keeps_its_decoded_length():
    archive = ca.parse(_rom_with(_archive_bytes(CHUNKS, DATA)))
    with pytest.raises(na.RomError):
        archive.set_chunk(0, b"too short")
