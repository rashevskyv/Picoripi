"""Retro RFRM packages (Metroid Prime 4): directory, LZSS and Huffman-LZ decoding, repacking, texture buffers.

Synthetic packages and streams check the rules; the game's own files (skipped when missing) check that an
untouched package repacks byte for byte and that the tables come from the executable.
"""
import struct
from pathlib import Path

import pytest

from core.containers import retro_pak as rp

WS = Path(r"E:\Emulators\RomHacking\Metroid\Prime 4 Beyond")


def _form(kind: bytes, body: bytes, version: int = 1) -> bytes:
    return rp.FORM.pack(b"RFRM", len(body), 0, kind, version, version) + body


def _chunk(kind: bytes, body: bytes) -> bytes:
    return rp.CHUNK.pack(kind, len(body), 1, 0) + body


def _package(assets, meta=None) -> bytes:
    """A PACK with ``assets`` [(type, guid, form)] stored uncompressed and optional {guid: metadata}."""
    meta = meta or {}
    entries = []
    adir_size = 4 + 60 * len(assets)
    order = [guid for _t, guid, _f in assets if guid in meta]
    meta_body = struct.pack("<I", len(order))
    blobs, start = b"", 4 + 20 * len(order)
    for guid in order:
        meta_body += struct.pack("<16sI", guid, start + len(blobs))
        blobs += struct.pack("<I", len(meta[guid])) + meta[guid]
    meta_body += blobs
    names = struct.pack("<I", len(assets)) + b"".join(
        kind[::-1] + guid + struct.pack("<I", 5) + b"name%d" % i for i, (kind, guid, _f) in enumerate(assets))
    toc_len = rp.FORM.size + 3 * rp.CHUNK.size + adir_size + len(meta_body) + len(names)
    offset = rp.FORM.size + toc_len
    for kind, guid, form in assets:
        entries.append(struct.pack("<4s16sIIQQQQ", kind, guid, 1, 1, offset, len(form), len(form), 0))
        offset += len(form)
    adir = struct.pack("<I", len(assets)) + b"".join(entries)
    toc = _form(b"TOCC", _chunk(b"ADIR", adir) + _chunk(b"META", meta_body) + _chunk(b"STRG", names), 4)
    return _form(b"PACK", toc + b"".join(form for _k, _g, form in assets))


GUID_A, GUID_B = bytes(range(16)), bytes(range(16, 32))


def test_directory_names_and_reading(tmp_path):
    path = tmp_path / "a.pak"
    path.write_bytes(_package([(b"MSBT", GUID_A, _form(b"MSBT", b"hello")), (b"TXTR", GUID_B, _form(b"TXTR", b"x" * 9))],
                              {GUID_B: b"meta"}))
    pak = rp.Pak(path)
    assert [a.type for a in pak.assets] == ["MSBT", "TXTR"]
    assert pak.assets[0].name == "name0" and pak.meta[GUID_B] == b"meta"
    assert pak.read(pak.find("MSBT")[0])[-5:] == b"hello"


def test_repack_copies_or_replaces_and_resizes_metadata(tmp_path):
    path = tmp_path / "a.pak"
    original = _package([(b"MSBT", GUID_A, _form(b"MSBT", b"hello")), (b"TXTR", GUID_B, _form(b"TXTR", b"x" * 9))],
                        {GUID_B: b"meta"})
    path.write_bytes(original)
    rp.repack(path, tmp_path / "same.pak", {})
    assert (tmp_path / "same.pak").read_bytes() == original
    new = _form(b"MSBT", b"a much longer text")
    assert rp.repack(path, tmp_path / "new.pak", {GUID_A: new}, {GUID_B: b"longer metadata"}) == 1
    pak = rp.Pak(tmp_path / "new.pak")
    assert pak.read(pak.by_guid(GUID_A)) == new
    assert pak.read(pak.by_guid(GUID_B)) == _form(b"TXTR", b"x" * 9)
    assert pak.meta[GUID_B] == b"longer metadata"
    assert struct.unpack_from("<Q", (tmp_path / "new.pak").read_bytes(), 4)[0] + 0x20 == (tmp_path / "new.pak").stat().st_size


def test_lzss_literal_and_overlapping_match():
    # mode 1: flags 0b01000000 -> literal 'a', then a match of (0 + 3) bytes at distance 1
    stream = bytes([0b01000000]) + b"a" + bytes([0x00, 0x01])
    assert rp.lzss(stream, 4, 1) == b"aaaa"


