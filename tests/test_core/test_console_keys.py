"""The per-console key file location, the job's key source, the Switch identify, and the unpack hand-off.

No key bytes appear here: the tests write placeholder files and check which path the store keeps.
"""
import io
import json
import struct

import pytest

from core.containers import console_crypto, image_files, switch_images
from core.containers.image_files import ImageError, ImageReader
from core.project_library import build, console_keys, images, plugin_facts
from utils import constants
from test_core.test_n3ds_image import build_cci, build_ncch


@pytest.fixture
def data_folder(tmp_path, monkeypatch):
    folder = tmp_path / "data"
    monkeypatch.setattr(constants, "SETTINGS_DIR", folder)
    return folder


def _placeholder(tmp_path, name="keys.txt"):
    path = tmp_path / name
    path.write_bytes(b"placeholder")
    return path


def test_the_store_keeps_one_path_per_console_and_forgets_a_missing_file(tmp_path, data_folder):
    key_file = _placeholder(tmp_path)

    console_keys.set_path("3ds", str(key_file))

    assert console_keys.path_for("3ds") == str(key_file)
    assert console_keys.path_for("switch") is None
    assert json.loads(console_keys.store_path().read_text(encoding="utf-8")) == {"3ds": str(key_file)}
    key_file.unlink()
    assert console_keys.path_for("3ds") is None


def test_the_store_is_written_atomically_and_rejects_unknown_consoles(tmp_path, data_folder):
    console_keys.set_path("switch", str(_placeholder(tmp_path)))

    assert sorted(p.name for p in data_folder.iterdir()) == [console_keys.STORE_NAME]
    with pytest.raises(ValueError):
        console_keys.set_path("wiiu", str(tmp_path))


def test_a_damaged_store_reads_as_empty(tmp_path, data_folder):
    data_folder.mkdir(parents=True)
    console_keys.store_path().write_text("{not json", encoding="utf-8")

    assert console_keys.path_for("3ds") is None
    console_keys.set_path("3ds", str(_placeholder(tmp_path)))
    assert console_keys.path_for("3ds") is not None


def test_the_key_source_lives_only_for_the_job(tmp_path):
    seen = []
    with console_crypto.key_source(lambda console: f"/keys/{console}"):
        seen.append(console_crypto.key_path("3ds"))
    seen.append(console_crypto.key_path("3ds"))

    assert seen == ["/keys/3ds", None]


def test_an_encrypted_image_without_a_key_path_says_it_needs_one(tmp_path):
    path = tmp_path / "locked.cci"
    path.write_bytes(build_cci(build_ncch(encrypted=True)))
    with console_crypto.key_source(lambda console: None):
        with pytest.raises(ImageError, match="needs its key file"):
            with images.open_image(path):
                pass


def test_switch_nsp_title_comes_from_its_ticket_rights_id(tmp_path):
    ticket = bytearray(0x2C0)
    ticket[0x2A0:0x2B0] = bytes.fromhex("0100abcd00000800") + bytes(8)
    nsp = _pfs0([("0100ABCD00000800.tik", bytes(ticket)), ("0100ABCD00000800.cert", b"c" * 16)])
    path = tmp_path / "game.nsp"
    path.write_bytes(nsp)

    found = images.identify(path)

    assert found == {"kind": "switch", "game_id": "0100ABCD00000800", "title_id": "0100ABCD00000800",
                     "encrypted": True, "title_kind": "update"}
    assert images.needs_key(path) == "switch"   # the Switch unpack reads a key file (the wizard asks per plugin)
    with pytest.raises(ImageError, match="needs its key file"):
        with images.open_image(path):
            pass


