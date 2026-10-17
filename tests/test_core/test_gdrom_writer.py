"""GD-ROM writer (core/containers/gdrom_writer.py) on the synthetic disc of the reader tests: a write with no
replacement gives the same bytes, a replaced HD file reads back, its record and the PVD point at the new sectors,
and the changed sectors carry a valid EDC."""
import hashlib
import struct

import pytest

from core.containers import gdrom_writer
from core.containers.gdrom import HD_BASE, RAW_2352 as RAW, SECTOR, GdRomImage, GdRomStream
from core.containers.image_files import ImageError
from test_core.test_gdrom_reader import make_disc


def _sha(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _entries(cue):
    stream = GdRomStream(cue)
    try:
        return {e.path: e for e in GdRomImage(stream).entries()}
    finally:
        stream.close()


def _read(cue, path):
    stream = GdRomStream(cue)
    try:
        image = GdRomImage(stream)
        return image.read({e.path: e for e in image.entries()}[path])
    finally:
        stream.close()


def _nop(*_args):
    return None


def _never():
    return False


def test_a_write_with_no_replacement_gives_the_same_tracks(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    cue = make_disc(src)
    out = tmp_path / "out"
    written = gdrom_writer.write_set(cue, str(out), {}, _nop, _never)
    assert written == str(out / "disc.cue")
    assert _sha(src / "disc (Track 3).bin") == _sha(out / "disc (Track 3).bin")
    assert (out / "disc.cue").read_bytes() == (src / "disc.cue").read_bytes()


def test_a_longer_file_reads_back_from_the_end_of_the_track(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    cue = make_disc(src)
    out = tmp_path / "out"
    new = b"Ukrainian text " * 400   # 5600 bytes: three sectors
    written = gdrom_writer.write_set(cue, str(out), {"files/BIG.BIN": new}, _nop, _never)
    entry = _entries(written)["files/BIG.BIN"]
    assert entry.size == len(new)
    assert entry.offset // SECTOR >= HD_BASE + 40          # after the old end of the track
    assert _read(written, "files/BIG.BIN") == new
    assert _read(written, "files/DATA/FILE.TXT") == b"text"  # unchanged file still reads
    assert (out / "disc (Track 3).bin").stat().st_size == (src / "disc (Track 3).bin").stat().st_size + 3 * RAW


def test_the_changed_sectors_carry_a_valid_edc_and_the_pvd_has_the_new_size(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    cue = make_disc(src)
    out = tmp_path / "out"
    new = b"x" * 3000   # two sectors, appended after the 40 sectors of the track
    written = gdrom_writer.write_set(cue, str(out), {"files/BIG.BIN": new}, _nop, _never)
    raw_all = (out / "disc (Track 3).bin").read_bytes()
    for index in range(40, 42):   # the appended sectors
        raw = raw_all[index * RAW:(index + 1) * RAW]
        assert struct.unpack_from("<I", raw, 2064)[0] == gdrom_writer.edc(raw[:2064])
    pvd = raw_all[16 * RAW + 16:16 * RAW + 16 + SECTOR]
    volume = struct.unpack_from("<I", pvd, 80)[0]
    assert volume == 42   # the new end (45042) minus HD_BASE
    assert _entries(written)["files/BIG.BIN"].offset == (HD_BASE + 40) * SECTOR


def test_a_path_outside_the_hd_volume_is_refused(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    cue = make_disc(src)
    with pytest.raises(ImageError):
        gdrom_writer.write_set(cue, str(tmp_path / "out"), {"ld/HELLO.TXT": b"hi"}, _nop, _never)


def test_the_output_folder_cannot_be_the_disc_folder(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    cue = make_disc(src)
    with pytest.raises(ImageError):
        gdrom_writer.write_set(cue, str(src), {}, _nop, _never)
