"""The Nintendo DS cartridge writer (``core.containers.nds_write``) and the NARC writer (``narc_write``).

Synthetic images from ``tests/nds_rom.py`` cover the rules: unchanged = byte-exact, a grown file relocates and the
tables and the header CRC are written again. The real Platinum ROM (when the workspace is on disk) proves the writer
on a full image: unchanged rebuild byte-exact, a NARC repacked byte-exact, a grown message bank read back.
"""
import struct

import pytest

import romhacking_root
from core.containers import nds_write, narc_write
from core.containers.nds import NdsImage
from core.containers.narc_members import narc_members
from nds_rom import narc, nds_rom

FILES = {
    "a/0/0/1": b"ONE" * 100,
    "a/0/0/2": b"TWO" * 37,
    "a/1/0/0": bytes(range(256)) * 3,
}


def _image():
    return nds_rom(FILES)


def test_crc16_matches_the_modbus_test_vector():
    assert nds_write.crc16(b"123456789") == 0x4B37


def test_unchanged_rebuild_gives_the_same_image_back():
    rom = _image()
    assert nds_write.rebuild_nds(rom, {}) == rom
    assert nds_write.rebuild_nds(rom, {"a/0/0/1": FILES["a/0/0/1"]}) == rom


def test_a_grown_file_relocates_and_the_rest_reads_back():
    rom = _image()
    bigger = FILES["a/0/0/1"] + b"!" * 900
    built = nds_write.rebuild_nds(rom, {"a/0/0/1": bigger})
    files = nds_write.nitro_files(built)
    assert files["a/0/0/1"] == bigger
    assert files["a/0/0/2"] == FILES["a/0/0/2"]
    assert files["a/1/0/0"] == FILES["a/1/0/0"]
    nds_write.check_header(built)
    assert struct.unpack_from("<I", built, 0x80)[0] <= len(built)


def test_relocated_files_start_on_0x200_and_the_capacity_covers_the_image():
    built = nds_write.rebuild_nds(_image(), {"a/0/0/1": b"x" * 5000})
    fat_at = struct.unpack_from("<I", built, 0x48)[0]
    spans = [struct.unpack_from("<II", built, fat_at + 8 * i) for i in range(3)]
    for start, _end in spans:
        assert start % 0x200 == 0
    assert len(built) == 0x20000 << built[0x14]
    assert struct.unpack_from("<I", built, 0x80)[0] <= len(built)


def test_a_shrunk_file_reads_back_and_the_header_crc_is_correct():
    built = nds_write.rebuild_nds(_image(), {"a/0/0/2": b"short"})
    assert nds_write.nitro_files(built)["a/0/0/2"] == b"short"
    nds_write.check_header(built)


def test_the_crc_is_checked_on_a_damaged_header():
    built = bytearray(nds_write.rebuild_nds(_image(), {"a/0/0/2": b"short"}))
    built[0x30] ^= 0xFF
    with pytest.raises(nds_write.NdsWriteError):
        nds_write.check_header(bytes(built))


def test_an_unknown_file_is_refused():
    with pytest.raises(nds_write.NdsWriteError, match="no such NitroFS files"):
        nds_write.rebuild_nds(_image(), {"a/9/9/9": b"x"})


def test_the_rebuilt_image_opens_with_the_picoripi_reader():
    import io
    built = nds_write.rebuild_nds(_image(), {"a/0/0/1": b"Z" * 3000})
    image = NdsImage(io.BytesIO(built))
    names = {entry.path: entry for entry in image.entries()}
    assert image.read(names["a/0/0/1"]) == b"Z" * 3000


def test_narc_unchanged_is_the_same_bytes_and_a_grown_member_reads_back():
    archive = narc([b"alpha", b"beta", b"gamma"])
    assert narc_write.narc_rebuild(archive, narc_members(archive)) == archive
    grown = narc_write.narc_rebuild(archive, [b"alpha", b"a much longer beta" * 4, b"gamma"])
    assert narc_members(grown) == [b"alpha", b"a much longer beta" * 4, b"gamma"]
    assert struct.unpack_from("<I", grown, 8)[0] == len(grown)


def test_narc_repack_reproduces_a_fixture_archive():
    archive = narc([b"one", b"three", b"5", b"seven7"])
    assert narc_write.narc_repack(archive) == archive


def test_narc_member_count_must_not_change():
    with pytest.raises(narc_write.NarcWriteError, match="members"):
        narc_write.narc_rebuild(narc([b"a", b"b"]), [b"a"])


# ---------------------------------------------------------------- real Platinum image (skipped without the workspace)

PLATINUM = ("Pokemon", "Platinum", "ISO", "Pokemon - Platinum Version (USA).nds")


def _platinum():
    reason = romhacking_root.missing(*PLATINUM)
    if reason:
        pytest.skip(reason)
    return romhacking_root.path(*PLATINUM).read_bytes()


def test_real_platinum_unchanged_rebuild_is_byte_exact():
    rom = _platinum()
    assert nds_write.rebuild_nds(rom, {}) == rom


def test_real_platinum_narc_repack_is_byte_exact():
    rom = _platinum()
    members = nds_write.nitro_files(rom)
    for path in ("msgdata/msg.narc", "msgdata/pl_msg.narc"):
        assert narc_write.narc_repack(members[path]) == members[path], path


def test_real_platinum_grown_text_bank_builds_and_reads_back():
    rom = _platinum()
    members = nds_write.nitro_files(rom)
    bank_narc = members["msgdata/msg.narc"]
    banks = narc_members(bank_narc)
    edited = list(banks)
    edited[0] = banks[0] + b"\x00" * 64           # a longer bank: the NARC member grows
    new_narc = narc_write.narc_rebuild(bank_narc, edited)
    built = nds_write.rebuild_nds(rom, {"msgdata/msg.narc": new_narc})
    nds_write.check_header(built)
    after = nds_write.nitro_files(built)
    assert narc_members(after["msgdata/msg.narc"])[0] == edited[0]
    assert after["msgdata/pl_msg.narc"] == members["msgdata/pl_msg.narc"]
    assert len(built) == 0x20000 << built[0x14]
