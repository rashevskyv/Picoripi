"""PlayStation 1 disc reader (core/containers/psx_disc.py) on a synthetic MODE2/2352 disc: the ISO 9660 volume, the
boot line of SYSTEM.CNF, an interleaved (XA) stream file, and the refusals. No owner files are needed."""
import struct

import pytest

import romhacking_root

from core.containers.image_files import ImageError
from core.containers.psx_disc import XA_INTERLEAVED, fix_sector, identify_psx, open_psx, product_code, write_file

RAW = 2352
SECTOR = 2048


def raw_mode2(user: bytes = b"") -> bytes:
    """A Mode 2 Form 1 raw sector: sync, header (mode 2), 8-byte subheader, 2048 user bytes, EDC/ECC (zeros)."""
    body = user.ljust(SECTOR, b"\x00")
    return b"\x00" + b"\xff" * 10 + b"\x00" + b"\x00\x00\x00\x02" + b"\x00" * 8 + body + b"\x00" * 280


def dir_record(name: bytes, extent: int, size: int, is_dir: bool, xa_attr: int | None = None) -> bytes:
    pad = 1 if len(name) % 2 == 0 else 0
    system_use = b""
    if xa_attr is not None:
        system_use = struct.pack(">H", xa_attr) + b"XA" + b"\x00" * 10
    length = 33 + len(name) + pad + len(system_use)
    rec = bytearray(length)
    rec[0] = length
    struct.pack_into("<I", rec, 2, extent)
    struct.pack_into(">I", rec, 6, extent)
    struct.pack_into("<I", rec, 10, size)
    struct.pack_into(">I", rec, 14, size)
    rec[25] = 2 if is_dir else 0
    rec[32] = len(name)
    rec[33:33 + len(name)] = name
    rec[33 + len(name) + pad:] = system_use
    return bytes(rec)


def pvd(root_extent: int, root_size: int) -> bytes:
    body = bytearray(SECTOR)
    body[0] = 1
    body[1:6] = b"CD001"
    body[6] = 1
    body[156:190] = dir_record(b"\x00", root_extent, root_size, True)
    return bytes(body)


def directory(*records: bytes) -> bytes:
    return b"".join(records).ljust(SECTOR, b"\x00")


def make_disc(folder, boot: bytes = b"BOOT = cdrom:\\SCUS_944.57;1\r\nTCB = 4\r\n", with_pvd: bool = True):
    """Sectors: 0..15 system area, 16 PVD, 17 terminator, 18 root, 19 SYSTEM.CNF, 20 FIELD, 21 3034.MDP,
    22 an interleaved stream. Returns the cue sheet path."""
    sectors = [raw_mode2() for _ in range(23)]
    if with_pvd:
        sectors[16] = raw_mode2(pvd(18, SECTOR))
    sectors[17] = raw_mode2(b"\xff" + b"CD001" + b"\x01" + b"\x00" * (SECTOR - 7))
    sectors[18] = raw_mode2(directory(
        dir_record(b"\x00", 18, SECTOR, True), dir_record(b"\x01", 18, SECTOR, True),
        dir_record(b"SYSTEM.CNF;1", 19, len(boot), False),
        dir_record(b"FIELD", 20, SECTOR, True)))
    sectors[19] = raw_mode2(boot)
    sectors[20] = raw_mode2(directory(
        dir_record(b"\x00", 20, SECTOR, True), dir_record(b"\x01", 18, SECTOR, True),
        dir_record(b"3034.MDP;1", 21, 5, False),
        dir_record(b"MOV.STR;1", 22, SECTOR, False, xa_attr=0x3D55)))
    sectors[21] = raw_mode2(b"hello")
    sectors[22] = raw_mode2(b"stream")
    cue = folder / "disc.cue"
    (folder / "disc.bin").write_bytes(b"".join(sectors))
    cue.write_text('FILE "disc.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n', encoding="ascii")
    return str(cue)


