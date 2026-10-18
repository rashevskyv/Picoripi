"""Skies of Arcadia (Dreamcast, USA) plugin: the disc identity by region, the field-script unpack, the little-endian
script codec and the disc-set build. Synthetic GD-ROM sets built here (a small writer below); the real USA disc is
checked read-only when the owner's files are on disk."""
import os
import struct

import pytest

import romhacking_root

from core.containers.gdrom import HD_BASE, SECTOR
from core.project_library import images
from plugins.skies_of_arcadia import scripts
from plugins.skies_of_arcadia_dc.rules import GameRules

REAL_USA_CUE = romhacking_root.under(r"Skies of Arcadia\Skies of Arcadia\Dreamcast\ISO\Skies of Arcadia (USA) (Disc 1).cue")
SCRIPT_BODY = b"\\h(\x81sAlfonso\x81t)Hello there\\c" + b"\x00" * 2 + b"\\h(Bye\\e" + b"\x00" * 2


def _raw(user=b""):
    """A Mode 1 raw sector: sync, header, 2048 user bytes, 288 bytes of error correction (zeros here)."""
    return b"\x00" + b"\xff" * 10 + b"\x00" + b"\x00\x00\x00\x01" + user.ljust(SECTOR, b"\x00") + b"\x00" * 288


def _record(name: bytes, extent: int, size: int, is_dir: bool) -> bytes:
    body = bytearray(33 + len(name))
    body[2:6] = struct.pack("<I", extent)
    body[6:10] = struct.pack(">I", extent)
    body[10:14] = struct.pack("<I", size)
    body[14:18] = struct.pack(">I", size)
    body[25] = 0x02 if is_dir else 0x00
    body[32] = len(name)
    body[33:] = name
    if len(body) % 2:
        body += b"\x00"
    body[0] = len(body)
    return bytes(body)


def _pvd(root_extent: int, root_size: int) -> bytes:
    pvd = bytearray(SECTOR)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[156:190] = _record(b"\x00", root_extent, root_size, True)
    return bytes(pvd)


def _directory(*records: bytes) -> bytes:
    return b"".join(records).ljust(SECTOR, b"\x00")


def _ip_bin(region: bytes, game_id: bytes) -> bytes:
    """The SEGA IP.BIN fields the reader uses: magic, disc text, area symbol at 0x30 and product number at 0x40."""
    return (b"SEGA SEGAKATANA SEGA ENTERPRISES" + b"4F67 GD-ROM1/2   " + region.ljust(8)
            + b"0799A10 " + game_id.ljust(10))


def _write_cue(folder, region: bytes, game_id: bytes, script: bytes) -> str:
    """A set with a 20-sector LD track (sector 0 is the IP.BIN) and an HD track holding FIELD/ME201A.SCT."""
    b = HD_BASE
    count = (len(script) + SECTOR - 1) // SECTOR
    ld = [_raw(_ip_bin(region, game_id))] + [_raw() for _ in range(19)]
    root = _directory(_record(b"\x00", b + 18, SECTOR, True), _record(b"\x01", b + 18, SECTOR, True),
                      _record(b"FIELD", b + 19, SECTOR, True))
    field = _directory(_record(b"\x00", b + 19, SECTOR, True), _record(b"\x01", b + 18, SECTOR, True),
                       _record(b"ME201A.SCT;1", b + 20, len(script), False))
    hd = [_raw() for _ in range(20)]
    hd[16] = _raw(_pvd(b + 18, SECTOR))
    hd[18] = _raw(root)
    hd[19] = _raw(field)
    hd += [_raw(script[i * SECTOR:(i + 1) * SECTOR]) for i in range(count)]
    (folder / "ld.bin").write_bytes(b"".join(ld))
    (folder / "hd.bin").write_bytes(b"".join(hd))
    cue = folder / "disc (USA) (Disc 1).cue"
    cue.write_text('FILE "ld.bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n'
                   'REM HIGH-DENSITY AREA\nFILE "hd.bin" BINARY\n  TRACK 03 MODE1/2352\n    INDEX 01 00:00:00\n',
                   encoding="ascii")
    return str(cue)


def _script_le(body: bytes) -> bytes:
    """A little-endian script with no labels: a 16-byte header, then the pages."""
    return bytes(8) + struct.pack("<I", 0) + bytes(4) + body


def _make_dir(tmp_path, name: str):
    folder = tmp_path / name
    folder.mkdir()
    return folder


