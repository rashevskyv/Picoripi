"""Switch key file parsing, key derivation and Nintendo XTS. All keys are random values written by the test."""
import os

import pytest
from Crypto.Cipher import AES

from core.containers.image_files import ImageError
from core.containers.switch_crypto import load_keys, xts_decrypt


def _ecb(key, data, decrypt=False):
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.decrypt(data) if decrypt else cipher.encrypt(data)


def _double(tweak):
    value = int.from_bytes(tweak, "little") << 1
    if value >> 128:
        value = (value & ((1 << 128) - 1)) ^ 0x87
    return value.to_bytes(16, "little")


def _xts_encrypt(key, data, sector=0):
    out = bytearray()
    for index in range(len(data) // 0x200):
        tweak = _ecb(key[16:], (sector + index).to_bytes(16, "big"))
        for pos in range(index * 0x200, (index + 1) * 0x200, 16):
            block = bytes(a ^ b for a, b in zip(data[pos:pos + 16], tweak))
            out += bytes(a ^ b for a, b in zip(_ecb(key[:16], block), tweak))
            tweak = _double(tweak)
    return bytes(out)


def _write(tmp_path, lines):
    path = tmp_path / "prod.keys"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def test_key_area_key_is_derived_from_the_sources_when_no_derived_key_is_given(tmp_path):
    master, kek_src, key_src, area_src, titlekek_src = (os.urandom(16) for _ in range(5))
    header = os.urandom(32)
    path = _write(tmp_path, [
        f"header_key = {header.hex()}", "unknown_name = 00", "# a comment without a value",
        f"master_key_00 = {master.hex()}", f"aes_kek_generation_source = {kek_src.hex()}",
        f"aes_key_generation_source = {key_src.hex()}", f"key_area_key_application_source = {area_src.hex()}",
        f"titlekek_source = {titlekek_src.hex()}",
    ])

    keys = load_keys(path)

    kek = _ecb(master, kek_src, decrypt=True)
    source_kek = _ecb(kek, area_src, decrypt=True)
    assert keys.key_area_key(0, 0) == _ecb(source_kek, key_src, decrypt=True)
    assert keys.titlekek(0) == _ecb(master, titlekek_src, decrypt=True)
    assert keys.header_key() == header


def test_a_derived_key_in_the_file_is_used_as_it_is(tmp_path):
    area, titlekek = os.urandom(16), os.urandom(16)
    path = _write(tmp_path, [f"header_key = {os.urandom(32).hex()}",
                             f"key_area_key_application_00 = {area.hex()}", f"titlekek_00 = {titlekek.hex()}"])

    keys = load_keys(path)

    assert (keys.key_area_key(0, 0), keys.titlekek(0)) == (area, titlekek)


def test_key_file_without_a_header_key_is_an_image_error(tmp_path):
    path = _write(tmp_path, [f"master_key_00 = {os.urandom(16).hex()}"])

    with pytest.raises(ImageError, match="header_key"):
        load_keys(path)


def test_malformed_key_value_is_an_image_error_that_shows_no_key_text(tmp_path):
    secret = os.urandom(32).hex()
    path = _write(tmp_path, [f"header_key = {secret[:-1]}"])

    with pytest.raises(ImageError, match="malformed") as caught:
        load_keys(path)

    assert secret not in str(caught.value) and secret[:-1] not in str(caught.value)


def test_missing_source_key_is_an_image_error_when_a_key_is_needed(tmp_path):
    path = _write(tmp_path, [f"header_key = {os.urandom(32).hex()}"])

    with pytest.raises(ImageError, match="master_key_00"):
        load_keys(path).titlekek(0)


def test_xts_decrypt_inverts_the_reference_encryption_and_depends_on_the_sector(tmp_path):
    key = os.urandom(32)
    plain = os.urandom(0x400)

    cipher = _xts_encrypt(key, plain, sector=3)

    assert xts_decrypt(key, cipher, sector=3) == plain
    assert xts_decrypt(key, cipher, sector=0) != plain
