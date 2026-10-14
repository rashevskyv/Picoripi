"""The GameCube disc writer on a synthetic disc: same size, shorter, grown (moved), refused changes, cancel."""
import hashlib

import pytest

from core.containers.gcm import GameCubeImage
from core.containers.gcm_writer import ALIGN, write_disc
from core.containers.image_files import ImageError
from gc_disc import build_disc

FILES = {"data/a.szs": b"A" * 100, "data/b.bmg": b"B" * 64, "data/c.bin": b"C" * 40}


def _never() -> bool:
    return False


def _read(path, rel):
    with open(path, "rb") as stream:
        image = GameCubeImage(stream)
        for entry in image.entries():
            if entry.path == rel:
                return image.read(entry)
    raise KeyError(rel)


def _write(tmp_path, data: bytes, name="src.iso"):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _noop(percent, text):
    return None


def test_unchanged_rebuild_is_byte_identical(tmp_path):
    src = _write(tmp_path, build_disc({k: v for k, v in FILES.items()}))
    out = tmp_path / "out.iso"
    assert write_disc(src, out, {}, _noop, _never) == str(out)
    assert out.read_bytes() == src.read_bytes()


def test_same_size_change_is_written_in_place(tmp_path):
    data = build_disc(FILES)
    src = _write(tmp_path, data)
    out = tmp_path / "out.iso"
    write_disc(src, out, {"files/data/a.szs": b"X" * 100}, _noop, _never)
    assert _read(out, "files/data/a.szs") == b"X" * 100
    assert _read(out, "files/data/b.bmg") == b"B" * 64
    assert len(out.read_bytes()) == len(data)


def test_shorter_change_zero_fills_the_old_tail(tmp_path):
    src = _write(tmp_path, build_disc(FILES))
    out = tmp_path / "out.iso"
    write_disc(src, out, {"files/data/a.szs": b"Y" * 10}, _noop, _never)
    assert _read(out, "files/data/a.szs") == b"Y" * 10
    with open(out, "rb") as stream:
        image = GameCubeImage(stream)
        old = next(e for e in image.entries() if e.path == "files/data/a.szs")
        stream.seek(old.offset + 10)
        assert stream.read(90) == bytes(90)


def test_grown_change_moves_to_an_aligned_free_offset(tmp_path):
    src = _write(tmp_path, build_disc(FILES))
    out = tmp_path / "out.iso"
    write_disc(src, out, {"files/data/b.bmg": b"Z" * 5000}, _noop, _never)
    assert _read(out, "files/data/b.bmg") == b"Z" * 5000
    assert _read(out, "files/data/a.szs") == b"A" * 100
    assert _read(out, "files/data/c.bin") == b"C" * 40
    with open(out, "rb") as stream:
        image = GameCubeImage(stream)
        moved = next(e for e in image.entries() if e.path == "files/data/b.bmg")
    assert moved.offset % ALIGN == 0
    assert moved.size == 5000


def test_the_source_image_is_never_written(tmp_path):
    src = _write(tmp_path, build_disc(FILES))
    before = _sha(src)
    write_disc(src, tmp_path / "out.iso", {"files/data/b.bmg": b"Z" * 5000}, _noop, _never)
    assert _sha(src) == before


def test_a_path_the_disc_does_not_hold_is_refused(tmp_path):
    src = _write(tmp_path, build_disc(FILES))
    with pytest.raises(ImageError, match="no such file"):
        write_disc(src, tmp_path / "out.iso", {"files/data/new.bin": b"N"}, _noop, _never)
    assert not (tmp_path / "out.iso").exists()


def test_system_files_other_than_main_dol_are_refused(tmp_path):
    src = _write(tmp_path, build_disc(FILES))
    with pytest.raises(ImageError, match="only sys/main.dol"):
        write_disc(src, tmp_path / "out.iso", {"sys/boot.bin": b"\0" * 0x440}, _noop, _never)


def test_main_dol_must_keep_its_size(tmp_path):
    src = _write(tmp_path, build_disc(FILES))
    with pytest.raises(ImageError, match="keep its size"):
        write_disc(src, tmp_path / "out.iso", {"sys/main.dol": b"\0" * 7}, _noop, _never)


def test_output_must_not_be_the_source(tmp_path):
    src = _write(tmp_path, build_disc(FILES))
    with pytest.raises(ImageError, match="must not be the source"):
        write_disc(src, src, {}, _noop, _never)


def test_cancel_leaves_no_output_and_no_temp(tmp_path):
    src = _write(tmp_path, build_disc(FILES))
    out = tmp_path / "out.iso"
    calls = {"n": 0}

    def cancel_soon():
        calls["n"] += 1
        return calls["n"] > 1

    assert write_disc(src, out, {"files/data/a.szs": b"X" * 100}, _noop, cancel_soon) is None
    assert not out.exists()
    assert not (tmp_path / "out.iso.tmp").exists()