def test_identity_accepts_the_usa_disc_and_refuses_the_eu_disc(tmp_path):
    usa = _write_cue(_make_dir(tmp_path, "usa"), b"U", b"MK-51052", _script_le(SCRIPT_BODY))
    eu = _write_cue(_make_dir(tmp_path, "eu"), b"E", b"MK-51052", _script_le(SCRIPT_BODY))
    other = _write_cue(_make_dir(tmp_path, "other"), b"U", b"T17716N", _script_le(SCRIPT_BODY))
    assert GameRules().identify_source(usa) == {"role": "base", "platform": "gdrom"}
    assert GameRules().identify_source(eu) is None
    assert GameRules().identify_source(other) is None


def test_platform_and_build_target_are_the_dreamcast_disc_set():
    rules = GameRules()
    assert [p["id"] for p in rules.get_platforms()] == ["gdrom"]
    targets = rules.get_build_targets()
    assert [t["id"] for t in targets] == ["disc_set"]
    assert targets[0]["platforms"] == ["gdrom"]


def test_unpack_writes_only_the_field_scripts_and_the_source_mark(tmp_path):
    cue = _write_cue(_make_dir(tmp_path, "disc"), b"U", b"MK-51052", _script_le(SCRIPT_BODY))
    out = _make_dir(tmp_path, "source")
    assert GameRules().unpack_sources({"base": cue}, str(out), lambda *_: None, lambda: False) == str(out)
    assert (out / "FIELD" / "ME201A.SCT").read_bytes() == _script_le(SCRIPT_BODY)
    assert sorted(p.name for p in out.iterdir()) == [".picoripi_disc.json", "FIELD"]


def test_a_changed_script_is_written_into_a_new_disc_set(tmp_path):
    cue = _write_cue(_make_dir(tmp_path, "disc"), b"U", b"MK-51052", _script_le(SCRIPT_BODY))
    source, translation, output = _make_dir(tmp_path, "source"), _make_dir(tmp_path, "tr"), _make_dir(tmp_path, "out")
    GameRules().unpack_sources({"base": cue}, str(source), lambda *_: None, lambda: False)
    (translation / "FIELD").mkdir()
    edited = _script_le(SCRIPT_BODY.replace(b"Hello", b"Hullo"))
    (translation / "FIELD" / "ME201A.SCT").write_bytes(edited)
    new_cue = GameRules().build_target("disc_set", str(source), str(translation), str(output),
                                       lambda *_: None, lambda: False)
    with images.open_image(new_cue) as image:
        entries = {e.path: e for e in image.entries()}
        assert image.read(entries["files/FIELD/ME201A.SCT"]) == edited


def test_the_little_endian_codec_reads_and_writes_the_same_segments():
    body = _script_le(b"\\h(Hello\\c\\h(Bye\\e")
    assert scripts.read_strings(body, big=False) == ["Hello", "Bye"]
    out, refused, missing = scripts.write_strings(body, ["Hullo", "Bye"], fixed=False, big=False)
    assert refused == [] and missing == set()
    assert scripts.read_strings(out, big=False) == ["Hullo", "Bye"]


@pytest.mark.skipif(not os.path.isfile(REAL_USA_CUE), reason="the owner's Skies of Arcadia USA disc 1 is not on disk")
def test_real_usa_disc_is_identified_and_unpacked_as_field_scripts(tmp_path):
    rules = GameRules()
    assert rules.identify_source(REAL_USA_CUE) == {"role": "base", "platform": "gdrom"}
    out = _make_dir(tmp_path, "source")
    rules.unpack_sources({"base": REAL_USA_CUE}, str(out), lambda *_: None, lambda: False)
    assert len(list((out / "FIELD").glob("*.SCT"))) == 185
    assert (out / "FIELD" / "ME201A.SCT").stat().st_size == 60746


def test_the_plugin_opens_a_dreamcast_script_as_editor_text_and_saves_the_edit():
    rules = GameRules()
    data, _ = rules.load_data_from_json_obj(_script_le(b"\\h(Hello\\c\\h(Bye\\e"))
    assert data == [["Hello", "Bye"]]
    saved = rules.save_data_to_json_obj([["Hullo", "Bye"]], {})
    assert scripts.read_strings(saved, big=False) == ["Hullo", "Bye"]


def test_scripts_use_the_script_level_budget():
    fixed = GameRules.fixed_scripts
    assert not scripts.is_fixed("FIELD/ME201A.SCT", fixed)
    assert not scripts.is_fixed("FIELD/ME002A.SCT", fixed)
    body = _script_le(b"\\h(Hi\\c\\h(Bye\\e")
    _out, refused, _missing = scripts.write_strings(body, ["Hello there", "Bye"], fixed=True, big=False)
    assert refused == [0]