def test_identify_reads_product_code_from_system_cnf(tmp_path):
    cue = make_disc(tmp_path)
    assert identify_psx(cue) == {"kind": "psx", "game_id": "SCUS-94457", "encrypted": False}


def test_files_list_paths_and_read_back(tmp_path):
    image = open_psx(make_disc(tmp_path))
    names = {entry.path: entry for entry in image.files()}
    assert "FIELD/3034.MDP" in names
    assert image.read_file(names["FIELD/3034.MDP"]) == b"hello"
    assert names["SYSTEM.CNF"].size > 0


def test_interleaved_stream_is_flagged_and_not_read(tmp_path):
    image = open_psx(make_disc(tmp_path))
    stream = {entry.path: entry for entry in image.files()}["FIELD/MOV.STR"]
    assert stream.interleaved is True
    assert XA_INTERLEAVED == 0x2000
    with pytest.raises(ImageError):
        image.read_file(stream)


def test_plain_file_is_not_interleaved(tmp_path):
    image = open_psx(make_disc(tmp_path))
    assert {entry.path: entry for entry in image.files()}["FIELD/3034.MDP"].interleaved is False


def test_disc_without_volume_is_refused(tmp_path):
    with pytest.raises(ImageError):
        open_psx(make_disc(tmp_path, with_pvd=False))


def test_disc_without_boot_line_is_not_identified(tmp_path):
    assert identify_psx(make_disc(tmp_path, boot=b"VMODE = NTSC\r\n")) is None


@pytest.mark.parametrize("boot, code", [
    ("SCUS_944.57", "SCUS-94457"),
    ("SCUS_944.65", "SCUS-94465"),
    ("SLUS-00123", "SLUS-00123"),
])
def test_product_code_form(boot, code):
    assert product_code(boot) == code


REAL_CUE = romhacking_root.under(r"Grandia\Grandia\PlayStation\ISO\Grandia disc 1.cue")


@pytest.mark.skipif(not __import__("os").path.exists(REAL_CUE), reason="the owner's Grandia disc 1 is not on disk")
def test_real_disc_1_identifies_and_reads_a_field_script():
    assert identify_psx(REAL_CUE) == {"kind": "psx", "game_id": "SCUS-94457", "encrypted": False}
    image = open_psx(REAL_CUE)
    entries = {entry.path: entry for entry in image.files()}
    script = entries["FIELD/3034.MDP"]
    assert script.size == 425984
    assert image.read_file(script).count(b"\x0f\x03\x0a\x0c\x00") >= 2   # the speaker sequence of a dialogue file
    assert entries["MOV00.STR"].interleaved is True


def test_images_identify_and_extract_a_psx_cue(tmp_path):
    from core.project_library import images

    cue = make_disc(tmp_path / "src") if (tmp_path / "src").mkdir() is None else None
    assert images.identify(cue) == {"kind": "psx", "game_id": "SCUS-94457", "encrypted": False}
    out = tmp_path / "out"
    assert images.extract(cue, str(out), lambda _pct, _name: None, lambda: False) == str(out)
    assert (out / "FIELD" / "3034.MDP").read_bytes() == b"hello"
    assert not (out / "FIELD" / "MOV.STR").exists()


def _sector_is_consistent(raw: bytes) -> bool:
    """A raw sector is consistent when its EDC and ECC rebuild to the same bytes from its user data."""
    rebuilt = bytearray(raw)
    rebuilt[2072:2352] = bytes(280)
    fix_sector(rebuilt)
    return bytes(rebuilt) == raw


def _script_entry(image, path="FIELD/3034.MDP"):
    return {entry.path: entry for entry in image.files()}[path]


