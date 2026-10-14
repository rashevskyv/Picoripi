"""Tests for core/containers/romfs_write.py: the RomFS writer (port of LASRecomp romfs_build.c)."""
import os
import struct
from pathlib import Path

import pytest

from core.containers.console_crypto import RangeView
from core.containers.image_files import ImageReader
from core.containers.romfs_write import RomfsWriteCancelled, RomfsWriteError, write_romfs
from core.containers.switch_images import _romfs_files

EMPTY = 0xFFFFFFFF

TREE = {
    "region_common/a.bin": b"alpha",
    "region_common/empty.bin": b"",
    "regionUS/USen/message/System.msbt": b"MSBT" * 100,
    "regionUS/USen/message/zz.bin": bytes(range(256)) * 3,
    "regionUS/readme_ü.txt": "üé".encode(),
    "top.bin": b"top",
    ".DS_Store": b"hidden",
    "regionUS/.hidden/inside.bin": b"skip",
}


def _make_tree(root: Path, files: dict) -> Path:
    for rel, data in files.items():
        path = root.joinpath(*rel.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def _read_back(image: Path) -> dict:
    """The files of a written image, read through the Switch RomFS reader: {path: bytes}."""
    with open(image, "rb") as fh:
        view = RangeView(fh, 0, os.path.getsize(image))
        return {entry.path: ImageReader(view).read(entry) for entry in _romfs_files(view)}


def _hash(parent: int, name: bytes) -> int:
    """The RomFS name hash, written again from the C formula (name_hash in romfs_build.c)."""
    h = parent ^ 123456789
    for byte in name:
        h = (((h >> 5) | (h << 27)) & 0xFFFFFFFF) ^ byte
    return h


def _u32(table: bytes, pos: int) -> int:
    return struct.unpack_from("<I", table, pos)[0]


def _entries(table: bytes, header: int, name_at: int) -> list:
    """Offsets of the entries of a table, found by stepping over each entry's size."""
    offsets, pos = [], 0
    while pos < len(table):
        offsets.append(pos)
        pos += header + ((_u32(table, pos + name_at) + 3) & ~3)
    assert pos == len(table)
    return offsets


def _walk(head: int, table: bytes, next_at: int, limit: int) -> list:
    chain, pos = [], head
    while pos != EMPTY:
        assert len(chain) < limit, "a hash chain loops"
        chain.append(pos)
        pos = _u32(table, pos + next_at)
    return chain


def _check_table(buckets: list, table: bytes, header: int, name_at: int, next_at: int) -> None:
    """Every entry is found by walking the chain of its own bucket, and each entry is in exactly one chain."""
    offsets = _entries(table, header, name_at)
    chains = [_walk(head, table, next_at, len(offsets)) for head in buckets]
    for index, chain in enumerate(chains):
        for pos in chain:
            name = table[pos + header:pos + header + _u32(table, pos + name_at)]
            assert _hash(_u32(table, pos), name) % len(buckets) == index
    for pos in offsets:
        name = table[pos + header:pos + header + _u32(table, pos + name_at)]
        assert pos in chains[_hash(_u32(table, pos), name) % len(buckets)]
    assert sorted(p for chain in chains for p in chain) == offsets


def test_round_trip_keeps_files_and_skips_hidden(tmp_path):
    tree = _make_tree(tmp_path / "tree", TREE)
    out = tmp_path / "romfs.bin"
    write_romfs(str(tree), str(out))
    expected = {f"romfs/{rel}": data for rel, data in TREE.items()
                if not any(part.startswith(".") for part in rel.split("/"))}
    files = _read_back(out)
    assert files == expected
    assert not any(".DS_Store" in path or ".hidden" in path for path in files)


def test_hash_chains_reach_every_entry(tmp_path):
    tree = _make_tree(tmp_path / "tree", TREE)
    out = tmp_path / "romfs.bin"
    write_romfs(str(tree), str(out))
    data = out.read_bytes()
    head = struct.unpack_from("<10Q", data)
    dbuckets = struct.unpack_from(f"<{head[2] // 4}I", data, head[1])
    dtab = data[head[3]:head[3] + head[4]]
    fbuckets = struct.unpack_from(f"<{head[6] // 4}I", data, head[5])
    ftab = data[head[7]:head[7] + head[8]]
    _check_table(list(dbuckets), dtab, 0x18, 0x14, 0x10)
    _check_table(list(fbuckets), ftab, 0x20, 0x1C, 0x18)


def test_single_file_image_matches_hand_derived_bytes(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "a.bin").write_bytes(b"hello")
    out = tmp_path / "romfs.bin"
    write_romfs(str(tree), str(out))
    # Derived from romfs_build.c by hand. Root and a.bin: 1 folder entry (0x18), 1 file entry (0x20 + 8 = 0x28).
    # Bucket count of 1 entry is 3. a.bin is at data offset 0, size 5. Its data ends at 0x205; the directory
    # hash table starts at the next 4-byte boundary, 0x208. The root hash 123456789 % 3 = 0; the hash of
    # "a.bin" with parent 0 is 0xfd3c9aee, which % 3 = 0.
    header = struct.pack("<10Q", 0x50, 0x208, 12, 0x214, 24, 0x22C, 12, 0x238, 40, 0x200).ljust(0x200, b"\0")
    data = b"hello" + bytes(3)
    dbuckets = struct.pack("<3I", 0, EMPTY, EMPTY)
    root_entry = struct.pack("<6I", 0, EMPTY, EMPTY, 0, EMPTY, 0)
    fbuckets = struct.pack("<3I", 0, EMPTY, EMPTY)
    file_entry = struct.pack("<IIQQII", 0, EMPTY, 0, 5, EMPTY, 5) + b"a.bin" + bytes(3)
    assert out.read_bytes() == header + data + dbuckets + root_entry + fbuckets + file_entry


def test_overlay_replaces_a_file_and_adds_a_new_one(tmp_path):
    tree = _make_tree(tmp_path / "tree", {"region_common/a.bin": b"old", "top.bin": b"t"})
    patch = tmp_path / "patch.bin"
    patch.write_bytes(b"new text")
    added = tmp_path / "added.bin"
    added.write_bytes(b"added")
    out = tmp_path / "romfs.bin"
    write_romfs(str(tree), str(out), overlay={"region_common/a.bin": str(patch),
                                              "regionUS/USen/new.bin": str(added)})
    assert _read_back(out) == {"romfs/region_common/a.bin": b"new text", "romfs/top.bin": b"t",
                               "romfs/regionUS/USen/new.bin": b"added"}


def test_cancel_raises_and_leaves_no_output(tmp_path):
    tree = _make_tree(tmp_path / "tree", {"a.bin": b"1", "b.bin": b"2", "c.bin": b"3"})
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    calls = []

    def cancelled() -> bool:
        calls.append(1)
        return len(calls) >= 2

    with pytest.raises(RomfsWriteCancelled):
        write_romfs(str(tree), str(out_dir / "romfs.bin"), is_cancelled=cancelled)
    assert len(calls) == 2
    assert list(out_dir.iterdir()) == []


def test_two_writes_of_one_tree_are_identical(tmp_path):
    tree = _make_tree(tmp_path / "tree", TREE)
    write_romfs(str(tree), str(tmp_path / "one.bin"))
    write_romfs(str(tree), str(tmp_path / "two.bin"))
    assert (tmp_path / "one.bin").read_bytes() == (tmp_path / "two.bin").read_bytes()


def test_progress_ends_at_the_total_file_bytes(tmp_path):
    tree = _make_tree(tmp_path / "tree", {"a.bin": b"x" * 10, "b.bin": b"y" * 7})
    seen = []
    write_romfs(str(tree), str(tmp_path / "romfs.bin"), progress=lambda done, total: seen.append((done, total)))
    assert seen[-1] == (17, 17)


def test_folders_deeper_than_32_levels_are_left_out(tmp_path):
    tree = tmp_path / "tree"
    deep32 = tree.joinpath(*["d"] * 32)
    deep32.mkdir(parents=True)
    (deep32 / "keep.bin").write_bytes(b"k")
    deep33 = deep32 / "d"
    deep33.mkdir()
    (deep33 / "drop.bin").write_bytes(b"x")
    out = tmp_path / "romfs.bin"
    write_romfs(str(tree), str(out))
    assert _read_back(out) == {"romfs/" + "d/" * 32 + "keep.bin": b"k"}


def test_tree_without_files_is_an_error(tmp_path):
    tree = tmp_path / "tree"
    (tree / "empty_folder").mkdir(parents=True)
    out = tmp_path / "romfs.bin"
    with pytest.raises(RomfsWriteError):
        write_romfs(str(tree), str(out))
    assert not out.exists()
