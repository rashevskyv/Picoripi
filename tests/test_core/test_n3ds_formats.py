"""The 3DS image kinds a new project can take: Z3DS (compressed), CFA, encrypted CIA identity, homebrew, and the
whole-image unpack of a game without an unpack hook. Every image is built here; no game data is used.
"""
import importlib.util
import io
import struct
from pathlib import Path

import pytest

from core.containers import z3ds
from core.containers.console_crypto import key_source
from core.containers.image_files import ImageError
from core.project_library import build, images, plugin_facts
from plugins.base_game_rules import BaseGameRules

_fixture_spec = importlib.util.spec_from_file_location("n3ds_fixture", Path(__file__).with_name("test_n3ds_image.py"))
_fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture)
build_cci, build_cia, build_ncch, build_romfs = _fixture.build_cci, _fixture.build_cia, _fixture.build_ncch, _fixture.build_romfs

_crypto_spec = importlib.util.spec_from_file_location("n3ds_crypto", Path(__file__).with_name("test_n3ds_decrypt.py"))
_crypto = importlib.util.module_from_spec(_crypto_spec)
_crypto_spec.loader.exec_module(_crypto)
encrypt_ncch, standard_keys, key_file, read_all, reference_files = (
    _crypto.encrypt_ncch, _crypto.standard_keys, _crypto.key_file, _crypto.read_all, _crypto.reference_files)
ref_scramble, KEYX_3D, COMMON_0, TITLE_ID, TITLE_KEY = (
    _crypto.ref_scramble, _crypto.KEYX_3D, _crypto.COMMON_0, _crypto.TITLE_ID, _crypto.TITLE_KEY)


def _aes():
    from Crypto.Cipher import AES as aes
    return aes


def _zstd_compress(data):
    try:
        from compression import zstd   # Python 3.14+
        return zstd.compress(data)
    except ImportError:
        pass
    try:
        import zstandard
    except ImportError:
        pytest.skip("the Z3DS tests need a zstd package (Python 3.14 or zstandard)")
    return zstandard.ZstdCompressor().compress(data)


def z3ds_file(plain, frame=0x1000, underlying=b"NCSD"):
    """A Z3DS file of ``plain``: header, no metadata, one zstd frame per ``frame`` bytes, then the seek table."""
    pieces = [plain[i:i + frame] for i in range(0, len(plain), frame)]
    packed = [_zstd_compress(piece) for piece in pieces]
    table = b"".join(struct.pack("<II", len(c), len(p)) for c, p in zip(packed, pieces))
    seek = struct.pack("<II", z3ds.SKIPPABLE_MAGIC, len(table) + z3ds.FOOTER_SIZE) + table + struct.pack(
        "<IBI", len(pieces), 0, z3ds.SEEK_FOOTER_MAGIC)
    data = b"".join(packed)
    header = struct.pack("<4s4sBBHIQQ", b"Z3DS", underlying, 1, 0, 0x20, 0, len(data), len(plain))
    return header + data + seek


def encrypted_cia(tmp_path):
    """An encrypted CIA whose content is an encrypted NCCH, with its title key wrapped under the common key."""
    wrapped = _aes().new(ref_scramble(KEYX_3D, COMMON_0), _aes().MODE_CBC, TITLE_ID + bytes(8)).encrypt(TITLE_KEY)
    content = _aes().new(TITLE_KEY, _aes().MODE_CBC, bytes(16)).encrypt(encrypt_ncch(build_ncch()))
    cia = bytearray(build_cia(content, encrypted=True))
    ticket_body = 0x2040 + 0x140
    cia[ticket_body + 0x7F:ticket_body + 0x8F] = wrapped
    cia[ticket_body + 0xB1] = 0
    cia[ticket_body + 0x9C:ticket_body + 0xA4] = TITLE_ID
    path = tmp_path / "game.cia"
    path.write_bytes(bytes(cia))
    return path


class GenericRules(BaseGameRules):
    """A game with no unpack hook: the wizard unpacks its 3DS images whole."""


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def _unpack(tmp_path, sources, key_provider=None):
    project = tmp_path / "project"
    project.mkdir()
    return build.run_unpack(GenericRules(), sources, project, lambda *_: None, lambda: False, key_provider)


def test_z3ds_card_image_is_identified_and_read_decompressed(tmp_path):
    plain = build_cci(build_ncch())
    path = _write(tmp_path, "game.zcci", z3ds_file(plain))
    found = images.identify(path)
    assert (found["kind"], found["game_id"], found["encrypted"]) == ("3ds", "TEST", False)
    with images.open_image(path) as reader:
        assert read_all(reader) == reference_files()


def test_z3ds_stream_reads_across_frames_in_any_order(tmp_path):
    plain = bytes(range(256)) * 40
    stream = z3ds.Z3dsStream(io.BytesIO(z3ds_file(plain, frame=1000)))
    assert stream.size == len(plain)
    for offset, size in ((0, 10), (3500, 2000), (999, 5), (9000, 1000), (1, 9000)):
        stream.seek(offset)
        assert stream.read(size) == plain[offset:offset + size]
    stream.seek(0, 2)
    assert stream.tell() == len(plain)


