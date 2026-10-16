"""Unreal pak v10/v11, IoStore and the Oodle wrapper: synthetic layouts, and the real Metal Gear Solid Delta files.

The real-file tests read ``MGSDelta/Content/Paks`` under ``PICORIPI_ROMHACKING`` (read only) and the Oodle library from
``_shared/tools/oodle`` or ``PICORIPI_OODLE_DLL``; they skip with the reason when either is missing.
"""
import struct

import pytest

import romhacking_root
from core.unreal import iostore, oodle, pak

GAME_PAKS = ("Metal Gear", "Metal Gear Solid Delta", "PC", "ISO", "MGSDelta_game", "MGSDelta", "Content", "Paks")
PAK_V11 = GAME_PAKS + ("pakchunk0-Windows.pak",)
TOC = GAME_PAKS + ("pakchunk0-Windows.utoc",)


def _real(*parts):
    """Skip the test when the real game file is not on disk."""
    reason = romhacking_root.missing(*parts)
    if reason:
        pytest.skip(reason)
    return romhacking_root.path(*parts)


def _oodle():
    """The Oodle library for the real-data tests; skips when it is not on this machine."""
    try:
        return oodle.Oodle(oodle.find_library(search_dirs=(romhacking_root.under("_shared/tools/oodle"),)))
    except oodle.OodleError as exc:
        pytest.skip(str(exc))


# ---- Oodle -----------------------------------------------------------------------------------------------------

def test_missing_oodle_library_is_an_error(tmp_path, monkeypatch):
    monkeypatch.delenv(oodle.ENV_VAR, raising=False)
    with pytest.raises(oodle.OodleError, match="no Oodle library"):
        oodle.find_library(search_dirs=(tmp_path,))
    with pytest.raises(oodle.OodleError, match="not found"):
        oodle.find_library(tmp_path / "missing.dll")


def test_a_file_that_is_not_oodle_is_refused(tmp_path):
    not_a_dll = tmp_path / "oo2core_9_win64.dll"
    not_a_dll.write_bytes(b"MZ not a library")
    with pytest.raises(oodle.OodleError, match="cannot load"):
        oodle.Oodle(not_a_dll)


# ---- pak v10/v11 synthetic ---------------------------------------------------------------------------------------

def test_encoded_record_with_one_compressed_block():
    # flags: offset, uncompressed size and size are 32-bit (bits 31, 30, 29); method 1; one block; block size bits 0
    flags = 0xE0000000 | (1 << 23) | (1 << 6)
    blob = struct.pack("<IIII", flags, 1000, 5000, 300)
    entry = pak._decode_encoded_entry(blob, 0)
    assert (entry.offset, entry.usize, entry.size, entry.method) == (1000, 5000, 300, 1)
    assert entry.blocks == [(73, 373)]                  # 57 + 16 bytes of record header, then the block


def test_encoded_record_with_two_blocks_reads_their_sizes():
    flags = 0xE0000000 | (1 << 23) | (2 << 6) | 0x20   # block size bits 0x20: 0x20 << 11 = 65536
    blob = struct.pack("<IIIIII", flags, 0, 100000, 300, 100, 200)   # offset, usize, size, then the two block sizes
    entry = pak._decode_encoded_entry(blob, 0)
    assert entry.block_size == 65536
    assert entry.blocks == [(89, 189), (189, 389)]
    assert pak._block_raw_sizes(entry) == [65536, 100000 - 65536]


def test_block_sizes_that_do_not_make_the_uncompressed_size_are_refused():
    flags = 0xE0000000 | (1 << 23) | (2 << 6) | 0x20   # two 65536-byte blocks
    blob = struct.pack("<IIIIII", flags, 0, 60000, 300, 100, 200)   # but only 60000 uncompressed bytes
    entry = pak._decode_encoded_entry(blob, 0)
    with pytest.raises(pak.PakError, match="do not make"):
        pak._block_raw_sizes(entry)


def test_an_encrypted_encoded_record_is_refused():
    flags = 0xE0000000 | (1 << 22)
    with pytest.raises(pak.PakError, match="encrypted"):
        pak._decode_encoded_entry(struct.pack("<IIII", flags, 0, 4, 4), 0)


def test_directory_index_gives_full_paths_and_chunk_numbers():
    mount = b"../../../"
    strings = [b"Game", b"a.uasset"]

    def fstr(text):
        return struct.pack("<i", len(text) + 1) + text + b"\0"

    none = 0xFFFFFFFF
    blob = fstr(mount) + struct.pack("<i", 2)
    blob += struct.pack("<IIII", none, 1, none, none) + struct.pack("<IIII", 0, none, none, 0)
    blob += struct.pack("<i", 1) + struct.pack("<III", 1, none, 7)
    blob += struct.pack("<i", 2) + fstr(strings[0]) + fstr(strings[1])
    mount_point, files = iostore.parse_directory(blob)
    assert mount_point == "../../../"
    assert files == [("../../../Game/a.uasset", 7)]


def test_a_directory_blob_of_nothing_is_empty():
    assert iostore.parse_directory(b"") == ("", [])


def test_toc_with_a_wrong_magic_is_refused():
    with pytest.raises(iostore.IoStoreError, match="magic"):
        iostore.parse_toc(b"\0" * 200)


# ---- real game files (read only) ----------------------------------------------------------------------------------

def test_real_pak_v11_index_lists_every_entry():
    path = _real(*PAK_V11)
    with pak.open_path(path) as opened:
        assert opened.version == 11
        assert opened.mount == "../../../"
        assert len(opened.entries) == 22700
        assert all(entry.offset + entry.size <= opened.size for entry in opened.entries)
        assert any(name.startswith("../../../MGSDelta/Content/") for name in opened.names())


def test_real_pak_v11_oodle_entries_decode_to_their_indexed_size():
    lib = _oodle()
    path = _real(*PAK_V11)
    with pak.open_path(path, oodle=lib) as opened:
        oodle_entries = [e for e in opened.entries if e.method and opened.methods[e.method - 1] == "Oodle"]
        assert oodle_entries
        for entry in oodle_entries[:2]:
            assert len(opened.data(entry)) == entry.usize


def test_real_iostore_toc_matches_the_directory_and_chunk_counts():
    toc_path = _real(*TOC)
    store = iostore.IoStore(toc_path)
    assert store.toc.version == 5
    assert store.toc.method_names == ["Oodle"]
    assert len(store.toc.chunks) == 106974
    assert len(store.files()) == 92144
    assert store.toc.meta_size == 33


def test_real_iostore_chunks_decompress_to_the_toc_length():
    lib = _oodle()
    store = iostore.IoStore(_real(*TOC), oodle=lib)
    checked = 0
    for path, index in store.files():
        if not path.endswith(".uasset"):
            continue
        chunk = store.toc.chunks[index]
        assert len(store.chunk_bytes(chunk)) == chunk.length
        checked += 1
        if checked == 3:
            break
    assert checked == 3
