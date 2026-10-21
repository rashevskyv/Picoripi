"""Okami Wii plugin: the disc header, the big-endian message containers, the streamed AFS reader and the changed-files build.

Synthetic data only: no disc, no key. The real disc is read by hand (the key is in the console key store).
"""
import io
import os
import struct

from core.containers import afs as core_afs
from plugins.okami_hd import charset, msd, textfile
from plugins.okami_ps2 import afs
from plugins.okami_wii import build, unpack
from plugins.okami_wii.rules import GameRules

WII_MAGIC = 0x5D1C9EA3


def _wii_head(game_id: bytes) -> bytes:
    head = bytearray(0x20)
    head[:6] = game_id
    struct.pack_into(">I", head, 0x18, WII_MAGIC)
    return bytes(head)


def be_container(units):
    """One big-endian message container: one MSD table section with one 1-unit record and one string."""
    record = bytes.fromhex("8303") + b"".join(struct.pack(">H", unit) for unit in units) + b"\x00\x00"
    section = struct.pack(">HH", 1, 0) + struct.pack(">II", 12, 0) + record
    return struct.pack(">I", 1) + struct.pack(">I", 12) + b"MSD\x00" + section


def le_afs(payloads):
    """An AFS archive (little-endian table) with the payloads, each at a 0x800 boundary."""
    count = len(payloads)
    table = bytearray(b"AFS\x00" + struct.pack("<I", count))
    body = bytearray()
    offset = 0x800
    for payload in payloads:
        table += struct.pack("<II", offset, len(payload))
        padded = payload + b"\x00" * ((-len(payload)) % 0x800)
        body += padded
        offset += len(padded)
    out = bytearray(0x800)
    out[:len(table)] = table
    return bytes(out) + bytes(body)


def test_identify_accepts_the_wii_header_of_the_game_only(tmp_path):
    good = tmp_path / "good.iso"
    good.write_bytes(_wii_head(b"ROWP08") + b"\x00" * 0x100)
    assert unpack.identify(str(good)) == {"role": "base", "platform": "wii", "libraries": []}
    other = tmp_path / "other.iso"
    other.write_bytes(_wii_head(b"RSBP01") + b"\x00" * 0x100)
    assert unpack.identify(str(other)) is None
    plain = tmp_path / "plain.iso"
    plain.write_bytes(b"\x00" * 0x100)
    assert unpack.identify(str(plain)) is None


def test_big_endian_container_round_trips_and_takes_a_longer_text():
    data = be_container([charset.CHAR_TO_CODE["H"], charset.CHAR_TO_CODE["i"]])
    assert textfile.read_text(data, ">") == ["Hi"]
    assert textfile.read_text(data) == []                      # the little-endian reader sees no section
    same, warnings = textfile.write_text(data, ["Hi"], ">")
    assert same == data and warnings == []
    longer, warnings = textfile.write_text(data, ["Hiya"], ">")
    assert textfile.read_text(longer, ">") == ["Hiya"]
    assert warnings == []
    assert len(msd.parse_container(longer, ">").section_bytes(0)) % 16 == 0     # padded to the disc's 16 bytes


def test_message_entries_follow_the_byte_order_of_the_containers():
    archive = le_afs([be_container([charset.CHAR_TO_CODE["H"]]), b"not a container"])
    read = afs.stream_reader(io.BytesIO(archive), 0, len(archive))
    assert [entry.index for entry in afs.message_entries(read, len(archive), ">")] == [0]
    assert afs.message_entries(read, len(archive)) == []
    assert afs.read_entry(read, core_afs.parse(archive)[0]) == be_container([charset.CHAR_TO_CODE["H"]])


def test_stream_reader_clips_to_its_part_of_the_stream():
    stream = io.BytesIO(b"0123456789")
    read = afs.stream_reader(stream, 2, 5)
    assert read(0, 3) == b"234" and read(3, 10) == b"56" and read(9, 4) == b""


def test_build_writes_the_changed_entries_as_files(tmp_path):
    source = tmp_path / "source"
    translation = tmp_path / "translation"
    (source / "afs" / "DATA0").mkdir(parents=True)
    (translation / "afs" / "DATA0").mkdir(parents=True)
    (source / "afs" / "DATA0" / "0005.bin").write_bytes(b"old")
    (translation / "afs" / "DATA0" / "0005.bin").write_bytes(b"new text")
    (translation / "afs" / "DATA0" / "0006.bin").write_bytes(b"added")
    (translation / "afs" / "DATA0" / "0007.bin").write_bytes(b"not changed")
    (source / "afs" / "DATA0" / "0007.bin").write_bytes(b"not changed")
    out = tmp_path / "out"
    out.mkdir()
    result = build.build_changed(str(source), str(translation), str(out), lambda done, text: None, lambda: False)
    assert result == str(out)
    written = sorted(os.path.relpath(os.path.join(dp, name), out) for dp, _d, names in os.walk(out) for name in names)
    assert written == [os.path.join("afs", "DATA0", "0005.bin"), os.path.join("afs", "DATA0", "0006.bin")]
    assert (out / "afs" / "DATA0" / "0005.bin").read_bytes() == b"new text"


def test_rules_use_the_big_endian_codec_and_declare_the_wii_platform():
    rules = GameRules()
    assert rules.get_display_name() == "Okami (Wii)"
    assert rules.ENDIAN == ">"
    assert [p["id"] for p in rules.get_platforms()] == ["wii"]
    lines, names = rules.load_data_from_json_obj(be_container([charset.CHAR_TO_CODE["H"]]))
    assert lines == [["H"]] and names == {"0": "messages"}


def test_changed_entries_map_to_the_disc_archives(tmp_path):
    translation = tmp_path / "translation"
    (translation / "afs" / "DATA0").mkdir(parents=True)
    (translation / "afs" / "DATA1").mkdir(parents=True)
    (translation / "afs" / "DATA0" / "0005.bin").write_bytes(b"text")
    (translation / "afs" / "DATA1" / "0002.bin").write_bytes(b"more")
    changes = build.read_changes(str(tmp_path / "source"), str(translation))
    assert changes == {"files/_data0.afs": {5: b"text"}, "files/_data1.afs": {2: b"more"}}


def test_the_disc_target_is_declared_next_to_the_file_target():
    ids = [target["id"] for target in GameRules().get_build_targets()]
    assert ids == [build.ISO_TARGET, build.TARGET_ID]


def test_disc_build_needs_the_unpacked_folder_and_the_key_file(tmp_path, monkeypatch):
    import pytest

    with pytest.raises(ValueError, match="unpack the disc again"):
        build.build_iso(str(tmp_path), str(tmp_path), str(tmp_path / "out"), lambda d, t: None, lambda: False)
    (tmp_path / build.REF_NAME).write_text('{"image": "%s"}' % (tmp_path / "missing.iso").as_posix(), encoding="utf-8")
    with pytest.raises(ValueError, match="not on disk"):
        build.build_iso(str(tmp_path), str(tmp_path), str(tmp_path / "out"), lambda d, t: None, lambda: False)
    image = tmp_path / "disc.iso"
    image.write_bytes(b"")
    (tmp_path / build.REF_NAME).write_text('{"image": "%s"}' % image.as_posix(), encoding="utf-8")
    monkeypatch.setattr(build.console_keys, "path_for", lambda console: None)
    with pytest.raises(ValueError, match="Wii key file"):
        build.build_iso(str(tmp_path), str(tmp_path), str(tmp_path / "out"), lambda d, t: None, lambda: False)
