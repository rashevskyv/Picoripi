"""Synthetic encrypted 3DS programs: the reader must decrypt them with keys, and refuse what it cannot read.

The encryption side here is written from the public 3DS formats, independently of ``core.containers.n3ds``: the key
scrambler, the CTR keystream (AES-ECB of each counter block) and the CIA title key (AES-CBC). The keys are test values.
"""
import importlib.util
import io
import struct
import traceback
from pathlib import Path

import pytest

pytest.importorskip("Crypto.Cipher.AES", reason="the 3DS decryption tests need pycryptodome")
from Crypto.Cipher import AES  # noqa: E402

from core.containers import n3ds  # noqa: E402
from core.containers.image_files import ImageError

# The plaintext program builders live beside test_n3ds_image.py; load them from that file.
_spec = importlib.util.spec_from_file_location("n3ds_fixture", Path(__file__).with_name("test_n3ds_image.py"))
_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture)
build_cci, build_cia, build_ncch = _fixture.build_cci, _fixture.build_cia, _fixture.build_ncch

MASK = (1 << 128) - 1
SCRAMBLER = 0x1FF9E9AAC5FE0408024591DC5D52768A
KEYX_2C = bytes(range(1, 17))
KEYX_3D = bytes(range(0x21, 0x31))
COMMON_0 = bytes(range(0x41, 0x51))
KEY_Y = bytes(range(0x61, 0x71))          # the NCCH signature's first 16 bytes: the KeyY of the program
TITLE_ID = bytes.fromhex("0004000000012345")
TITLE_KEY = bytes(range(0x81, 0x91))


def ref_scramble(keyx, keyy):
    def rol(value, count):
        return ((value << count) | (value >> (128 - count))) & MASK
    mixed = (rol(int.from_bytes(keyx, "big"), 2) ^ int.from_bytes(keyy, "big")) + SCRAMBLER & MASK
    return rol(mixed, 87).to_bytes(16, "big")


