"""SwitchImage on synthetic packages: an NSP with a ticket, a program NCA (XTS header, key area or ticket key, AES-CTR
sections), an ExeFS and a RomFS. Every key is random and written by the test; the test encrypts with its own code."""
import io
import os
import struct

import pytest

pytest.importorskip("Crypto.Cipher.AES", reason="the Switch image tests need pycryptodome")
from Crypto.Cipher import AES  # noqa: E402
zstd = pytest.importorskip("compression.zstd", reason="the NCZ tests compress with Python 3.14 zstd")

from core.containers import console_crypto  # noqa: E402
from core.containers.image_files import ImageError  # noqa: E402
from core.containers.switch_crypto import load_keys  # noqa: E402
from core.containers.switch_images import SwitchImage  # noqa: E402
from core.project_library import images  # noqa: E402

NO = 0xFFFFFFFF
SECTOR = 0x200
HEADER = 0xC00
ROMFS_HEADER = 0x50
TITLE = 0x0100ABCD00000000
MAGIC_SECTIONS = b"NCZSECTN"


def _ecb(key, data, decrypt=False):
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.decrypt(data) if decrypt else cipher.encrypt(data)


def _xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def _double(tweak):
    value = int.from_bytes(tweak, "little") << 1
    if value >> 128:
        value = (value & ((1 << 128) - 1)) ^ 0x87
    return value.to_bytes(16, "little")


