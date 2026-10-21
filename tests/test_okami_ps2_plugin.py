"""Okami PlayStation 2 plugin: ISO 9660 reading, AFS entry selection, unpack and the text layer (synthetic discs).

The last test reads the owner's PS2 disc image when ``PICORIPI_ROMHACKING`` names the workspace; it skips otherwise.
"""
import io
import os
import struct

import pytest

import romhacking_root
from core.containers import afs as core_afs
from plugins.okami_ps2 import afs, build, iso, unpack
from plugins.okami_ps2.rules import GameRules
from plugins.okami_hd import textfile


def _record(name, lba, size, is_dir):
    raw = name.encode("ascii")
    length = 33 + len(raw) + (len(raw) % 2 == 0)
    rec = bytearray(length)
    rec[0] = length
    struct.pack_into("<I", rec, 2, lba)
    struct.pack_into(">I", rec, 6, lba)
    struct.pack_into("<I", rec, 10, size)
    struct.pack_into(">I", rec, 14, size)
    rec[25] = 2 if is_dir else 0
    rec[32] = len(raw)
    rec[33:33 + len(raw)] = raw
    return bytes(rec)


def iso_image(files):
    """An ISO 9660 image: sector 16 = primary volume, sector 17 = root folder, files from sector 18."""
    lba = 18
    placed = []
    for name, data in files.items():
        placed.append((name, lba, len(data)))
        lba += (len(data) + 2047) // 2048
    root = bytearray(2048)
    at = 0
    for name, start, size in placed:
        record = _record(name + ";1", start, size, False)
        root[at:at + len(record)] = record
        at += len(record)
    pvd = bytearray(2048)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[156:156 + 34] = _record("\x00", 17, 2048, True).ljust(34, b"\x00")
    out = bytearray(b"\x00" * (16 * 2048))
    out += pvd + root
    for name, start, size in placed:
        data = files[name]
        out += data + b"\x00" * ((-len(data)) % 2048)
    sectors = len(out) // 2048
    struct.pack_into("<I", out, 16 * 2048 + 80, sectors)
    struct.pack_into(">I", out, 16 * 2048 + 84, sectors)
    return bytes(out), placed


def afs_archive(entries):
    """An AFS archive with the given entry payloads, each at a 0x800 boundary."""
    count = len(entries)
    header_end = 0x800
    table = bytearray(b"AFS\x00" + struct.pack("<I", count))
    offset = header_end
    body = bytearray()
    for payload in entries:
        table += struct.pack("<II", offset, len(payload))
        padded = payload + b"\x00" * ((-len(payload)) % 0x800)
        body += padded
        offset += len(padded)
    out = bytearray(b"\x00" * header_end)
    out[:len(table)] = table
    return bytes(out) + bytes(body)


def container(strings):
    """One MSD container (list layout) with one section, as in the HD files."""
    section = bytes.fromhex("01000000 0c000000 00000000")
    for string in strings:
        section += b"".join(struct.pack("<H", unit) for unit in string) + b"\x00\x00"
    # two sections: an ACT section first (32 bytes), then the MSD section
    count = 2
    header = 4 + 8 * count
    act = b"\x11" * 32
    out = bytearray(struct.pack("<I", count))
    out += struct.pack("<II", header, header + len(act))
    out += b"ACT\x00MSD\x00"
    out += act + section
    return bytes(out)


def disc_bytes(afs_files):
    system = b"BOOT2 = cdrom0:\\SLUS_211.15;1\r\nVER = 1.00\r\nVMODE = NTSC\r\n"
    files = {"SYSTEM.CNF": system, "_DATA0.AFS": afs_files[0], "_DATA1.AFS": afs_files[1]}
    return iso_image(files)[0]


def test_identify_finds_the_disc_id_and_refuses_another_disc(tmp_path):
    good = tmp_path / "good.iso"
    good.write_bytes(disc_bytes((afs_archive([b"x"]), afs_archive([b"y"]))))
    assert unpack.identify(str(good)) == {"role": "base", "platform": "ps2", "libraries": []}
    other = tmp_path / "other.iso"
    system = b"BOOT2 = cdrom0:\\SLUS_000.00;1\r\n"
    other.write_bytes(iso_image({"SYSTEM.CNF": system})[0])
    assert unpack.identify(str(other)) is None


def test_iso_find_is_case_blind_and_reads_a_range(tmp_path):
    raw = iso_image({"SYSTEM.CNF": b"hello disc", "_DATA0.AFS": b"0123456789"})[0]
    with io.BytesIO(raw) as image:
        entry = iso.find(image, "system.cnf")
        assert entry is not None and iso.read(image, entry, 6, 100) == b"disc"
        assert iso.find(image, "MISSING.BIN") is None


def test_afs_selects_only_message_entries():
    data = afs_archive([b"not a container at all", container([[0x44, 0x38, 0x35]])])
    raw = disc_bytes((data, afs_archive([b"junk"])))
    with io.BytesIO(raw) as image:
        system = iso.find(image, "_DATA0.AFS")
        read = afs.ps2_reader(image, system)
        found = afs.message_entries(read, system.size)
        assert [entry.index for entry in found] == [1]
        assert afs.read_entry(read, found[0]) == container([[0x44, 0x38, 0x35]])


