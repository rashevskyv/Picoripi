"""AKLZ (Skies of Arcadia Legends) LZSS codec: hand-built streams, round trip, and an optional real file."""
import os
import random
import struct

import pytest

from core.containers import aklz

CONST = aklz.CONSTANT_WORDS


def _file(size: int, stream: bytes) -> bytes:
    return aklz.MAGIC + CONST + struct.pack(">I", size) + stream


def test_literal_stream_decodes_in_flag_order():
    # flags 0b111 (LSB first): three literals
    assert aklz.decode(_file(3, b"\x07abc")) == b"abc"


def test_reference_copies_from_ring_start_and_overlaps_its_own_output():
    # literals A, B, then a reference to ring index 0xFEE (= output 0), length 3.
    # The third copied byte is the first one the copy itself wrote: "AB" + "ABA".
    stream = b"\x03" + b"AB" + b"\xee\xf0"
    assert aklz.decode(_file(5, stream)) == b"ABABA"


def test_decode_rejects_truncated_stream():
    with pytest.raises(ValueError):
        aklz.decode(_file(10, b"\x07abc"))


def test_round_trip_random_and_repetitive():
    rng = random.Random(7)
    samples = [b"", b"x", bytes(rng.randrange(256) for _ in range(5000)),
               b"Vyse\x7fsays\n" * 400, bytes(9000)]
    for body in samples:
        packed = aklz.encode(body)
        assert packed[:4] == aklz.MAGIC
        assert aklz.decode(packed) == body


def test_repetitive_data_gets_smaller():
    body = rb"\h(\x81sVyse\x81t)Hey there.\e" * 200
    assert len(aklz.encode(body)) < len(body) // 2


REAL = os.environ.get("PICORIPI_SKIES_LEGENDS_ME002A", "")


@pytest.mark.skipif(not REAL or not os.path.isfile(REAL), reason="real Skies of Arcadia Legends file not set")
def test_real_file_decodes_to_declared_size_and_round_trips():
    data = open(REAL, "rb").read()
    body = aklz.decode(data)
    assert len(body) == aklz.decompressed_size(data)
    assert aklz.decode(aklz.encode(body)) == body