def test_write_file_replaces_the_bytes_and_keeps_the_sector_consistent(tmp_path):
    cue = make_disc(tmp_path)
    before = (tmp_path / "disc.bin").read_bytes()
    entry = _script_entry(open_psx(cue))
    assert write_file(cue, entry, b"HOLA!") == 1
    after = (tmp_path / "disc.bin").read_bytes()
    assert after[21 * RAW + 24:21 * RAW + 24 + 5] == b"HOLA!"
    assert _sector_is_consistent(after[21 * RAW:22 * RAW])
    assert after[22 * RAW:23 * RAW] == before[22 * RAW:23 * RAW]        # the next sector is untouched
    assert open_psx(cue).read_file(_script_entry(open_psx(cue))) == b"HOLA!"


def test_write_file_refuses_a_length_change_and_leaves_the_disc(tmp_path):
    cue = make_disc(tmp_path)
    before = (tmp_path / "disc.bin").read_bytes()
    with pytest.raises(ImageError):
        write_file(cue, _script_entry(open_psx(cue)), b"too long")
    assert (tmp_path / "disc.bin").read_bytes() == before


def test_write_file_with_the_same_bytes_rewrites_nothing(tmp_path):
    cue = make_disc(tmp_path)
    before = (tmp_path / "disc.bin").read_bytes()
    assert write_file(cue, _script_entry(open_psx(cue)), b"hello") == 0
    assert (tmp_path / "disc.bin").read_bytes() == before


def test_write_file_refuses_an_interleaved_stream(tmp_path):
    cue = make_disc(tmp_path)
    stream = _script_entry(open_psx(cue), "FIELD/MOV.STR")
    with pytest.raises(ImageError):
        write_file(cue, stream, b"x" * stream.size)


@pytest.mark.skipif(not __import__("os").path.exists(REAL_CUE), reason="the owner's Grandia disc 1 is not on disk")
def test_real_disc_sectors_rebuild_their_edc_and_ecc_byte_for_byte():
    """Zeroing the EDC and ECC and rebuilding them gives the original bytes: the code matches the disc's own sectors."""
    from core.containers.gdrom import parse_layout

    seg = parse_layout(REAL_CUE)[0]
    with open(seg.path, "rb") as handle:
        for lba in range(seg.first + 1, seg.first + 201):
            handle.seek(seg.file_offset + (lba - seg.first) * seg.raw)
            raw = handle.read(seg.raw)
            if raw[18] & 0x20:
                continue
            assert _sector_is_consistent(raw), lba


def test_write_set_copies_the_set_and_patches_only_the_copy(tmp_path):
    from core.containers.psx_disc import write_set

    src = tmp_path / "src"
    src.mkdir()
    cue = make_disc(src)
    original = (src / "disc.bin").read_bytes()
    out = tmp_path / "out"
    result = write_set(cue, str(out), {"FIELD/3034.MDP": b"HOLA!"}, lambda p, n: None, lambda: False)
    assert result == str(out / "disc.cue")
    assert (out / "disc.cue").is_file()
    assert (src / "disc.bin").read_bytes() == original           # the source set is untouched
    disc = open_psx(result)
    assert disc.read_file(next(e for e in disc.files() if e.path == "FIELD/3034.MDP")) == b"HOLA!"
    assert _sector_is_consistent((out / "disc.bin").read_bytes()[21 * RAW:22 * RAW])


def test_write_set_refuses_an_unknown_path_and_a_cancel_returns_none(tmp_path):
    from core.containers.psx_disc import write_set

    src = tmp_path / "src"
    src.mkdir()
    cue = make_disc(src)
    with pytest.raises(ImageError):
        write_set(cue, str(tmp_path / "out"), {"NOPE.MDP": b"x"}, lambda p, n: None, lambda: False)
    assert write_set(cue, str(tmp_path / "out2"), {}, lambda p, n: None, lambda: True) is None


def test_write_set_refuses_the_folder_of_the_source_set(tmp_path):
    from core.containers.psx_disc import write_set

    cue = make_disc(tmp_path)
    with pytest.raises(ImageError):
        write_set(cue, str(tmp_path), {}, lambda p, n: None, lambda: False)
