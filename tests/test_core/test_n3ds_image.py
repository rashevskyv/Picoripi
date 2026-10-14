"""Nintendo 3DS images, built in the test: a decrypted (NoCrypto) program is read without any key.

The builders write the smallest valid layouts: an NCCH with an exheader, an ExeFS and an IVFC RomFS with one
directory; a card image (CCI) and a CIA around it. Encrypted content is refused with the reason, never read.
"""
import io
import struct

import pytest

from core.containers import n3ds, romfs
from core.containers.console_crypto import key_source
from core.containers.image_files import ImageError
from core.containers.nitro import blz_compress
from core.project_library import images

NO = 0xFFFFFFFF
UNIT = 0x200
EXHEADER = (bytes(range(256)) * 8)[:0x0D] + b"\0" + (bytes(range(256)) * 8)[0x0E:]   # flag byte 0: not packed
CODE = b"CODE" * 64


def _pad4(data):
    return data.ljust((len(data) + 3) // 4 * 4, b"\0")


def _name(text):
    return text.encode("utf-16-le")


def _dir_entry(parent, sibling, child_dir, child_file, name=""):
    raw = _name(name)
    return _pad4(struct.pack("<IIIIII", parent, sibling, child_dir, child_file, NO, len(raw)) + raw)


def _file_entry(parent, sibling, offset, size, name):
    raw = _name(name)
    return _pad4(struct.pack("<IIQQII", parent, sibling, offset, size, NO, len(raw)) + raw)


def build_romfs():
    """IVFC RomFS: the root holds a.bin ('hello'); the directory d holds b.txt ('xyz')."""
    dir_meta = _dir_entry(0, NO, 0x18, 0) + _dir_entry(0, NO, NO, 0x2C, "d")
    file_meta = _file_entry(0, NO, 0, 5, "a.bin") + _file_entry(0x18, NO, 8, 3, "b.txt")
    data = b"hello".ljust(8, b"\0") + b"xyz"
    dir_off = 0x28
    file_off = dir_off + len(dir_meta)
    data_off = file_off + len(file_meta)
    header = struct.pack("<IIIIIIIIII", 0x28, 0, 0, dir_off, len(dir_meta), 0, 0, file_off, len(file_meta), data_off)
    level3 = _pad4(header + dir_meta) + file_meta
    level3 = _pad4(level3) + data
    ivfc = bytearray(0x1000)
    ivfc[0:4] = b"IVFC"
    struct.pack_into("<I", ivfc, 8, 0)       # master hash size
    struct.pack_into("<I", ivfc, 0x4C, 12)   # level 3 block size: 2**12
    return bytes(ivfc) + level3


def build_ncch(encrypted=False, romfs=None, tamper=None, packed=False):
    romfs = build_romfs() if romfs is None else romfs
    code = blz_compress(CODE) if packed else CODE
    exheader = bytearray(EXHEADER)
    exheader[0x0D] = 0x01 if packed else 0          # exheader flag: bit 0 = the ExeFS code is BLZ-packed
    exefs_header = bytearray(0x200)
    exefs_header[0:5] = b".code"
    struct.pack_into("<II", exefs_header, 8, 0, len(code))
    exefs = _pad4(bytes(exefs_header) + code).ljust(((0x200 + len(code) + UNIT - 1) // UNIT) * UNIT, b"\0")
    romfs = romfs.ljust(((len(romfs) + UNIT - 1) // UNIT) * UNIT, b"\0")
    header = bytearray(0x200)
    header[0x100:0x104] = b"NCCH"
    header[0x118:0x120] = b"\x01\x00\x00\x00\x00\x00\x00\x00"       # program id, little-endian
    header[0x150:0x15A] = b"CTR-P-TEST"
    struct.pack_into("<I", header, 0x180, 0x400)                      # exheader size
    header[0x188 + 7] = 0 if encrypted else 0x04                       # NoCrypto flag
    exefs_at = 5                                                       # after the header and the exheader
    romfs_at = exefs_at + len(exefs) // UNIT
    struct.pack_into("<II", header, 0x1A0, exefs_at, len(exefs) // UNIT)
    struct.pack_into("<II", header, 0x1B0, romfs_at, len(romfs) // UNIT)
    body = bytes(header) + bytes(exheader).ljust(0x800, b"\0") + exefs + romfs
    return tamper(bytearray(body)) if tamper else body


def build_cci(ncch):
    header = bytearray(0x200)
    header[0x100:0x104] = b"NCSD"
    struct.pack_into("<II", header, 0x120, 0x4000 // UNIT, len(ncch) // UNIT)
    return bytes(header).ljust(0x4000, b"\0") + ncch


def build_cia(ncch, encrypted=False):
    """A CIA whose only content (index 0) is ``ncch``: one ticket, one title metadata, then the content."""
    ticket = bytearray(0x350)
    struct.pack_into(">I", ticket, 0, 0x10004)
    body = bytearray(0xC4 + 0x900 + 0x30)
    body[0x4C:0x54] = bytes.fromhex("0004000000012345")
    struct.pack_into(">H", body, 0x9E, 1)
    struct.pack_into(">IHHQ", body, 0xC4 + 0x900, 0, 0, 1 if encrypted else 0, len(ncch))
    tmd = bytearray(0x140) + body
    struct.pack_into(">I", tmd, 0, 0x10004)
    header = bytearray(0x2020)
    struct.pack_into("<IHHIIIIQ", header, 0, 0x2020, 0, 0, 0, len(ticket), len(tmd), 0, len(ncch))
    header[0x20] = 0x80                                                # content index 0 is present
    out = bytes(header).ljust(0x2040, b"\0")                           # the header is aligned to 0x40
    out += bytes(ticket).ljust(0x380, b"\0")
    out += bytes(tmd).ljust(((len(tmd) + 0x3F) // 0x40) * 0x40, b"\0")
    return out + ncch


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_decrypted_card_image_lists_exheader_exefs_and_romfs_without_a_key(tmp_path):
    path = _write(tmp_path, "game.3ds", build_cci(build_ncch()))

    found = images.identify(path)

    assert found["kind"] == "3ds"
    assert found["game_id"] == "TEST"
    assert found["encrypted"] is False
    assert images.needs_key(path) is None
    out = tmp_path / "out"
    assert images.extract(path, out, lambda p, t: None, lambda: False) == str(out)
    assert (out / "exheader.bin").read_bytes() == EXHEADER
    assert (out / "exefs" / "code.bin").read_bytes() == CODE
    assert (out / "romfs" / "a.bin").read_bytes() == b"hello"
    assert (out / "romfs" / "d" / "b.txt").read_bytes() == b"xyz"


def test_packed_code_section_is_written_decoded(tmp_path):
    path = _write(tmp_path, "packed.cci", build_cci(build_ncch(packed=True)))
    out = tmp_path / "out"

    images.extract(path, out, lambda p, t: None, lambda: False)

    assert (out / "exefs" / "code.bin").read_bytes() == CODE
    assert (out / "exheader.bin").read_bytes() == bytes(
        EXHEADER[:0x0D] + b"\x01" + EXHEADER[0x0E:])


def test_decrypted_cia_reads_its_main_content_without_a_key(tmp_path):
    path = _write(tmp_path, "game.cia", build_cia(build_ncch()))

    found = images.identify(path)

    assert found["kind"] == "3ds"
    assert found["game_id"] == "TEST"
    assert found["encrypted"] is False
    with images.open_image(path) as reader:
        assert sorted(entry.path for entry in reader.entries()) == [
            "exefs/code.bin", "exheader.bin", "romfs/a.bin", "romfs/d/b.txt"]


def test_encrypted_program_needs_its_key_file_and_no_key_is_read(tmp_path):
    path = _write(tmp_path, "locked.cci", build_cci(build_ncch(encrypted=True)))

    assert images.identify(path)["encrypted"] is True
    assert images.needs_key(path) == "3ds"
    with pytest.raises(ImageError, match="needs its key file"):
        with images.open_image(path):
            pass


def test_encrypted_program_with_a_key_file_that_holds_no_keys_is_refused(tmp_path):
    path = _write(tmp_path, "locked.cci", build_cci(build_ncch(encrypted=True)))
    key_file = _write(tmp_path, "keyfile.txt", b"placeholder")

    with key_source(lambda console: str(key_file) if console == "3ds" else None):
        with pytest.raises(ImageError, match="has no KeyX for slot 0x2C"):
            with images.open_image(path):
                pass


def test_encrypted_cia_is_refused_with_the_reason(tmp_path):
    path = _write(tmp_path, "locked.cia", build_cia(build_ncch(), encrypted=True))

    assert images.identify(path)["encrypted"] is True
    with pytest.raises(ImageError, match="needs its key file"):
        with images.open_image(path):
            pass


def test_romfs_name_with_a_separator_is_refused():
    bad = build_romfs().replace(_name("a.bin"), _name("a/bin"))
    with pytest.raises(ImageError, match="unsafe file name"):
        n3ds.N3dsImage(io.BytesIO(build_cci(build_ncch(romfs=bad))))


def test_romfs_entry_outside_the_image_is_refused():
    def point_past_end(body):
        romfs = body.index(b"IVFC")
        level3 = romfs + 0x1000
        file_meta = level3 + struct.unpack_from("<I", body, level3 + 0x1C)[0]
        struct.pack_into("<Q", body, file_meta + 0x08, 0x10000000)
        return body

    with pytest.raises(ImageError, match="ends past the RomFS"):
        n3ds.N3dsImage(io.BytesIO(build_cci(build_ncch(tamper=point_past_end))))


def test_romfs_with_more_directories_than_the_limit_is_refused(monkeypatch):
    monkeypatch.setattr(romfs, "MAX_FILES", 1)    # the root and one file fit; the subfolder d does not

    with pytest.raises(ImageError, match="too many directories"):
        n3ds.N3dsImage(io.BytesIO(build_cci(build_ncch())))


def test_bytes_that_are_no_3ds_image_are_not_identified(tmp_path):
    path = _write(tmp_path, "noise.bin", bytes(range(256)) * 16)

    assert images.identify(path) is None
    with pytest.raises(ImageError, match="not a GameCube or Nintendo DS image"):
        with images.open_image(path):
            pass


def test_cia_with_an_empty_ticket_is_refused_with_the_reason():
    cia = bytearray(build_cia(build_ncch()))
    struct.pack_into("<I", cia, 0x0C, 0)                  # ticket size 0

    with pytest.raises(ImageError, match="bad size"):
        n3ds.N3dsImage(io.BytesIO(bytes(cia)))


def test_packed_code_section_over_the_size_limit_is_refused(monkeypatch):
    monkeypatch.setattr(n3ds, "MAX_CODE", 16)

    with pytest.raises(ImageError, match="packed code section is too large"):
        n3ds.N3dsImage(io.BytesIO(build_cci(build_ncch(packed=True))))
