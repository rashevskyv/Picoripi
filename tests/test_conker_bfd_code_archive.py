"""Conker's Bad Fur Day game archive: parse, identity rebuild, a grown code chunk that shifts the data section.

Synthetic chunks only (made-up bytes). The archive is placed in a blank cartridge image at its real ROM offset.
"""
import struct

import pytest

from plugins.conker_bfd import code_archive as ca, n64_archive as na

ROM_SIZE = 0x4000000


def _archive_bytes(chunks, data, gap=16):
    stored = []
    for chunk in chunks:
        blob = na.encode_rzip(chunk)
        stored.append(blob + b"\x00" * (len(blob) & 1))  # the real archive keeps every chunk start even
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


def test_a_re_encoded_chunk_keeps_its_slot_or_pads_to_even():
    assert ca._slot_fit(b"abc", 8) == b"abc" + b"\x00" * 5          # fits: the old slot length
    assert len(ca._slot_fit(b"a" * 9, 8)) == 10                    # grows past it: even length
    assert len(ca._slot_fit(b"a" * 10, 8)) == 10                   # grows, already even


def test_every_chunk_start_stays_even_after_a_grown_chunk():
    archive = ca.parse(_rom_with(_archive_bytes(CHUNKS, DATA)))
    for index, level in ((0, 0), (1, 1), (2, 9)):
        archive.set_chunk(index, archive.decoded(index), level=level)
    back = ca.parse(_rom_with(ca.build(archive)))
    assert back.decoded_code() == b"".join(CHUNKS)
    assert all(offset % 2 == 0 for offset in back.offsets)


def test_the_gap_after_the_code_keeps_its_original_bytes():
    archive = ca.parse(_rom_with(_archive_bytes(CHUNKS, DATA)))
    archive.padding = bytes([1, 2, 3]) + archive.padding[3:]
    rebuilt = ca.build(archive)
    gap = archive.offsets[-1]                 # offsets are relative to ARCHIVE_START, as is ``rebuilt``
    assert rebuilt[gap:gap + 3] == bytes([1, 2, 3])


def test_a_data_section_past_the_loader_end_is_refused(monkeypatch):
    archive = ca.parse(_rom_with(_archive_bytes(CHUNKS, DATA)))
    archive.set_chunk(1, archive.decoded(1), level=0)
    monkeypatch.setattr(ca, "LOADER_DATA_END", ca.ARCHIVE_START + 0x100)
    with pytest.raises(na.RomError):
        ca.build(archive)