class _Bits:
    def __init__(self):
        self.value, self.count = 0, 0

    def put(self, value: int, bits: int):
        self.value = self.value << bits | value
        self.count += bits

    def bytes(self) -> bytes:
        pad = -self.count % 8
        return (self.value << pad).to_bytes((self.count + pad) // 8, "big")


def _flat_tables() -> rp.HuffmanTables:
    """Every symbol an 8-bit code equal to itself (a complete canonical code)."""
    table = b"".join(struct.pack("<HBBI", 8, 1, i, i) for i in range(256))
    return rp.HuffmanTables(table * 3)


@pytest.mark.parametrize("mode, unit", [(12, 1), (13, 2), (14, 4)])
def test_huffman_lz_units(mode, unit):
    bits = _Bits()
    literal = bytes(range(1, unit + 1))
    bits.put(0, 1)
    bits.put(int.from_bytes(literal, "big"), 8 * unit)
    bits.put(1, 1)                       # match: length symbol 0, distance 1 unit
    for symbol in (0, 1, 0):
        bits.put(symbol, 8)
    count = 15 - mode                   # units copied for length symbol 0
    blob = struct.pack("<I", mode) + bits.bytes()
    assert rp.decompress(blob, unit * (1 + count), _flat_tables()) == literal * (1 + count)


def test_compressed_modes_need_tables():
    with pytest.raises(ValueError):
        rp.decompress(struct.pack("<I", 12) + b"\0" * 8, 4)


def test_lz4_block():
    # 1 literal 'x', match offset 1 length 4 + 4
    assert rp.lz4_block(bytes([0x14]) + b"x" + bytes([1, 0]), 9) == b"x" * 9


def test_texture_metadata_of_an_unpacked_form():
    head = _chunk(b"HEAD", b"h" * 42)
    gpu_body = struct.pack("<I", 0) + b"p" * 16
    form = _form(b"TXTR", head + _chunk(b"GPU ", gpu_body))
    header_end = len(form) - len(gpu_body)
    meta = struct.pack("<6I", 7, 0, 0, header_end - 24, 512, 16) + struct.pack("<I", 2)
    meta += struct.pack("<BII", 0, 0, header_end) + struct.pack("<BII", 0, header_end, len(gpu_body))
    meta += struct.pack("<IIIII", 1, len(gpu_body), 0, 16, 3) + b"\0" * 28
    assert len(meta) == 94
    assert rp.unpack_texture(form, meta) == form
    assert rp.texture_meta(form, meta) == meta


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_game_package_repacks_byte_for_byte(tmp_path):
    source = _need(WS / "romfs" / "MiscData.pak")
    rp.repack(source, tmp_path / "MiscData.pak", {})
    assert (tmp_path / "MiscData.pak").read_bytes() == source.read_bytes()


def test_game_tables_decode_every_font():
    tables = rp.HuffmanTables.from_executable(_need(WS / "exefs" / "main"))
    for rel in ("MiscData.pak", "Preload/MPR4/PreloadMP4.pak"):
        pak = rp.Pak(_need(WS / "romfs" / rel))
        for asset in pak.find("FONT"):
            assert asset.compressed
            data = pak.read(asset, tables)
            assert rp.form_header(data)[0] == "FONT" and len(data) == asset.size


def test_remastered_texture_buffers_unpack_and_get_metadata():
    """Metadata version 5 (Prime Remastered): a list of compressed buffers placed at their data offsets."""
    head = _chunk(b"HEAD", b"h" * 46)
    literal = bytes([0]) + b"abcdefgh"                      # mode 1: eight literal bytes
    buffers = struct.pack("<I", 1) + literal, struct.pack("<I", 0) + b"XYZW"
    form = _form(b"TXTR", head + _chunk(b"GPU ", b"".join(buffers)))
    header_end = len(form) - sum(map(len, buffers))
    meta = struct.pack("<6I", 5, 0, 0, header_end - 24, 512, 12) + struct.pack("<I", 1)
    meta += struct.pack("<BII", 0, 0, len(form)) + struct.pack("<I", 2)
    meta += struct.pack("<5I", 0, header_end, len(buffers[0]), 4, 8)
    meta += struct.pack("<5I", 0, header_end + len(buffers[0]), len(buffers[1]), 0, 4)
    exploded = rp.unpack_texture(form, meta)
    assert exploded[header_end:] == struct.pack("<I", 0) + b"XYZWabcdefgh"
    again = rp.texture_meta(exploded, meta)
    assert struct.unpack_from("<I", again)[0] == 5 and len(again) == 61
    assert rp.unpack_texture(exploded, again) == exploded
