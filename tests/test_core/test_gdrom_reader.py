"""GD-ROM (Dreamcast BIN/CUE) reader on synthetic discs: a small writer in this file builds raw MODE1/2352 tracks with
an ISO 9660 volume in each area, an audio track, and the refusals. The real-disc test skips without the owner's files."""
import os
import struct

import pytest

from core.containers.gdrom import HD_BASE, SECTOR, GdRomImage, GdRomStream
from core.containers.image_files import ImageError

RAW = 2352
REAL_CUE = r"E:\Emulators\RomHacking\Grandia\Grandia II\Dreamcast\ISO\Grandia II (USA).cue"


def raw_sector(user: bytes = b"") -> bytes:
    """A Mode 1 raw sector: sync, header, 2048 user bytes, 288 bytes of error correction (zeros here)."""
    body = user.ljust(SECTOR, b"\x00")
    return b"\x00" + b"\xff" * 10 + b"\x00" + b"\x00\x00\x00\x01" + body + b"\x00" * 288


def dir_record(name: bytes, extent: int, size: int, is_dir: bool) -> bytes:
    length = 33 + len(name) + (1 - len(name) % 2) % 2
    rec = bytearray(length)
    rec[0] = length
    struct.pack_into("<I", rec, 2, extent)
    struct.pack_into(">I", rec, 6, extent)
    struct.pack_into("<I", rec, 10, size)
    struct.pack_into(">I", rec, 14, size)
    rec[25] = 2 if is_dir else 0
    rec[32] = len(name)
    rec[33:33 + len(name)] = name
    return bytes(rec)


def pvd(root_extent: int, root_size: int) -> bytes:
    body = bytearray(SECTOR)
    body[0] = 1
    body[1:6] = b"CD001"
    body[6] = 1
    body[156:190] = dir_record(b"\x00", root_extent, root_size, True)
    return bytes(body)


def terminator() -> bytes:
    return b"\xff" + b"CD001" + b"\x01" + b"\x00" * (SECTOR - 7)


def directory(*records: bytes) -> bytes:
    return b"".join(records).ljust(SECTOR, b"\x00")


def write_cue(folder, tracks):
    """tracks: list of (area, file name, mode, bytes of the file). Writes the .bin files and the .cue."""
    lines = []
    area_now = None
    for index, (area, name, mode, data) in enumerate(tracks, start=1):
        if area != area_now:
            lines.append("REM HIGH-DENSITY AREA" if area == "hd" else "REM SINGLE-DENSITY AREA")
            area_now = area
        (folder / name).write_bytes(data)
        lines.append(f'FILE "{name}" BINARY')
        lines.append(f"  TRACK {index:02d} {mode}")
        lines.append("    INDEX 01 00:00:00")
    cue = folder / "disc.cue"
    cue.write_text("\n".join(lines) + "\n", encoding="ascii")
    return str(cue)


def ld_area() -> bytes:
    """Sectors 0..19 of the LD area: a volume with HELLO.TXT in sector 19, then four audio sectors (20..23)."""
    sectors = [raw_sector() for _ in range(20)]
    sectors[16] = raw_sector(pvd(18, SECTOR))
    sectors[17] = raw_sector(terminator())
    sectors[18] = raw_sector(directory(
        dir_record(b"\x00", 18, SECTOR, True), dir_record(b"\x01", 18, SECTOR, True),
        dir_record(b"HELLO.TXT;1", 19, 5, False)))
    sectors[19] = raw_sector(b"hello")
    return b"".join(sectors)


def hd_area() -> bytes:
    """File sectors 0..39 of the HD area (absolute 45000..45039): volume, DATA/FILE.TXT and BIG.BIN (2 sectors).
    Extents are absolute sector numbers, as on a real GD-ROM volume."""
    b = HD_BASE
    sectors = [raw_sector() for _ in range(40)]
    sectors[16] = raw_sector(pvd(b + 18, SECTOR))
    sectors[17] = raw_sector(terminator())
    sectors[18] = raw_sector(directory(
        dir_record(b"\x00", b + 18, SECTOR, True), dir_record(b"\x01", b + 18, SECTOR, True),
        dir_record(b"DATA", b + 19, SECTOR, True), dir_record(b"BIG.BIN;1", b + 20, 3000, False)))
    sectors[19] = raw_sector(directory(
        dir_record(b"\x00", b + 19, SECTOR, True), dir_record(b"\x01", b + 18, SECTOR, True),
        dir_record(b"FILE.TXT;1", b + 22, 4, False)))
    sectors[20] = raw_sector(b"A" * SECTOR)
    sectors[21] = raw_sector(b"B" * (3000 - SECTOR))
    sectors[22] = raw_sector(b"text")
    return b"".join(sectors)