def ctr(key, counter, data):
    ecb = AES.new(key, AES.MODE_ECB)
    out = bytearray()
    for index in range(0, len(data), 16):
        stream = ecb.encrypt(((counter + index // 16) & MASK).to_bytes(16, "big"))
        out += bytes(a ^ b for a, b in zip(data[index:index + 16], stream))
    return bytes(out)


def encrypt_ncch(plain, version=0, key=None, flags7=0, title_id=None):
    """The plaintext NCCH from ``build_ncch`` with KeyY, flags and sections encrypted as a real program has them.

    ``key`` is the region key (default: slot 0x2C from KeyX and KeyY); ``flags7`` sets the flags byte 7 (0x01 is a
    fixed-key program, which uses ``key`` directly); ``title_id`` (big-endian hex) sets the program ID.
    """
    body = bytearray(plain)
    body[:16] = KEY_Y
    body[0x112:0x114] = struct.pack("<H", version)
    body[0x188 + 7] = flags7
    if title_id is not None:
        body[0x108:0x110] = body[0x118:0x120] = bytes.fromhex(title_id)[::-1]
    key = key or ref_scramble(KEYX_2C, KEY_Y)
    partition = bytes(body[0x108:0x110])

    def counter(region_start, kind):
        if version == 1:
            return int.from_bytes(partition + bytes(4) + region_start.to_bytes(4, "big"), "big")
        return int.from_bytes(partition[::-1] + bytes([kind]) + bytes(7), "big")

    regions = [(0x200, 0x800, 1)]
    exefs_at, exefs_size = struct.unpack_from("<II", body, 0x1A0)
    romfs_at, romfs_size = struct.unpack_from("<II", body, 0x1B0)
    regions.append((exefs_at * 0x200, exefs_size * 0x200, 2))
    regions.append((romfs_at * 0x200, romfs_size * 0x200, 3))
    for start, size, kind in regions:
        if size:
            body[start:start + size] = ctr(key, counter(start, kind), bytes(body[start:start + size]))
    return bytes(body)


def key_file(tmp_path, lines, name="aes_keys.txt"):
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return str(path)


def standard_keys(tmp_path):
    return key_file(tmp_path, [f"slot0x2CKeyX={KEYX_2C.hex()}", f"slot0x3DKeyX={KEYX_3D.hex()}",
                               f"common0={COMMON_0.hex()}"])


def read_all(reader):
    return {entry.path: reader.read(entry) for entry in reader.entries()}


def reference_files():
    """The files of the same program read as a decrypted (NoCrypto) image."""
    return read_all(n3ds.N3dsImage(io.BytesIO(build_cci(build_ncch()))))


def test_encrypted_card_image_decrypts_to_the_plain_files(tmp_path):
    cci = build_cci(encrypt_ncch(build_ncch()))
    reader = n3ds.N3dsImage(io.BytesIO(cci), standard_keys(tmp_path))

    assert read_all(reader) == reference_files()


def test_version_1_counters_decrypt(tmp_path):
    cci = build_cci(encrypt_ncch(build_ncch(), version=1))
    reader = n3ds.N3dsImage(io.BytesIO(cci), standard_keys(tmp_path))

    assert read_all(reader) == reference_files()


def test_boot9_in_the_key_folder_supplies_keyx_0x2c(tmp_path):
    boot9 = bytearray(0x10000)
    boot9[0xD9D0:0xD9D0 + 16] = KEYX_2C                       # the boot9 key area, KeyX 0x2C first
    (tmp_path / "QJF_boot9_00.bin").write_bytes(bytes(boot9))
    path = key_file(tmp_path, ["# no keys in this file"])
    reader = n3ds.N3dsImage(io.BytesIO(build_cci(encrypt_ncch(build_ncch()))), path)

    assert read_all(reader) == reference_files()


def test_encrypted_cia_decrypts_its_title_key_then_its_content(tmp_path):
    common_key = ref_scramble(KEYX_3D, COMMON_0)
    wrapped = AES.new(common_key, AES.MODE_CBC, TITLE_ID + bytes(8)).encrypt(TITLE_KEY)
    content = AES.new(TITLE_KEY, AES.MODE_CBC, bytes(16)).encrypt(encrypt_ncch(build_ncch()))
    cia = bytearray(build_cia(content, encrypted=True))
    ticket_body = 0x2040 + 0x140                              # the header, then the ticket after its signature
    cia[ticket_body + 0x7F:ticket_body + 0x8F] = wrapped
    cia[ticket_body + 0xB1] = 0                               # common key index 0
    cia[ticket_body + 0x9C:ticket_body + 0xA4] = TITLE_ID
    reader = n3ds.N3dsImage(io.BytesIO(bytes(cia)), standard_keys(tmp_path))

    assert read_all(reader) == reference_files()


def test_wrong_key_is_refused_without_echoing_key_bytes(tmp_path):
    wrong = bytes(range(0x90, 0xA0))
    path = key_file(tmp_path, [f"slot0x2CKeyX={wrong.hex()}"])

    with pytest.raises(ImageError, match="does not decrypt") as info:
        n3ds.N3dsImage(io.BytesIO(build_cci(encrypt_ncch(build_ncch()))), path)
    assert wrong.hex() not in str(info.value)
    assert KEYX_2C.hex() not in str(info.value)


def test_fixed_key_title_with_zero_key_needs_no_key_file():
    cci = build_cci(encrypt_ncch(build_ncch(), key=n3ds.ZERO_KEY, flags7=0x01))
    reader = n3ds.N3dsImage(io.BytesIO(cci), None)

    assert read_all(reader) == reference_files()
    assert reader.program["encrypted"] is False


def test_fixed_key_system_title_uses_the_fixed_system_key():
    cci = build_cci(encrypt_ncch(build_ncch(), key=n3ds.FIXED_SYSTEM_KEY, flags7=0x01, title_id="0004001B00012345"))

    assert read_all(n3ds.N3dsImage(io.BytesIO(cci), None)) == reference_files()


@pytest.mark.parametrize("title_id, key", [("0004000000F3FF00", n3ds.ZERO_KEY),
                                           ("0004000000012345", n3ds.ZERO_KEY),
                                           ("0004013800012345", n3ds.FIXED_SYSTEM_KEY),
                                           ("0004001B00012345", n3ds.FIXED_SYSTEM_KEY)])
def test_fixed_key_depends_on_the_system_bit_of_the_title_id(title_id, key):
    assert n3ds.fixed_key(title_id) == key


def test_encrypted_program_without_a_key_file_is_refused():
    with pytest.raises(ImageError, match="needs its key file"):
        n3ds.N3dsImage(io.BytesIO(build_cci(encrypt_ncch(build_ncch()))), None)


def test_key_file_line_parsing_ignores_noise(tmp_path):
    path = key_file(tmp_path, ["slot0x2CKeyX=" + KEYX_2C.hex(), "slot0xZZKeyX=00", "common=xyz", "junk line",
                               "slot0x3DKeyX=" + "12" * 15])
    keys = n3ds.Keys3ds.load(path)

    assert keys.normal(0x2C, KEY_Y) == ref_scramble(KEYX_2C, KEY_Y)
    with pytest.raises(ImageError, match="no KeyX for slot 0x3D"):
        keys.normal(0x3D, KEY_Y)


def test_unreadable_key_file_error_does_not_chain_the_path(tmp_path):
    """The worker logs a failed unpack with its traceback; the key folder must not appear there (D30)."""
    folder = tmp_path / ("zz" + "_marker_dir")   # not spelled out below: the test's own source line is in the traceback
    with pytest.raises(ImageError, match="cannot be read") as info:
        n3ds.Keys3ds.load(str(folder / "aes_keys.txt"))
    assert "zz_marker_dir" not in "".join(traceback.format_exception(info.value))


def test_unreadable_boot9_error_does_not_chain_the_path(tmp_path):
    (tmp_path / "zz_marker_boot9.bin").mkdir()   # a folder where boot9 is expected: opening it fails
    path = key_file(tmp_path, [f"slot0x2CKeyX={KEYX_2C.hex()}"])
    with pytest.raises(ImageError, match="boot9 file cannot be read") as info:
        n3ds.Keys3ds.load(path)
    assert "zz_marker" not in "".join(traceback.format_exception(info.value))


def test_open_image_decrypts_through_the_key_source(tmp_path):
    from core.containers.console_crypto import key_source
    from core.project_library import images

    keys = standard_keys(tmp_path)
    cci = tmp_path / "locked.cci"
    cci.write_bytes(build_cci(encrypt_ncch(build_ncch())))
    with key_source(lambda console: keys if console == "3ds" else None):
        with images.open_image(cci) as reader:
            assert read_all(reader) == reference_files()
