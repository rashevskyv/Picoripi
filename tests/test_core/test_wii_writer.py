"""The Wii disc writer (core/containers/wii_writer.py) on synthetic discs: the plain ISO copy, the WIA copy of a disc,
which must give back the sealed disc byte for byte, and the hash rule of a last group with missing clusters."""
import hashlib
import os
from pathlib import Path

from core.containers import wii_writer
from synthetic_wii import COMMON, DATA_AT, PART, make_disc
from test_core.test_wia_wii import NONE, build_wii


def _sealed(path: Path, files: dict) -> str:
    """A synthetic disc whose hashes, H3 and TMD are valid: every group is loaded and sealed once."""
    iso = make_disc(path, files)
    with open(iso, "r+b") as stream:
        part_at = wii_writer.data_partition(stream)
        part = wii_writer.Partition(stream, part_at, wii_writer.title_key(stream, part_at, COMMON))
        for group in range(-(-part.clusters // wii_writer.GROUP)):
            part._load(group)
            part.dirty.add(group)
        part.flush()
    return iso


def _no_progress(_percent, _text):
    pass


def test_a_plain_iso_copy_is_the_same_disc(tmp_path):
    iso = make_disc(tmp_path / "plain.iso", {"a.bin": b"abc" * 500})
    copy = tmp_path / "copy.iso"
    assert wii_writer.copy_as_iso(iso, str(copy), COMMON, _no_progress, lambda: False)
    assert copy.read_bytes() == Path(iso).read_bytes()


def test_a_copy_stops_when_cancelled(tmp_path):
    iso = make_disc(tmp_path / "stop.iso", {"a.bin": b"x"})
    assert wii_writer.copy_as_iso(iso, str(tmp_path / "copy.iso"), COMMON, _no_progress, lambda: True) is False


def test_a_wia_copy_gives_back_the_sealed_disc(tmp_path):
    iso = _sealed(tmp_path / "sealed.iso", {"a.bin": bytes(range(256)) * 90, "b.bin": b"tail" * 77})
    original = Path(iso).read_bytes()
    with open(iso, "rb") as stream:
        part_at = wii_writer.data_partition(stream)
        part = wii_writer.Partition(stream, part_at, wii_writer.title_key(stream, part_at, COMMON))
        plain = part.read(0, part.clusters * wii_writer.CLUSTER_DATA)
    data_at = PART + DATA_AT                       # the synthetic disc keeps its data after the raw area
    wia = tmp_path / "source.wia"
    wia.write_bytes(build_wii(plain, rvz=False, method=NONE, chunk=0x200000, raw=original[:data_at], data_at=data_at))
    copy = tmp_path / "copy.iso"
    assert wii_writer.copy_as_iso(str(wia), str(copy), COMMON, _no_progress, lambda: False)
    assert copy.read_bytes() == original


def test_the_missing_clusters_of_a_last_group_hash_as_zero_data():
    items = [[bytearray(0x400), bytearray(os.urandom(wii_writer.CLUSTER_DATA))] for _ in range(3)]
    enc, _h2 = wii_writer.seal_group(items, bytes(16))
    assert len(enc) == 3 * wii_writer.CLUSTER
    zero_h0 = b"".join(hashlib.sha1(bytes(0x400)).digest() for _ in range(31))
    phantom = hashlib.sha1(zero_h0).digest()
    assert bytes(items[0][0][0x280 + 3 * 20:0x280 + 4 * 20]) == phantom   # cluster 3 of the first subgroup is missing
