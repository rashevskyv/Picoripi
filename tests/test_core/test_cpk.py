"""CPK reader on archives built in memory: the file base rule, the TOC at the end, and CRILAYLA streams.

No game bytes: every archive and stream is written here.
"""
import io
import struct

import pytest

from core.containers import cpk

PREFIX = bytes(range(256))


def _utf_table(columns, rows):
    """A ``@UTF`` table: ``columns`` is a list of (name, type code), ``rows`` a list of value tuples."""
    strings = bytearray(b"\0")

    def add_string(text):
        offset = len(strings)
        strings.extend(text.encode() + b"\0")
        return offset

    name_offsets = [add_string(name) for name, _ in columns]
    col_defs = b"".join(bytes([0x50 | kind]) + struct.pack(">I", off) for (_, kind), off in zip(columns, name_offsets))
    row_bytes = bytearray()
    for row in rows:
        for (_, kind), value in zip(columns, row):
            if kind == 0x0A:
                row_bytes += struct.pack(">I", add_string(value))
            elif kind == 0x04:
                row_bytes += struct.pack(">I", value)
            else:
                row_bytes += struct.pack(">Q", value)
    rows_at = 0x20 + len(col_defs)
    strings_at = rows_at + len(row_bytes)
    total = strings_at + len(strings)
    head = bytearray(0x20)
    head[0:4] = b"@UTF"
    struct.pack_into(">I", head, 4, total - 8)
    struct.pack_into(">H", head, 8 + 2, rows_at - 8)
    struct.pack_into(">I", head, 8 + 4, strings_at - 8)
    struct.pack_into(">I", head, 8 + 8, strings_at - 8)
    struct.pack_into(">H", head, 8 + 0x10, len(columns))
    struct.pack_into(">H", head, 8 + 0x12, sum(TYPE_WIDTH[kind] for _, kind in columns))
    struct.pack_into(">I", head, 8 + 0x14, len(rows))
    return bytes(head) + col_defs + bytes(row_bytes) + bytes(strings)


TYPE_WIDTH = {0x04: 4, 0x06: 8, 0x0A: 4}


def _build_cpk(entries, content_at, base):
    """A CPK with the TOC after the files (as in the game's data archives).

    ``entries`` is a list of (path, stored bytes, extract size). File offsets count from ``base``.
    """
    buf = bytearray(0x800)
    rows = []
    cursor = 0
    for path, payload, extract in entries:
        folder, _, name = path.rpartition("/")
        end = base + cursor + len(payload)
        if len(buf) < end:
            buf.extend(b"\0" * (end - len(buf)))
        buf[base + cursor:end] = payload
        rows.append((folder, name, cursor, len(payload), extract))
        cursor = (cursor + len(payload) + 0xF) & ~0xF
    toc_table = _utf_table(
        [("DirName", 0x0A), ("FileName", 0x0A), ("FileOffset", 0x06), ("FileSize", 0x04), ("ExtractSize", 0x04)],
        rows)
    toc = b"TOC " + bytes(0x10 - 4) + toc_table
    toc_at = (len(buf) + 0x7FF) & ~0x7FF
    buf.extend(b"\0" * (toc_at + len(toc) - len(buf)))
    buf[toc_at:toc_at + len(toc)] = toc
    header = _utf_table([("TocOffset", 0x06), ("TocSize", 0x04), ("ContentOffset", 0x06)],
                        [(toc_at, len(toc), content_at)])
    buf[0:4] = b"CPK "
    buf[0x10:0x10 + len(header)] = header
    return bytes(buf)


def _bits_of(byte):
    return [(byte >> (7 - i)) & 1 for i in range(8)]


def _literal_bits(byte):
    return [0] + _bits_of(byte)


COPY_DISTANCE_3_LENGTH_3 = [1] + [0] * 13 + [0, 0]


def _crilayla(bits, size, prefix=PREFIX):
    """A CRILAYLA stream: ``bits`` in read order; the bit stream is stored backwards from the prefix."""
    padded = bits + [0] * ((-len(bits)) % 8)
    read_bytes = [int("".join(map(str, padded[i:i + 8])), 2) for i in range(0, len(padded), 8)]
    stream = bytes(reversed(read_bytes))
    return b"CRILAYLA" + struct.pack("<II", size, len(stream)) + stream + prefix


def test_plain_and_compressed_entries_read_from_the_archive():
    # Body "CBA" repeated: three literals, then copies of distance 3. Long enough that the stored entry is smaller.
    body = b"CBA" * 40
    bits = []
    for byte in b"ABC":                       # written first: the last bytes of the body
        bits += _literal_bits(byte)
    for _ in range(39):
        bits += COPY_DISTANCE_3_LENGTH_3
    compressed = _crilayla(bits, len(body))
    archive = _build_cpk([("FIL/plain.dds", b"DDS hello", 9), ("FIL/layla.dds", compressed, 0x100 + len(body))],
                         content_at=0x2800, base=0x800)
    stream = io.BytesIO(archive)
    entries = cpk.read_cpk(stream)
    assert [e.path for e in entries] == ["FIL/plain.dds", "FIL/layla.dds"]
    assert entries[0].offset == 0x800
    assert entries[0].size == 9 and entries[0].extract_size == 9
    assert cpk.read_file(stream, entries[0]) == b"DDS hello"
    assert cpk.read_file(stream, entries[1]) == PREFIX + body


def test_file_base_is_the_content_area_when_it_lies_below_0x800():
    archive = _build_cpk([("a.bin", b"xyz", 3)], content_at=0x400, base=0x400)
    (entry,) = cpk.read_cpk(io.BytesIO(archive))
    assert entry.offset == 0x400
    stream = io.BytesIO(archive)
    assert cpk.read_file(stream, entry) == b"xyz"


def test_base_stays_0x800_when_the_content_area_lies_after_it_and_the_toc_at_the_end():
    archive = _build_cpk([("a.bin", b"xyz", 3)], content_at=0x16000, base=0x800)
    (entry,) = cpk.read_cpk(io.BytesIO(archive))
    assert entry.offset == 0x800


def test_crilayla_stream_must_be_used_up_exactly():
    bits = []
    for byte in b"ABC":
        bits += _literal_bits(byte)
    bits += COPY_DISTANCE_3_LENGTH_3
    good = _crilayla(bits, 6)
    assert cpk.crilayla_decompress(good, 0x106) == PREFIX + b"CBACBA"
    # The byte at 0x10 is read last; its low bits are the padding after the last value.
    tampered = bytearray(good)
    tampered[0x10] |= 0x01
    with pytest.raises(cpk.CpkError):
        cpk.crilayla_decompress(bytes(tampered), 0x106)


def test_crilayla_size_must_match_the_table():
    bits = []
    for byte in b"ABC":
        bits += _literal_bits(byte)
    bits += COPY_DISTANCE_3_LENGTH_3
    good = _crilayla(bits, 6)
    with pytest.raises(cpk.CpkError):
        cpk.crilayla_decompress(good, 0x107)


def test_read_cpk_rejects_a_missing_toc():
    with pytest.raises(cpk.CpkError):
        cpk.read_cpk(io.BytesIO(b"CPK " + bytes(0x2000)))