def make_disc(folder, ld=None, hd=None):
    ld = ld_area() if ld is None else ld
    hd = hd_area() if hd is None else hd
    audio = b"\x11" * (4 * RAW)
    return write_cue(folder, [
        ("ld", "disc (Track 1).bin", "MODE1/2352", ld),
        ("ld", "disc (Track 2).bin", "AUDIO", audio),
        ("hd", "disc (Track 3).bin", "MODE1/2352", hd),
    ])


def test_lists_hd_files_under_files_and_ld_files_under_ld(tmp_path):
    stream = GdRomStream(make_disc(tmp_path))
    entries = {e.path: e for e in GdRomImage(stream).entries()}
    assert set(entries) == {"files/DATA/FILE.TXT", "files/BIG.BIN", "ld/HELLO.TXT"}
    assert entries["files/BIG.BIN"].size == 3000
    assert entries["ld/HELLO.TXT"].size == 5


def test_file_bytes_cross_sector_boundaries(tmp_path):
    image = GdRomImage(GdRomStream(make_disc(tmp_path)))
    entries = {e.path: e for e in image.entries()}
    assert image.read(entries["files/BIG.BIN"]) == b"A" * SECTOR + b"B" * (3000 - SECTOR)
    assert image.read(entries["files/DATA/FILE.TXT"]) == b"text"
    assert image.read(entries["ld/HELLO.TXT"]) == b"hello"


def test_the_hd_area_starts_at_sector_45000(tmp_path):
    stream = GdRomStream(make_disc(tmp_path))
    stream.seek((HD_BASE + 16) * SECTOR)
    assert stream.read(6) == b"\x01CD001"


def test_an_audio_sector_is_refused_as_data(tmp_path):
    stream = GdRomStream(make_disc(tmp_path))
    stream.seek(20 * SECTOR)
    with pytest.raises(ImageError):
        stream.read(10)


def test_a_track_file_that_is_not_whole_sectors_is_refused(tmp_path):
    cue = make_disc(tmp_path, hd=hd_area()[:-1])
    with pytest.raises(ImageError):
        GdRomStream(cue)


def test_an_unsupported_track_mode_is_refused(tmp_path):
    cue = write_cue(tmp_path, [("hd", "disc (Track 3).bin", "MODE2/2352", hd_area())])
    with pytest.raises(ImageError):
        GdRomStream(cue)


def test_a_disc_without_a_volume_is_refused(tmp_path):
    blank = b"".join(raw_sector() for _ in range(20))
    hd = b"".join(raw_sector() for _ in range(40))
    stream = GdRomStream(make_disc(tmp_path, ld=blank, hd=hd))
    with pytest.raises(ImageError):
        GdRomImage(stream)


REAL_SOA_CUE = r"E:\Emulators\RomHacking\Skies of Arcadia\Skies of Arcadia\Dreamcast\ISO\Skies of Arcadia (USA) (Disc 1).cue"


@pytest.mark.skipif(not os.path.isfile(REAL_SOA_CUE), reason="the owner's Skies of Arcadia disc 1 is not on disk")
def test_real_skies_disc_lists_the_hd_and_ld_volumes():
    image = GdRomImage(GdRomStream(REAL_SOA_CUE))
    entries = {e.path: e for e in image.entries()}
    assert entries["files/1ST_READ.BIN"].size == 5460080
    assert entries["ld/MASTER01.BMP"].size == 921656
    assert image.read(entries["ld/COPYRIGH.TXT"]) != b""


@pytest.mark.skipif(not os.path.isfile(REAL_CUE), reason="the owner's Grandia II image is not on disk")
def test_real_grandia_disc_lists_the_game_files():
    image = GdRomImage(GdRomStream(REAL_CUE))
    entries = {e.path: e for e in image.entries()}
    assert entries["files/GR2.AFS"].size == 276037632
    assert entries["files/1ST_READ.BIN"].size == 1279172
    assert "files/GR2.IDX" in entries
    head = image.read_at(entries["files/GR2.AFS"].offset, 4)
    assert head == b"AFS\x00"
