"""WIA and RVZ reader on synthetic images: a small writer in this file builds every method, junk packing, zero groups and
the refusals, and each decoded image is compared byte for byte with the plain image it came from."""
import bz2
import io
import lzma
import random
import struct

import pytest

from core import zstd_frame
from core.containers import wia
from core.containers.gcm_writer import write_disc
from core.containers.image_files import ImageError
from core.project_library import images
from gc_disc import build_disc

NONE, PURGE, BZIP2, LZMA, LZMA2, ZSTD = range(6)
MIB2 = 0x200000
HEAD_LEN = 0x48 + 0xDC


def spec_junk(seed: bytes, offset: int, size: int) -> bytes:
    """A literal transcription of the RVZ spec's PRNG (independent of wia._Lfg): no shortcuts."""
    buf = list(struct.unpack(">17I", seed)) + [0] * (521 - 17)
    for i in range(17, 521):
        buf[i] = ((buf[i - 17] << 23) ^ (buf[i - 16] >> 9) ^ buf[i - 1]) & 0xFFFFFFFF

    def advance():
        for i in range(32):
            buf[i] ^= buf[i + 521 - 32]
        for i in range(32, 521):
            buf[i] ^= buf[i - 32]

    for _ in range(4):
        advance()
    word = 0

    def next_word():
        nonlocal word
        if word == 521:
            advance()
            word = 0
        value = buf[word]
        word += 1
        return value

    for _ in range((offset % 0x8000) // 4):
        next_word()
    out = bytearray()
    while len(out) < size:
        x = next_word()
        out += bytes([x >> 24, (x >> 18) & 0xFF, (x >> 8) & 0xFF, x & 0xFF])
    return bytes(out[:size])


def _compress(method: int, data: bytes):
    """(compressed bytes, compr_data props) for the method; the props are the same for every stream of one image."""
    if method == NONE:
        return data, b""
    if method == BZIP2:
        return bz2.compress(data), b""
    if method == LZMA:
        filters = [{"id": lzma.FILTER_LZMA1, "lc": 3, "lp": 0, "pb": 2, "dict_size": 1 << 20}]
        props = bytes([(2 * 5 + 0) * 9 + 3]) + struct.pack("<I", 1 << 20)
        return lzma.compress(data, format=lzma.FORMAT_RAW, filters=filters), props
    if method == LZMA2:
        filters = [{"id": lzma.FILTER_LZMA2, "dict_size": 1 << 20}]
        return lzma.compress(data, format=lzma.FORMAT_RAW, filters=filters), bytes([16])   # 2 << 19 = 1 MiB
    if method == ZSTD:
        return zstd_frame.compress(data, "test"), b""
    raise AssertionError(method)


def build_wia(image: bytes, *, rvz: bool, method: int, chunk: int, junk=(), disc_type: int = 1,
              compression_field: int = None, dhead: bytes = None, stored=None) -> bytes:
    """A WIA or RVZ file of ``image``. ``junk`` lists (start, end, seed) regions that RVZ packs as seeds: each lies in
    one group and its bytes are the spec's PRNG output from its seed at its start. ``stored`` ({group: bytes}) puts
    other plain bytes into a group (in RVZ as its packed data), to build a hostile image.

    Layout: header, raw data table, group data, group table (last, so the data offsets are known when it is written).
    """
    method_field = method if compression_field is None else compression_field
    count = -(-len(image) // chunk)
    props = b""
    data_area = bytearray()
    raw_entry = struct.pack(">QQII", 0, len(image), 0, count)
    raw_table, props = _compress(method, raw_entry)   # the props are the same for every stream of this method
    raw_len = len(raw_table)
    raw_table = bytes(raw_table) + b"\0" * (-raw_len % 4)
    data_base = HEAD_LEN + len(raw_table)            # group data starts after the header and the raw table
    entries = []
    for index in range(count):
        start = index * chunk
        logical = image[start:start + chunk]
        if not any(logical):
            entries.append((0, 0, 0))   # every byte of this group is zero
            continue
        here = sorted((s, e, seed) for s, e, seed in junk if start <= s < start + chunk)
        packed = b""
        if rvz and here:
            parts = bytearray()
            pos = start
            for s, e, seed in here:
                assert e <= start + chunk, "a junk region crosses a group"
                if pos < s:
                    literal = image[pos:s]
                    parts += struct.pack(">I", len(literal)) + literal
                parts += struct.pack(">I", (e - s) | wia.JUNK_FLAG) + seed
                pos = e
            if pos < start + chunk:
                literal = image[pos:start + chunk]
                parts += struct.pack(">I", len(literal)) + literal
            packed = bytes(parts)
        plain = packed if packed else logical
        if stored and index in stored:
            plain = stored[index]
            packed = plain if rvz else b""
        compressed = method != NONE and (not rvz or index % 2 == 0)
        data = _compress(method, plain)[0] if compressed else plain
        while len(data_area) % 4:
            data_area.append(0)
        off4 = (data_base + len(data_area)) // 4
        if rvz:
            flag = wia.JUNK_FLAG if compressed else 0
            entries.append((off4, len(data) | flag, len(packed)))
        else:
            entries.append((off4, len(data), 0))
        data_area += data
    group_plain = b"".join(struct.pack(">III", o, f, p) if rvz else struct.pack(">II", o, f)
                           for o, f, p in entries)
    group_table, _ = _compress(method, group_plain)
    group_off = data_base + len(data_area)          # the group table comes last; its place is known now
    body = bytearray(raw_table) + bytes(data_area) + group_table

    head = bytearray(HEAD_LEN)
    head[0:4] = wia.MAGIC_RVZ if rvz else wia.MAGIC_WIA
    struct.pack_into(">I", head, 4, 0x01000000)
    struct.pack_into(">I", head, 8, 0x00090000)
    struct.pack_into(">Q", head, 0x24, len(image))
    struct.pack_into(">Q", head, 0x2C, HEAD_LEN + len(body))
    disc = 0x48
    struct.pack_into(">IIII", head, disc, disc_type, method_field, 0, chunk)
    head[disc + 0x10:disc + 0x10 + 0x80] = (dhead if dhead is not None else image[:0x80])
    struct.pack_into(">I", head, disc + 0x90, 0)   # n_part: no Wii partitions
    struct.pack_into(">I", head, disc + 0xB4, 1)
    struct.pack_into(">QI", head, disc + 0xB8, HEAD_LEN, raw_len)
    struct.pack_into(">I", head, disc + 0xC4, count)
    struct.pack_into(">QI", head, disc + 0xC8, group_off, len(group_table))
    head[disc + 0xD4] = len(props)
    head[disc + 0xD5:disc + 0xD5 + len(props)] = props
    return bytes(head) + bytes(body)


def _random(size: int, seed: int = 1) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(size))


def _rvz_image(chunk: int):
    """Four groups: literal data, a zero group, a group with a junk region at its start, and one with a junk region
    starting in the middle of its chunk. The junk bytes are the spec's PRNG output from the seeds, so the reader must
    reproduce them from the seeds alone."""
    rng = random.Random(7)
    image = bytearray(rng.getrandbits(8) & 0x3F for _ in range(4 * chunk))
    image[:0x80] = bytes(range(0x80))
    image[chunk:2 * chunk] = bytes(chunk)
    seed_a = bytes(rng.getrandbits(8) for _ in range(68))
    seed_b = bytes(rng.getrandbits(8) for _ in range(68))
    a = 2 * chunk
    b = 3 * chunk + 0x8000
    image[a:a + 0x10000] = spec_junk(seed_a, a, 0x10000)
    image[b:b + 0x10000] = spec_junk(seed_b, b, 0x10000)
    return bytes(image), [(a, a + 0x10000, seed_a), (b, b + 0x10000, seed_b)]


@pytest.mark.parametrize("method", [NONE, BZIP2, LZMA, LZMA2, ZSTD])
def test_rvz_round_trip_with_junk_packing_for_every_method(method):
    image, junk = _rvz_image(0x20000)
    data = build_wia(image, rvz=True, method=method, chunk=0x20000, junk=junk)
    with wia.WiaStream(io.BytesIO(data)) as stream:
        assert stream.size == len(image)
        assert stream.read() == image


@pytest.mark.parametrize("method", [NONE, BZIP2, LZMA, LZMA2])
def test_wia_round_trip_with_two_mib_chunks(method):
    image = bytearray(_random(2 * MIB2 + 0x18000, seed=5))
    image[MIB2 // 2:MIB2] = bytes(MIB2 // 2)   # a zero stretch inside the first group
    image = bytes(image)
    data = build_wia(image, rvz=False, method=method, chunk=MIB2)
    with wia.WiaStream(io.BytesIO(data)) as stream:
        assert stream.read() == image


def test_random_reads_match_the_plain_image():
    image, junk = _rvz_image(0x20000)
    stream = wia.WiaStream(io.BytesIO(build_wia(image, rvz=True, method=LZMA2, chunk=0x20000, junk=junk)))
    rng = random.Random(3)
    for _ in range(60):
        start = rng.randrange(len(image))
        size = rng.randrange(1, 0x9000)
        stream.seek(start)
        assert stream.read(size) == image[start:start + size]
    stream.seek(-10, 2)
    assert stream.read(100) == image[-10:]


def test_the_junk_generator_matches_the_literal_spec_transcription():
    seed = bytes(range(68))
    for offset, size in ((0, 3000), (0x8000, 4500), (0x12340, 2100), (0x1F8000, 9000)):
        assert wia.junk_bytes(seed, offset, size) == spec_junk(seed, offset, size)


def test_the_first_0x80_bytes_come_from_the_header_not_from_the_groups():
    image, junk = _rvz_image(0x20000)
    header = bytes([0xAA]) * 0x80
    data = build_wia(image, rvz=True, method=NONE, chunk=0x20000, junk=junk, dhead=header)
    with wia.WiaStream(io.BytesIO(data)) as stream:
        assert stream.read(0x100) == header + image[0x80:0x100]


def test_a_wii_image_is_refused_with_its_reason():
    data = build_wia(_random(0x8000), rvz=True, method=NONE, chunk=0x8000, disc_type=2)
    with pytest.raises(ImageError, match="Wii"):
        wia.WiaStream(io.BytesIO(data))


def test_the_purge_method_is_refused():
    data = build_wia(_random(0x8000), rvz=False, method=NONE, chunk=MIB2, compression_field=PURGE)
    with pytest.raises(ImageError, match="Purge"):
        wia.WiaStream(io.BytesIO(data))


def test_a_wia_chunk_that_is_not_two_mib_is_refused():
    data = build_wia(_random(0x8000), rvz=False, method=NONE, chunk=0x8000)
    with pytest.raises(ImageError, match="multiple of 2 MiB"):
        wia.WiaStream(io.BytesIO(data))


def test_an_rvz_is_identified_as_its_gamecube_disc_and_extracts_the_same_files(tmp_path):
    disc = build_disc({"data/a.bin": b"A" * 300, "data/b.bin": bytes(range(200))}, game_id=b"GMSE01")
    rvz = tmp_path / "game.rvz"
    rvz.write_bytes(build_wia(disc, rvz=True, method=LZMA2, chunk=0x8000))
    found = images.identify(rvz)
    assert found["kind"] == images.KIND_GC and found["game_id"] == "GMSE01" and found["revision"] == 0
    out = tmp_path / "out"
    images.extract(rvz, out, lambda p, t: None, lambda: False)
    assert (out / "files/data/a.bin").read_bytes() == b"A" * 300
    assert (out / "files/data/b.bin").read_bytes() == bytes(range(200))


def test_the_disc_writer_copies_an_rvz_source_as_its_disc(tmp_path):
    disc = build_disc({"data/a.bin": b"A" * 300}, game_id=b"GMSE01")
    rvz = tmp_path / "game.rvz"
    rvz.write_bytes(build_wia(disc, rvz=True, method=BZIP2, chunk=0x8000))
    out = tmp_path / "out.iso"
    write_disc(rvz, out, {}, lambda p, t: None, lambda: False)
    assert out.read_bytes() == disc
    assert rvz.read_bytes()[:4] == wia.MAGIC_RVZ   # the source is untouched


def test_open_disc_gives_a_plain_stream_for_an_iso(tmp_path):
    iso = tmp_path / "game.iso"
    iso.write_bytes(b"x" * 100)
    with wia.open_disc(iso) as stream:
        assert stream.read() == b"x" * 100


def test_open_disc_closes_the_file_of_a_refused_image(tmp_path, monkeypatch):
    rvz = tmp_path / "wii.rvz"
    rvz.write_bytes(build_wia(_random(0x8000), rvz=True, method=NONE, chunk=0x8000, disc_type=2))
    opened = []
    real_open = open
    monkeypatch.setattr(wia, "open", lambda *args: opened.append(real_open(*args)) or opened[-1], raising=False)
    with pytest.raises(ImageError, match="Wii"):
        wia.open_disc(rvz)
    assert len(opened) == 1 and opened[0].closed


def _set_group_count(data: bytes, count: int) -> bytes:
    out = bytearray(data)
    struct.pack_into(">I", out, 0x48 + 0xC4, count)
    return bytes(out)


@pytest.mark.parametrize("method", [BZIP2, LZMA, LZMA2])
def test_a_group_that_decompresses_past_its_disc_data_is_refused(method):
    data = build_wia(_random(MIB2), rvz=False, method=method, chunk=MIB2, stored={0: bytes(4 * MIB2)})
    with wia.WiaStream(io.BytesIO(data)) as stream, pytest.raises(ImageError, match="more than the"):
        stream.read(0x100)


def test_a_zstd_frame_is_decompressed_only_up_to_the_limit():
    frame = zstd_frame.compress(bytes(1 << 20), "test")
    assert zstd_frame.decompress(frame, "test", 100) == bytes(100)
    assert zstd_frame.decompress(frame, "test") == bytes(1 << 20)


def test_an_rvz_group_whose_packed_size_is_larger_than_two_chunks_is_refused():
    data = build_wia(_random(0x8000), rvz=True, method=NONE, chunk=0x8000, stored={0: bytes(0x10004)})
    with wia.WiaStream(io.BytesIO(data)) as stream, pytest.raises(ImageError, match="more than a group"):
        stream.read(0x100)


def test_an_rvz_junk_run_longer_than_its_group_is_refused_before_it_is_generated():
    packed = struct.pack(">I", 0x7FFFFFFF | wia.JUNK_FLAG) + bytes(wia.SEED_SIZE)
    data = build_wia(_random(0x8000), rvz=True, method=NONE, chunk=0x8000, stored={0: packed})
    with wia.WiaStream(io.BytesIO(data)) as stream, pytest.raises(ImageError, match="longer than its disc data"):
        stream.read(0x100)


@pytest.mark.parametrize("method", [NONE, LZMA2])
def test_a_group_table_that_holds_more_entries_than_the_header_declares_is_refused(method):
    image = _random(3 * 0x8000)
    data = _set_group_count(build_wia(image, rvz=True, method=method, chunk=0x8000), 2)
    with pytest.raises(ImageError, match="group"):
        wia.WiaStream(io.BytesIO(data))


def test_a_group_count_too_large_for_any_disc_is_refused_before_the_table_is_read():
    data = _set_group_count(build_wia(_random(0x8000), rvz=True, method=LZMA2, chunk=0x8000), 0x10000000)
    with pytest.raises(ImageError, match="too large"):
        wia.WiaStream(io.BytesIO(data))


def test_identify_takes_an_image_that_runs_out_of_memory_as_not_identified(tmp_path, monkeypatch):
    rvz = tmp_path / "game.rvz"
    rvz.write_bytes(build_wia(build_disc({"a.bin": b"A"}, game_id=b"GMSE01"), rvz=True, method=NONE, chunk=0x8000))

    def out_of_memory(_stream):
        raise MemoryError
    monkeypatch.setattr(images, "WiaStream", out_of_memory)
    assert images.identify(rvz) is None
