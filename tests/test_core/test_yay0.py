import struct

import pytest

from core.containers.yay0 import decompress


def _yay0(size, mask_words, links, chunk):
    mask_bytes = b"".join(struct.pack(">I", word) for word in mask_words)
    link_bytes = b"".join(struct.pack(">H", link) for link in links)
    link_off = 16 + len(mask_bytes)
    chunk_off = link_off + len(link_bytes)
    header = b"Yay0" + struct.pack(">III", size, link_off, chunk_off)
    return header + mask_bytes + link_bytes + chunk


def test_yay0_literals_then_back_reference():
    # "ABC" as literals, then 6 bytes copied from 3 back.
    data = _yay0(9, [0xE0000000], [0x4002], b"ABC")
    assert decompress(data) == b"ABCABCABC"


def test_yay0_long_back_reference_reads_length_from_chunk():
    # "x" as a literal, then 20 bytes copied from 1 back (length nibble 0: chunk byte 2 + 0x12).
    data = _yay0(21, [0x80000000], [0x0000], b"x\x02")
    assert decompress(data) == b"x" * 21


def test_yay0_limit_stops_early():
    data = _yay0(9, [0xE0000000], [0x4002], b"ABC")
    assert decompress(data, limit=4) == b"ABCA"


def test_yay0_rejects_wrong_magic():
    with pytest.raises(ValueError):
        decompress(b"Yaz0" + b"\x00" * 12)



@pytest.mark.parametrize("payload", [b"", b"A", b"0123456789" * 7, bytes(range(256)) * 3])
def test_yay0_literal_compress_round_trips(payload):
    from core.containers.yay0 import compress

    assert decompress(compress(payload)) == payload
