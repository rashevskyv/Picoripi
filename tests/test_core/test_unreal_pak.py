"""Unreal ``.pak`` version 8 (core/unreal/pak.py): a written pak reads back, and the zstd helper works.

Generated data only. The real Bravely Default II pak sits inside an encrypted NSP, so reading it needs the owner's
Switch keys; that check was removed, and no test here opens a key file or a game file.
"""
import sys

import pytest

from core.unreal import pak


def test_written_pak_reads_back(tmp_path):
    files = {"Game/Content/a.uasset": b"\xc1\x83\x2a\x9e" + b"x" * 300, "Game/Content/b.txt": b"hello"}
    target = tmp_path / "patch_P.pak"
    pak.write_pak(target, files)
    opened = pak.open_path(target)
    assert opened.version == 8
    assert sorted(opened.names()) == sorted(files)
    for entry in opened.entries:
        assert opened.data(entry) == files[entry.name]


def test_a_closed_pak_releases_its_file(tmp_path):
    target = tmp_path / "patch_P.pak"
    pak.write_pak(target, {"a.txt": b"hi"})
    with pak.open_path(target) as opened:
        assert opened.data(opened.entries[0]) == b"hi"
    target.unlink()                     # on Windows an open file cannot be deleted
    assert not target.exists()
    opened.close()                      # closing twice is harmless


def test_bad_footer_is_refused(tmp_path):
    target = tmp_path / "not_a_pak.bin"
    target.write_bytes(b"\x00" * 400)
    with pytest.raises(pak.PakError):
        pak.open_path(target)


def test_zstd_without_a_zstd_module_is_a_pak_error(monkeypatch):
    # a None entry makes the import fail: this is how the test simulates a missing optional module
    monkeypatch.setitem(sys.modules, "compression", None)  # deslop: ignore[module-mocking] simulates a missing module; no mock object
    monkeypatch.setitem(sys.modules, "zstandard", None)  # deslop: ignore[module-mocking] simulates a missing module; no mock object
    with pytest.raises(pak.PakError, match="zstd needs Python 3.14 or the zstandard package"):
        pak._zstd_decompress(b"\x28\xb5\x2f\xfd", "Content/x.uasset")


def test_zstd_round_trip_with_the_standard_library():
    zstd = pytest.importorskip("compression.zstd")
    assert pak._zstd_decompress(zstd.compress(b"hello pak"), "x") == b"hello pak"
