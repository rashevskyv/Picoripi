"""GFAC archives with GFCP (BPE) payloads: the codec on synthetic data, block shapes, and refused inputs."""
import random
import struct

import pytest

from core.containers import gfac


def _skip_run_block() -> bytes:
    """One BPE block whose pair table reaches code 128 through a skip run, then identity entries to 255.

    Code 128 is the pair (0x41, 0x42). The tokens are 128, 0x43, 0x44, so the output is 41 42 43 44.
    """
    table = bytearray([255, 0x41, 0x42, 126])
    table += bytes(range(129, 256))
    return bytes(table) + struct.pack(">H", 3) + bytes([128, 0x43, 0x44])


def test_bpe_decodes_skip_run_pair_table():
    assert gfac.bpe_decode(_skip_run_block(), 4) == bytes([0x41, 0x42, 0x43, 0x44])


def test_bpe_round_trip_spans_more_than_one_block():
    rng = random.Random(7)
    data = bytes(rng.choice(b"abcde \n") for _ in range(gfac.BPE_BLOCK_SIZE * 2 + 1234))
    packed = gfac.bpe_encode(data)
    assert gfac.bpe_decode(packed, len(data)) == data
    assert len(packed) < len(data)


def test_bpe_block_with_every_byte_value_has_no_free_code():
    data = bytes(range(256)) * 3
    assert gfac.bpe_decode(gfac.bpe_encode(data), len(data)) == data


def test_bpe_block_without_repeated_pairs_stays_literal():
    data = bytes(range(0, 200, 2))
    assert gfac.bpe_decode(gfac.bpe_encode(data), len(data)) == data


def test_bpe_empty_input_round_trips():
    assert gfac.bpe_decode(gfac.bpe_encode(b""), 0) == b""


def test_truncated_bpe_payload_is_refused():
    data = b"hello hello hello hello hello"
    packed = gfac.bpe_encode(data)
    with pytest.raises(gfac.GfacError):
        gfac.bpe_decode(packed[:-3], len(data))


def test_size_mismatch_is_refused():
    packed = gfac.bpe_encode(b"abcabcabcabc")
    with pytest.raises(gfac.GfacError):
        gfac.bpe_decode(packed, 99)


def test_gfcp_round_trip_and_bad_magic():
    data = b"x" * 100 + b"yz" * 50
    assert gfac.gfcp_unpack(gfac.gfcp_pack(data), 0) == data
    assert gfac.gfcp_unpack(gfac.gfcp_pack(data, gfac.GFCP_TYPE_NONE), 0) == data
    with pytest.raises(gfac.GfacError):
        gfac.gfcp_unpack(b"NOPE" + b"\0" * 32, 0)


@pytest.mark.parametrize("version", [0x1, 0x200])
def test_gfac_round_trip_keeps_names_data_checksum_and_version(version):
    entries = [
        gfac.GfacEntry(name="message_a.bmg", data=b"MESGbmg1" + b"A" * 40, checksum=0x7691DCA2),
        gfac.GfacEntry(name="message_b.bmg", data=b"MESGbmg1" + b"B" * 21, checksum=0xB813F366),
        gfac.GfacEntry(name="c.bmg", data=b"", checksum=0),
    ]
    archive = gfac.GfacArchive(entries=entries, version=version)
    raw = gfac.write_gfac(archive)
    again = gfac.read_gfac(raw)
    assert again.version == version
    assert again.compressed is True
    assert [(e.name, e.data, e.checksum) for e in again.entries] == [
        (e.name, e.data, e.checksum) for e in entries]


def test_gfac_entries_start_on_32_byte_boundaries():
    entries = [gfac.GfacEntry(name="a.bmg", data=b"q" * 0x18), gfac.GfacEntry(name="b.bmg", data=b"r" * 0x40)]
    raw = gfac.write_gfac(gfac.GfacArchive(entries=entries))
    offsets = [struct.unpack_from("<I", raw, 0x30 + i * 16 + 12)[0] for i in range(2)]
    assert all(off % 0x20 == 0 for off in offsets)
    assert offsets[1] - offsets[0] == 0x20


def test_uncompressed_gfac_round_trip():
    entries = [gfac.GfacEntry(name="raw.bmg", data=b"MESG" * 9)]
    raw = gfac.write_gfac(gfac.GfacArchive(entries=entries, compressed=False))
    again = gfac.read_gfac(raw)
    assert again.compressed is False
    assert [e.data for e in again.entries] == [b"MESG" * 9]


def test_gfac_bad_magic_is_refused():
    with pytest.raises(gfac.GfacError):
        gfac.read_gfac(b"NOPE" + b"\0" * 0x80)