def test_unpack_writes_message_entries_per_archive(tmp_path):
    disc = tmp_path / "disc.iso"
    disc.write_bytes(disc_bytes((afs_archive([container([[0x44, 0x38, 0x35]])]), afs_archive([b"junk"]))))
    out = tmp_path / "source"
    result = unpack.unpack({"base": str(disc)}, str(out), lambda done, text: None, lambda: False)
    assert result == str(out)
    written = sorted(os.path.relpath(os.path.join(dp, name), out) for dp, _d, names in os.walk(out) for name in names)
    assert written == [os.path.join("afs", "DATA0", "0000.bin"), "source_image.ref"]


def test_text_layer_round_trip_on_a_ps2_container():
    data = container([[0x44, 0x38, 0x35], [0x31]])
    rules = GameRules()
    lines, names = rules.load_data_from_json_obj(data)
    assert lines == [["the a"]] and names == {"0": "messages"}      # one row per record; strings joined by a space
    assert rules.save_data_to_json_obj(lines, names) == data
    edited, warnings = textfile.write_text(data, ["the b"])
    assert textfile.read_text(edited) == ["the b"] and warnings == []


def test_real_ps2_disc_identifies_and_lists_messages():
    reason = romhacking_root.missing("Okami", "Okami", "PS2", "ISO", "Okami (USA).iso")
    if reason:
        pytest.skip(reason)
    path = str(romhacking_root.path("Okami", "Okami", "PS2", "ISO", "Okami (USA).iso"))
    assert unpack.identify(path) is not None
    with open(path, "rb") as image:
        archive = iso.find(image, "_DATA0.AFS")
        assert len(afs.message_entries(afs.ps2_reader(image, archive), archive.size)) > 100


def _quiet(*_args):
    return None


def test_build_without_changes_is_a_byte_copy(tmp_path):
    src = tmp_path / "disc.iso"
    src.write_bytes(disc_bytes((afs_archive([container([[0x44, 0x38, 0x35]])]), afs_archive([b"junk"]))))
    out = tmp_path / "out.iso"
    build.build_image(str(src), {}, str(out), _quiet, lambda: False)
    assert out.read_bytes() == src.read_bytes()


def test_a_grown_entry_moves_its_archive_to_the_end_and_keeps_the_other_entries(tmp_path):
    src = tmp_path / "disc.iso"
    src.write_bytes(disc_bytes((afs_archive([container([[0x44, 0x38, 0x35]]), b"second entry"]), afs_archive([b"junk"]))))
    original_sectors = src.stat().st_size // 2048
    big = container([[0x41] * 3000])
    out = tmp_path / "out.iso"
    build.build_image(str(src), {"_DATA0.AFS": {0: big}}, str(out), _quiet, lambda: False)
    with open(out, "rb") as image:
        archive = iso.find(image, "_DATA0.AFS")
        assert archive.lba == original_sectors
        assert iso.volume_sectors(image) == out.stat().st_size // 2048
        read = afs.ps2_reader(image, archive)
        entries = core_afs.parse_from(read, archive.size)
        assert afs.read_entry(read, entries[0]) == big
        assert afs.read_entry(read, entries[1]) == b"second entry"
        data1 = iso.find(image, "_DATA1.AFS")
        assert iso.read(image, data1, 0, data1.size) == afs_archive([b"junk"])


def test_a_smaller_entry_is_written_in_place_with_its_new_size(tmp_path):
    src = tmp_path / "disc.iso"
    src.write_bytes(disc_bytes((afs_archive([container([[0x41] * 3000]), b"tail"]), afs_archive([b"junk"]))))
    out = tmp_path / "out.iso"
    small = container([[0x44, 0x38, 0x35]])
    build.build_image(str(src), {"_DATA0.AFS": {0: small}}, str(out), _quiet, lambda: False)
    assert out.stat().st_size == src.stat().st_size
    with open(src, "rb") as before, open(out, "rb") as image:
        original = iso.find(before, "_DATA0.AFS")
        archive = iso.find(image, "_DATA0.AFS")
        assert archive.lba == original.lba and archive.size < original.size
        read = afs.ps2_reader(image, archive)
        entries = core_afs.parse_from(read, archive.size)
        assert afs.read_entry(read, entries[0]) == small
        assert afs.read_entry(read, entries[1]) == b"tail"


def test_the_streamed_writer_matches_the_bytes_writer_and_its_size():
    data = afs_archive([b"a" * 300, b"b" * 2100, b"c" * 40])
    replacements = {1: b"x" * 5000}
    reader = lambda offset, count: data[offset:offset + count]   # noqa: E731
    out = io.BytesIO()
    size = core_afs.write_to(reader, len(data), out, replacements)
    assert out.getvalue() == core_afs.write(data, replacements)
    assert size == len(out.getvalue()) == core_afs.layout(reader, len(data), replacements).total


def test_changed_pictures_and_messages_are_read_as_disc_entries(tmp_path):
    from plugins.okami_ps2 import build as ps2_build

    source = tmp_path / "source"
    translation = tmp_path / "translation"
    (translation / "pictures" / "DATA0").mkdir(parents=True)
    (translation / "afs" / "DATA0").mkdir(parents=True)
    (translation / "pictures" / "DATA0" / "0022.tm2").write_bytes(b"TIM2-edited")
    (translation / "afs" / "DATA0" / "0005.bin").write_bytes(b"message")
    (translation / "pictures" / "DATA0" / "notes.tm2").write_bytes(b"not an entry")
    changes = ps2_build.read_changes(str(source), str(translation))
    assert changes == {"_DATA0.AFS": {22: b"TIM2-edited", 5: b"message"}}