def _xts_encrypt(key, data):
    out = bytearray()
    for index in range(len(data) // SECTOR):
        tweak = _ecb(key[16:], index.to_bytes(16, "big"))
        for pos in range(index * SECTOR, (index + 1) * SECTOR, 16):
            out += _xor(_ecb(key[:16], _xor(data[pos:pos + 16], tweak)), tweak)
            tweak = _double(tweak)
    return bytes(out)


def _ctr(key, counter, data):
    """AES-CTR over ``data`` with a 128-bit counter block; the caller passes the NCA-relative block number."""
    out = bytearray()
    for index in range(0, len(data), 16):
        keystream = _ecb(key, ((counter + index // 16) & ((1 << 128) - 1)).to_bytes(16, "big"))
        out += _xor(data[index:index + 16], keystream)
    return bytes(out)


def _pad(data, size=SECTOR):
    return data + bytes(-len(data) % size)


def _pfs0(entries):
    names = b""
    offsets = []
    for name, _ in entries:
        offsets.append(len(names))
        names += name.encode() + b"\0"
    table = b""
    data = b""
    for (name, body), name_at in zip(entries, offsets):
        table += struct.pack("<QQII", len(data), len(body), name_at, 0)
        data += body
    return b"PFS0" + struct.pack("<III", len(entries), len(names), 0) + table + names + data


def _romfs(root_files, sub_name, sub_files):
    """A Switch RomFS: root files, one directory with files. Returns the region (header first)."""
    items = list(root_files.items()) + list(sub_files.items())
    count = len(root_files)
    positions = []
    at = 0
    for name, _ in items:
        positions.append(at)
        at += 0x20 + ((len(name.encode()) + 3) & ~3)
    meta = bytearray(at)
    data = bytearray()
    for index, (name, body) in enumerate(items):
        end = count if index < count else len(items)
        sibling = positions[index + 1] if index + 1 < end else NO
        raw = name.encode()
        struct.pack_into("<IIQQII", meta, positions[index], 0, sibling, len(data), len(body), 0, len(raw))
        meta[positions[index] + 0x20:positions[index] + 0x20 + len(raw)] = raw
        data += body
    sub_name_raw = sub_name.encode()
    dirs = bytearray(0x30 + ((len(sub_name_raw) + 3) & ~3))   # the root entry, then the subdirectory's entry
    struct.pack_into("<6I", dirs, 0, 0, NO, 0x18, positions[0] if count else NO, 0, 0)
    struct.pack_into("<6I", dirs, 0x18, 0, NO, NO, positions[count] if sub_files else NO, 0, len(sub_name_raw))
    dirs[0x30:0x30 + len(sub_name_raw)] = sub_name_raw
    dirs_at = ROMFS_HEADER
    meta_at = dirs_at + len(dirs)
    data_at = meta_at + len(meta)
    head = struct.pack("<10Q", ROMFS_HEADER, 0, 0, dirs_at, len(dirs), 0, 0, meta_at, len(meta), data_at)
    return head + bytes(dirs) + bytes(meta) + bytes(data)


def _ticket(rights, enc_title_key, personal=False):
    ticket = bytearray(0x2C0)
    ticket[0x180:0x190] = enc_title_key
    ticket[0x281] = 1 if personal else 0
    ticket[0x2A0:0x2B0] = rights
    return bytes(ticket)


def _section(body, fs, crypto, iv=None, field=(0x40, 0)):
    return {"body": body, "fs": fs, "crypto": crypto, "iv": iv or os.urandom(8), "field": field}


BODY = 0x4000   # where the sections start: an NCZ copies this many bytes of NCA header first


def _nca(header_key, content_key, area_key, sections, content_type=0, rights=bytes(16)):
    """(NCA bytes, plain body, placed sections). The NCA holds the sections from BODY on, encrypted as their crypto type
    says. ``plain`` is the body with the sections decrypted; ``placed`` lists (start, size, crypto type, IV) per section.
    ``content_key`` encrypts the sections; with no rights ID the key area holds it (wrapped with ``area_key``), otherwise
    the ticket holds it."""
    body = bytearray()
    plain = bytearray()
    table = []
    fshs = []
    placed = []
    for spec in sections:
        start = BODY + len(body)
        data = _pad(spec["body"])
        plain += data
        if spec["crypto"] == 3:
            data = _ctr(content_key, (int.from_bytes(spec["iv"], "little") << 64) | (start // 16), data)
        body += data
        table.append((start // SECTOR, (BODY + len(body)) // SECTOR))
        placed.append((start, len(data), spec["crypto"], spec["iv"]))
        fsh = bytearray(0x200)
        fsh[2] = spec["fs"]
        fsh[4] = spec["crypto"]
        fsh[0x140:0x148] = spec["iv"]
        struct.pack_into("<Q", fsh, spec["field"][0], spec["field"][1])
        fshs.append(bytes(fsh))
    head = bytearray(HEADER)
    head[0x200:0x204] = b"NCA3"
    head[0x205] = content_type
    head[0x206] = 1
    struct.pack_into("<Q", head, 0x210, TITLE)
    head[0x230:0x240] = rights
    for index, (start, end) in enumerate(table):
        struct.pack_into("<II", head, 0x240 + index * 0x10, start, end)
    if rights == bytes(16):
        area = bytearray(os.urandom(0x40))
        area[0x20:0x30] = content_key
        head[0x300:0x340] = _ecb(area_key, bytes(area))
    else:
        head[0x300:0x340] = os.urandom(0x40)
    for index, fsh in enumerate(fshs):
        head[0x400 + index * 0x200:0x600 + index * 0x200] = fsh
    return _xts_encrypt(header_key, bytes(head)) + bytes(BODY - HEADER) + bytes(body), bytes(plain), placed


def _material():
    return {
        "header_key": os.urandom(32), "master_key_00": os.urandom(16),
        "aes_kek_generation_source": os.urandom(16), "aes_key_generation_source": os.urandom(16),
        "key_area_key_application_source": os.urandom(16), "titlekek_source": os.urandom(16),
    }


def _derived(material):
    kek = _ecb(material["master_key_00"], material["aes_kek_generation_source"], decrypt=True)
    source_kek = _ecb(kek, material["key_area_key_application_source"], decrypt=True)
    area = _ecb(source_kek, material["aes_key_generation_source"], decrypt=True)
    titlekek = _ecb(material["master_key_00"], material["titlekek_source"], decrypt=True)
    return area, titlekek


def _key_file(tmp_path, material, direct=False, extra=()):
    """The key file: the sources, or with ``direct`` only the header key and the derived keys."""
    if direct:
        area, titlekek = _derived(material)
        lines = [f"header_key = {material['header_key'].hex()}",
                 f"key_area_key_application_00 = {area.hex()}", f"titlekek_00 = {titlekek.hex()}"]
    else:
        lines = [f"{name} = {value.hex()}" for name, value in material.items()]
    path = tmp_path / "prod.keys"
    path.write_text("\n".join(list(lines) + list(extra)), encoding="utf-8")
    return str(path)


BIG = bytes(range(256)) * 160   # 40960 bytes: a body of three NCZ blocks (zstd frames compress it)


def _program_sections(random_romfs=False, big=False):
    exefs = _pfs0([("main", b"MAIN" * 300), ("main.npdm", b"NPDM" * 50)])
    sub = {"b.bin": b"bravo" * 30}
    if big:
        sub["big.bin"] = BIG
    romfs = _romfs({"a.bin": b"alpha" * 40}, "dir", sub)
    romfs_body = bytes(SECTOR) + (os.urandom(0x300) if random_romfs else romfs)
    return [
        _section(exefs, fs=1, crypto=3, field=(0x40, 0)),
        _section(romfs_body, fs=0, crypto=4 if random_romfs else 3, field=(0x90, SECTOR)),
    ]


BLOCK_EXP = 14   # NCZBLOCK blocks of 16 KiB in the synthetic files


def _ncz(nca, plain, placed, key, mode):
    """An NCZ of ``nca`` built the way nsz builds one: the first 0x4000 bytes of the NCA, the section table, then the body
    (``plain``, the sections decrypted). ``solid``: one zstd frame. ``block``: NCZBLOCK blocks, each zstd or raw when
    zstd would not make it smaller, and the second block is raw by choice."""
    table = MAGIC_SECTIONS + struct.pack("<Q", len(placed))
    for start, size, crypto, iv in placed:
        table += struct.pack("<4Q", start, size, crypto, 0) + (key if crypto == 3 else bytes(16)) + iv + bytes(8)
    if mode == "solid":
        body = zstd.compress(plain)
    else:
        size = 1 << BLOCK_EXP
        pieces = [plain[pos:pos + size] for pos in range(0, len(plain), size)]
        packed = []
        for index, piece in enumerate(pieces):
            frame = zstd.compress(piece)
            packed.append(piece if index == 1 or len(frame) >= len(piece) else frame)
        head = b"NCZBLOCK" + bytes([2, 1, 0, BLOCK_EXP]) + struct.pack("<IQ", len(packed), len(plain))
        head += b"".join(struct.pack("<I", len(item)) for item in packed)
        body = head + b"".join(packed)
    return nca[:BODY] + table + body


def _package(material, *, ticketed=True, personal=False, meta_first=False, random_romfs=False, content_key=None,
             ncz=None, big=False):
    """The NSP bytes. ``ncz`` ("block" or "solid") stores the program NCA as an .ncz instead of an .nca."""
    header_key = material["header_key"]
    area, titlekek = _derived(material)
    content_key = content_key or os.urandom(16)
    sections = _program_sections(random_romfs, big)
    if ticketed:
        rights = os.urandom(16)
        nca, plain, placed = _nca(header_key, content_key, area, sections, rights=rights)
        ticket = _ticket(rights, _ecb(titlekek, content_key), personal)
    else:
        nca, plain, placed = _nca(header_key, content_key, area, sections)
        ticket = None
    entries = [("0100abcd00000000.nca", nca)]
    if ncz:
        entries = [("0100abcd00000000.ncz", _ncz(nca, plain, placed, content_key, ncz))]
    if ticket is not None:
        entries.append(("0100abcd00000000.tik", ticket))
    if meta_first:
        meta, _, _ = _nca(header_key, os.urandom(16), area, [], content_type=1)
        entries.insert(0, ("0100abcd00000000.cnmt.nca", meta))
    return _pfs0(entries)


def _read_all(nsp, keys, cache=None):
    """Every file of the package, read; the cache copy of an .nsz is deleted before this returns."""
    reader = SwitchImage(io.BytesIO(nsp), keys, cache)
    try:
        return {entry.path: reader.read(entry) for entry in reader.entries()}, reader
    finally:
        reader.close()


@pytest.mark.parametrize("ticketed", [True, False])
@pytest.mark.parametrize("direct", [False, True])
def test_reads_exefs_and_romfs_of_a_base_package(tmp_path, ticketed, direct):
    material = _material()
    content_key = os.urandom(16)
    nsp = _package(material, ticketed=ticketed, content_key=content_key)
    keys = load_keys(_key_file(tmp_path, material, direct=direct))

    files, reader = _read_all(nsp, keys)

    assert files == {
        "exefs/main": b"MAIN" * 300, "exefs/main.npdm": b"NPDM" * 50,
        "romfs/a.bin": b"alpha" * 40, "romfs/dir/b.bin": b"bravo" * 30,
    }
    assert reader.romfs_is_patch is False


def test_program_is_picked_by_content_type_not_by_file_order(tmp_path):
    material = _material()
    nsp = _package(material, meta_first=True)
    keys = load_keys(_key_file(tmp_path, material))

    files, _ = _read_all(nsp, keys)

    assert "exefs/main" in files and "romfs/a.bin" in files


def test_update_with_a_patch_romfs_lists_only_the_exefs(tmp_path):
    material = _material()
    nsp = _package(material, random_romfs=True)
    keys = load_keys(_key_file(tmp_path, material))

    files, reader = _read_all(nsp, keys)

    assert sorted(files) == ["exefs/main", "exefs/main.npdm"]
    assert reader.romfs_is_patch is True


def test_wrong_header_key_is_an_image_error_that_shows_no_key_text(tmp_path):
    material = _material()
    nsp = _package(material)
    other = dict(material, header_key=os.urandom(32))
    keys = load_keys(_key_file(tmp_path, other))

    with pytest.raises(ImageError) as caught:
        _read_all(nsp, keys)

    assert other["header_key"].hex() not in str(caught.value)
    assert material["header_key"].hex() not in str(caught.value)


def test_wrong_key_area_key_fails_the_exefs_check_not_with_garbage(tmp_path):
    material = _material()
    nsp = _package(material, ticketed=False)
    keys = load_keys(_key_file(tmp_path, material, extra=[f"key_area_key_application_00 = {os.urandom(16).hex()}"]))

    with pytest.raises(ImageError, match="does not decrypt"):
        _read_all(nsp, keys)


def test_truncated_package_is_an_image_error(tmp_path):
    material = _material()
    nsp = _package(material)
    keys = load_keys(_key_file(tmp_path, material))

    for cut in range(0, len(nsp), 61):
        with pytest.raises(ImageError):
            _read_all(nsp[:cut], keys)


def test_tampered_name_table_is_an_image_error(tmp_path):
    material = _material()
    nsp = bytearray(_package(material))
    nsp[0x10 + 2 * 0x18] = 0xFF    # the first name starts with an invalid UTF-8 byte
    keys = load_keys(_key_file(tmp_path, material))

    with pytest.raises(ImageError, match="unsafe"):
        _read_all(bytes(nsp), keys)


def test_personalised_ticket_is_refused(tmp_path):
    material = _material()
    nsp = _package(material, personal=True)
    keys = load_keys(_key_file(tmp_path, material))

    with pytest.raises(ImageError, match="personalised"):
        _read_all(nsp, keys)


def test_key_file_missing_a_needed_key_is_an_image_error(tmp_path):
    material = _material()
    nsp = _package(material, ticketed=False)
    partial = {"header_key": material["header_key"]}
    keys = load_keys(_key_file(tmp_path, partial))

    with pytest.raises(ImageError, match="no master_key_00"):
        _read_all(nsp, keys)


def test_cartridge_image_is_recognised_but_not_read(tmp_path):
    material = _material()
    keys = load_keys(_key_file(tmp_path, material))
    xci = bytearray(0x200)
    xci[0x100:0x104] = b"HEAD"

    with pytest.raises(ImageError, match="not read yet"):
        SwitchImage(io.BytesIO(bytes(xci)), keys).entries()


def test_reading_writes_no_file(tmp_path):
    material = _material()
    nsp = _package(material)
    keys = load_keys(_key_file(tmp_path, material))
    before = sorted(os.listdir(tmp_path))

    _read_all(nsp, keys)

    assert sorted(os.listdir(tmp_path)) == before


@pytest.mark.parametrize("mode", ["block", "solid"])
def test_ncz_reads_the_same_files_as_the_plain_nca(tmp_path, mode):
    material = _material()
    content_key = os.urandom(16)
    keys = load_keys(_key_file(tmp_path, material))
    cache = tmp_path / "cache"
    ncz_nsp = _package(material, content_key=content_key, big=True, ncz=mode)

    plain, _ = _read_all(_package(material, content_key=content_key, big=True), keys, cache)
    packed, _ = _read_all(ncz_nsp, keys, cache)

    assert MAGIC_SECTIONS in ncz_nsp
    assert packed == plain
    assert packed["romfs/dir/big.bin"] == BIG and packed["exefs/main"] == b"MAIN" * 300
    assert os.listdir(cache) == []


@pytest.mark.parametrize("field, value", [
    (16, 0x100),    # section 0 starts inside the NCA header
    (24, 0x2000),   # section 0 is too short: section 1 does not start where it ends
    (8, 5),         # five sections
])
def test_ncz_bad_section_table_is_an_image_error(tmp_path, field, value):
    material = _material()
    nsp = bytearray(_package(material, ncz="block", big=True))
    struct.pack_into("<Q", nsp, nsp.find(MAGIC_SECTIONS) + field, value)
    keys = load_keys(_key_file(tmp_path, material))

    with pytest.raises(ImageError):
        _read_all(bytes(nsp), keys, tmp_path / "cache")


def test_ncz_without_its_magic_is_an_image_error(tmp_path):
    material = _material()
    nsp = bytearray(_package(material, ncz="solid"))
    nsp[nsp.find(MAGIC_SECTIONS)] = ord("X")
    keys = load_keys(_key_file(tmp_path, material))

    with pytest.raises(ImageError, match="NCZSECTN"):
        _read_all(bytes(nsp), keys, tmp_path / "cache")


def test_ncz_corrupt_zstd_block_is_an_image_error_and_the_cache_is_removed(tmp_path):
    material = _material()
    nsp = bytearray(_package(material, ncz="block", big=True))
    at = nsp.find(MAGIC_SECTIONS)
    count = struct.unpack_from("<Q", nsp, at + 8)[0]
    block_head = at + 0x10 + 0x40 * count
    blocks = struct.unpack_from("<I", nsp, block_head + 12)[0]
    assert struct.unpack_from("<I", nsp, block_head + 0x18)[0] < 1 << BLOCK_EXP   # block 0 is a zstd frame
    first = block_head + 0x18 + 4 * blocks
    nsp[first:first + 4] = bytes(4)   # the zstd magic number
    keys = load_keys(_key_file(tmp_path, material))
    cache = tmp_path / "cache"
    reader = SwitchImage(io.BytesIO(bytes(nsp)), keys, cache)

    with pytest.raises(ImageError, match="corrupt"):
        reader.entries()
    assert os.listdir(cache) == []


def test_ncz_cancel_stops_the_decompression_between_blocks(tmp_path):
    material = _material()
    keys = load_keys(_key_file(tmp_path, material))
    cache = tmp_path / "cache"
    checks = []

    def cancel_from_the_second_check():
        checks.append(1)
        return len(checks) > 1

    reader = SwitchImage(io.BytesIO(_package(material, ncz="block", big=True)), keys, cache,
                         cancel_from_the_second_check)
    assert reader.entries() == []
    reader.close()

    assert len(checks) == 2
    assert os.listdir(cache) == []


def test_extract_unpacks_an_nsz_and_leaves_only_its_files(tmp_path):
    material = _material()
    keys_path = _key_file(tmp_path, material)
    nsz = tmp_path / "game.nsz"
    nsz.write_bytes(_package(material, ncz="solid", big=True))
    target = tmp_path / "out"

    with console_crypto.key_source(lambda console: keys_path if console == "switch" else None):
        assert images.extract(nsz, target, lambda done, text: None, lambda: False) == str(target)

    assert sorted(os.listdir(target)) == ["exefs", "romfs"]
    assert (target / "romfs" / "dir" / "big.bin").read_bytes() == BIG


def test_extract_cancelled_while_decompressing_returns_none_and_writes_nothing(tmp_path):
    material = _material()
    keys_path = _key_file(tmp_path, material)
    nsz = tmp_path / "game.nsz"
    nsz.write_bytes(_package(material, ncz="block", big=True))
    target = tmp_path / "out"

    with console_crypto.key_source(lambda console: keys_path if console == "switch" else None):
        assert images.extract(nsz, target, lambda done, text: None, lambda: True) is None

    assert not target.exists() or not any(target.iterdir())


def test_room_for_an_nsz_counts_its_decompressed_program_and_an_nsp_does_not(tmp_path):
    material = _material()
    nsz = tmp_path / "game.nsz"
    nsz.write_bytes(_package(material, ncz="solid", big=True))
    plain = tmp_path / "game.nsp"
    plain.write_bytes(_package(material, big=True))
    assert images.unpack_room(plain) == plain.stat().st_size
    assert images.unpack_room(nsz) - nsz.stat().st_size > len(BIG)