def test_z3ds_with_a_damaged_seek_table_is_refused_with_the_reason(tmp_path):
    data = bytearray(z3ds_file(build_cci(build_ncch())))
    data[-4:] = b"\0\0\0\0"                    # the footer magic
    path = _write(tmp_path, "damaged.zcci", bytes(data))
    found = images.identify(path)
    assert found["kind"] == images.KIND_UNSUPPORTED and "seek table" in found["reason"]
    [row] = plugin_facts.identify_sources(GenericRules(), [path])
    assert row["status"] == plugin_facts.STATUS_UNSUPPORTED
    with pytest.raises(ImageError):
        z3ds.Z3dsStream(io.BytesIO(bytes(data)))


def test_z3ds_without_a_zstd_package_says_so(tmp_path, monkeypatch):
    def no_backend():
        raise ImageError("needs the zstandard package")
    monkeypatch.setattr(z3ds, "_backend", no_backend)
    path = _write(tmp_path, "game.zcci", z3ds_file(build_cci(build_ncch())))
    assert images.identify(path)["reason"] == "needs the zstandard package"


def test_z3ds_room_is_the_decompressed_size(tmp_path):
    plain = build_cci(build_ncch())
    path = _write(tmp_path, "game.zcci", z3ds_file(plain))
    assert images.unpack_room(path) == len(plain)


def test_3dsx_is_homebrew_and_is_refused_with_the_reason(tmp_path):
    path = _write(tmp_path, "tool.3dsx", b"3DSX" + bytes(64))
    assert images.identify(path)["kind"] == images.KIND_HOMEBREW
    with pytest.raises(ImageError, match="homebrew"):
        with images.open_image(path):
            pass
    [row] = plugin_facts.identify_sources(GenericRules(), [path])
    assert row["status"] == plugin_facts.STATUS_HOMEBREW
    assert (row["role"], row["platform"], row["key"]) == ("", "3ds", "")


def test_cfa_is_a_bare_program_read_without_a_key(tmp_path):
    path = _write(tmp_path, "manual.cfa", build_ncch())
    found = images.identify(path)
    assert (found["kind"], found["encrypted"]) == ("3ds", False)
    with images.open_image(path) as reader:
        assert read_all(reader) == reference_files()


def test_encrypted_cia_identity_is_the_title_id_then_the_product_with_the_key(tmp_path):
    path = encrypted_cia(tmp_path)
    assert images.identify(str(path))["game_id"] == "0004000000012345"   # no key: the product code is inside
    with key_source(lambda console: standard_keys(tmp_path) if console == "3ds" else None):
        assert images.identify(str(path))["game_id"] == "TEST"


def test_encrypted_cia_with_a_wrong_key_keeps_the_title_id(tmp_path):
    path = encrypted_cia(tmp_path)
    wrong = key_file(tmp_path, [f"slot0x2CKeyX={_crypto.KEYX_2C.hex()}", f"slot0x3DKeyX={bytes(16).hex()}",
                                f"common0={COMMON_0.hex()}"], name="wrong_keys.txt")
    with key_source(lambda console: wrong if console == "3ds" else None):
        found = images.identify(str(path))
    assert found is not None and found["game_id"] == "0004000000012345"


def test_game_without_an_unpack_hook_gets_the_whole_image(tmp_path):
    folder = _unpack(tmp_path, {"base": _write(tmp_path, "game.cci", build_cci(build_ncch()))})
    unpacked = Path(folder)
    assert (unpacked / "exheader.bin").read_bytes() == reference_files()["exheader.bin"]
    assert (unpacked / "exefs" / "code.bin").read_bytes() == reference_files()["exefs/code.bin"]
    assert (unpacked / "romfs" / "a.bin").read_bytes() == b"hello"
    assert (unpacked / "romfs" / "d" / "b.txt").read_bytes() == b"xyz"


def test_update_image_overwrites_the_base_files_it_shares(tmp_path):
    base = _write(tmp_path, "base.cci", build_cci(build_ncch()))
    update = _write(tmp_path, "update.cci", build_cci(build_ncch(romfs=build_romfs().replace(b"hello", b"HELLO"))))
    folder = Path(_unpack(tmp_path, {"base": base, "update": update}))
    assert (folder / "romfs" / "a.bin").read_bytes() == b"HELLO"
    assert (folder / "romfs" / "d" / "b.txt").read_bytes() == b"xyz"   # only in the base: kept


def test_encrypted_image_without_a_hook_unpacks_with_its_key(tmp_path):
    keys = standard_keys(tmp_path)
    path = _write(tmp_path, "locked.cci", build_cci(encrypt_ncch(build_ncch())))
    folder = Path(_unpack(tmp_path, {"base": path}, key_provider=lambda console: keys if console == "3ds" else None))
    assert (folder / "romfs" / "a.bin").read_bytes() == b"hello"


def test_wizard_rows_of_3ds_images_without_a_hook(tmp_path):
    plain = _write(tmp_path, "plain.cci", build_cci(build_ncch()))
    locked = _write(tmp_path, "locked.cci", build_cci(encrypt_ncch(build_ncch())))
    rows = {row["path"]: row for row in plugin_facts.identify_sources(GenericRules(), [plain, locked])}
    assert (rows[plain]["status"], rows[plain]["key"]) == (plugin_facts.STATUS_OK, "")
    assert (rows[locked]["status"], rows[locked]["key"]) == (plugin_facts.STATUS_OK, "3ds")
    assert rows[plain]["platform"] == "3ds" and rows[plain]["role"] == "base"