def test_switch_nsp_title_and_kind_come_from_its_plain_content_meta(tmp_path):
    meta = (b'<?xml version="1.0" encoding="utf-8"?>\n<ContentMeta>\n  <Type>Patch</Type>\n'
            b'  <Id>0x0100f43008c44800</Id>\n  <Version>393216</Version>\n  <Content>\n    <Type>Program</Type>\n'
            b'    <Id>461e1e40fb6a016a4e6cb76e7d5b482d</Id>\n  </Content>\n</ContentMeta>\n')
    path = tmp_path / "update.nsp"
    path.write_bytes(_pfs0([("0100f43008c44800.cnmt.xml", meta), ("abc.nca", b"x" * 64)]))

    found = images.identify(path)

    assert (found["game_id"], found["title_kind"]) == ("0100F43008C44800", "update")


def test_switch_cartridge_is_recognised_but_its_title_is_not_read(tmp_path):
    xci = bytearray(0x200)
    xci[0x100:0x104] = b"HEAD"
    path = tmp_path / "game.xci"
    path.write_bytes(bytes(xci))

    assert images.identify(path) == {"kind": "switch", "game_id": "", "title_id": "", "encrypted": True,
                                     "title_kind": ""}


def test_switch_pfs0_name_table_over_the_limit_is_refused(monkeypatch):
    monkeypatch.setattr(image_files, "MAX_TABLE", 8)
    data = b"PFS0" + struct.pack("<III", 0, 16, 0) + bytes(16)

    with pytest.raises(ImageError, match="too large"):
        switch_images.locate(ImageReader(io.BytesIO(data)), data)


def test_title_kind_of_a_switch_title():
    assert switch_images.title_kind("0100ABCD00000000") == "base"
    assert switch_images.title_kind("0100ABCD00000800") == "update"
    assert switch_images.title_kind("0100ABCD00000001") == "dlc"
    assert switch_images.title_kind("") == ""


def test_identification_reports_the_key_a_file_needs(tmp_path, data_folder):
    class Rules:
        def get_source_roles(self):
            return [{"id": "base", "label": "Base game"}]

        def identify_source(self, path):
            return {"role": "base", "platform": "3ds"}

        def unpack_key_consoles(self):
            return ["3ds"]

    path = tmp_path / "locked.cci"
    path.write_bytes(build_cci(build_ncch(encrypted=True)))
    plain = tmp_path / "plain.cci"
    plain.write_bytes(build_cci(build_ncch()))

    before = plugin_facts.identify_sources(Rules(), [str(path), str(plain)])
    console_keys.set_path("3ds", str(_placeholder(tmp_path)))
    after = plugin_facts.identify_sources(Rules(), [str(path)])

    assert [(item["key"], item["key_ready"]) for item in before] == [("3ds", False), ("", False)]
    assert (after[0]["key"], after[0]["key_ready"]) == ("3ds", True)


def test_the_unpack_job_sees_the_key_file_of_its_console_only_while_it_runs(tmp_path, data_folder):
    image = tmp_path / "locked.cci"
    image.write_bytes(build_cci(build_ncch(encrypted=True)))
    key_file = _placeholder(tmp_path)
    console_keys.set_path("3ds", str(key_file))
    seen = []

    class Unpacker:
        def unpack_sources(self, sources, target, progress, is_cancelled):
            seen.append((console_crypto.key_path("3ds"), console_crypto.key_path("switch")))
            return None

        def get_source_subfolder(self):
            return None

    folder = tmp_path / "project"
    folder.mkdir()
    result = build.run_unpack(Unpacker(), {"base": str(image)}, folder, lambda p, t: None, lambda: False,
                              key_provider=console_keys.path_for)

    assert result is None
    assert seen == [(str(key_file), None)]
    assert console_crypto.key_path("3ds") is None


def _pfs0(files):
    names = b"".join(name.encode() + b"\0" for name, _body in files)
    entries = b""
    data = b""
    name_at = 0
    for name, body in files:
        entries += struct.pack("<QQII", len(data), len(body), name_at, 0)
        name_at += len(name) + 1
        data += body
    return b"PFS0" + struct.pack("<III", len(files), len(names), 0) + entries + names + data
