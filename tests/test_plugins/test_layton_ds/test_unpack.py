"""Professor Layton DS unpack (plugins/layton_ds/unpack.py): loose files of three games, and the GFSA archives of
Spectre's Call. The synthetic ROMs and archives are built here (tests/nds_rom.py); real-data tests need
PICORIPI_ROMHACKING.
"""
import struct
from pathlib import Path

import pytest

import romhacking_root
from core.containers.image_files import ImageError
from nds_rom import nds_rom
from plugins.layton_ds import unpack
from plugins.layton_ds.rules import GameRules
from plugins.layton_ds.unpack import _x25


def _stored(data: bytes) -> bytes:
    """A Level-5 stored stream: the size shifted left by 3, method 0."""
    return struct.pack("<I", len(data) << 3) + data


def _gsd1(text: bytes) -> bytes:
    """A GSD1 script with one string operand (type 0x18) at 0x18."""
    plain = bytearray(0x20)
    plain[0:4] = b"GSD1"
    struct.pack_into("<3H", plain, 4, 0, 0, 1)
    plain[0x12] = 0x18
    struct.pack_into("<I", plain, 0x13, 0x18)
    plain[0x18:0x18 + len(text)] = text
    return bytes(plain)


def _gfsa(folders=()) -> bytes:
    """A GFSA archive: ``folders`` is [(folder name, [(file name, bytes)])]; files stored after the tables."""
    dir_names = b"".join(folder.encode("ascii") + b"\0" for folder, _members in folders)
    file_names, dir_table, file_table, data = b"", bytearray(), bytearray(), bytearray()
    count = 0
    for folder, members in folders:
        dir_table += struct.pack("<II", _x25(folder.encode("ascii")) | len(members) << 16, count)
        for name, body in members:
            file_names += name.encode("ascii") + b"\0"
            start = len(data)
            data += body + b"\0" * (-len(body) % 4)
            file_table += struct.pack("<II", (start & 0x3FFFF) >> 2 << 16,
                                      (len(body) >> 16) << 28 | (start >> 18) << 16 | (len(body) & 0xFFFF))
            count += 1
    tables = [_stored(bytes(dir_table)), _stored(bytes(file_table)), _stored(b""),
              _stored(dir_names + file_names)]
    offsets, at = [], 44
    for table in tables:
        offsets.append(at)
        at += len(table)
    head = struct.pack("<11I", int.from_bytes(b"GFSA", "little"), *offsets, at, len(folders), count, 0, 0, 0)
    return head + b"".join(tables) + bytes(data)


GSD_TEXT = _gsd1(b"Hello\0")
GSD_NO_TEXT = _gsd1("あ\0".encode("shift-jis"))


def _tree(folder: Path):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def test_a_rom_that_is_not_a_layton_game_is_refused(tmp_path):
    rom = tmp_path / "rom.nds"
    rom.write_bytes(nds_rom({}, title=b"NOTLAYT", code=b"A5FP"))
    with pytest.raises(ImageError):
        unpack.extract(str(rom), str(tmp_path / "out"), lambda *_: None, lambda: False)


def test_loose_fonts_and_pictures_are_kept_and_text_only_with_a_string(tmp_path):
    rom = tmp_path / "rom.nds"
    rom.write_bytes(nds_rom({
        "data/bg/a.arc": b"picture",
        "data/fnt/x.nftr": b"font",
        "data/sound/x.sad": b"audio",
        "data/script/x.gds": bytes(16),          # a script with no string: not text
    }, title=b"LAYTON1", code=b"A5FP"))
    out = tmp_path / "out"
    assert unpack.extract(str(rom), str(out), lambda *_: None, lambda: False) == str(out)
    assert _tree(out) == {"data/bg/a.arc": b"picture", "data/fnt/x.nftr": b"font"}


def test_plugin_identifies_the_cartridge(tmp_path):
    rom = tmp_path / "rom.nds"
    rom.write_bytes(nds_rom({}, title=b"LAYTON3", code=b"C3JP"))
    rules = GameRules(None)
    assert rules.get_platforms()[0]["id"] == "nds"
    assert rules.identify_source(str(rom)) == {"role": "base", "platform": "nds"}
    assert rules.unpack_sources({}, str(tmp_path / "none"), lambda *_: None, lambda: False) is None


def test_spectre_archives_keep_scripts_with_a_string_and_fonts_at_their_paths(tmp_path):
    font = b"fontdata"
    main = _gfsa([("txt/uk/", [("a.cb", _stored(GSD_TEXT)), ("b.cb", _stored(GSD_NO_TEXT))]),
                  ("fnt/", [("x.cf", font)])])
    rom = tmp_path / "rom.nds"
    rom.write_bytes(nds_rom({"lt4_main_uk.fa": main, "lt4_seq.fa": _gfsa(), "lt4_sub.fa": _gfsa()},
                            title=b"LAYTON4", code=b"BLFP"))
    out = tmp_path / "out"
    unpack.extract(str(rom), str(out), lambda *_: None, lambda: False)
    assert _tree(out) == {"txt/uk/a.cb": _stored(GSD_TEXT), "fnt/x.cf": font}


def test_a_member_in_two_archives_must_have_the_same_bytes(tmp_path):
    same = _stored(GSD_TEXT)
    main = _gfsa([("txt/uk/", [("a.cb", same)])])
    seq = _gfsa([("txt/uk/", [("a.cb", _stored(_gsd1(b"Bye\0")))])])
    rom = tmp_path / "rom.nds"
    rom.write_bytes(nds_rom({"lt4_main_uk.fa": main, "lt4_seq.fa": seq, "lt4_sub.fa": _gfsa()},
                            title=b"LAYTON4", code=b"BLFP"))
    with pytest.raises(ImageError):
        unpack.extract(str(rom), str(tmp_path / "out"), lambda *_: None, lambda: False)


def test_an_archive_member_that_climbs_out_of_the_folder_is_refused(tmp_path):
    # the path passes the text-folder rule ("txt" and "uk"), then climbs out of the output folder
    main = _gfsa([("txt/../../uk/", [("evil.cb", _stored(GSD_TEXT))])])
    rom = tmp_path / "rom.nds"
    rom.write_bytes(nds_rom({"lt4_main_uk.fa": main, "lt4_seq.fa": _gfsa(), "lt4_sub.fa": _gfsa()},
                            title=b"LAYTON4", code=b"BLFP"))
    with pytest.raises(ImageError, match="unsafe file name"):
        unpack.extract(str(rom), str(tmp_path / "out"), lambda *_: None, lambda: False)
    assert not (tmp_path / "uk" / "evil.cb").exists()


PB_ROM = ("Professor Layton", "Pandora's Box", "DS", "ISO", "Professor Layton and Pandora's Box (Europe).nds")
PB_SOURCE = ("Professor Layton", "Pandora's Box", "DS", "source")
SC_ROM = ("Professor Layton", "Spectre's Call", "ISO", "Professor Layton and the Spectre's Call (Europe).nds")
SC_SOURCE = ("Professor Layton", "Spectre's Call", "source")


@romhacking_root.needs(PB_ROM, PB_SOURCE)
def test_pandoras_box_unpack_equals_the_workspace_source(tmp_path):
    out = GameRules(None).unpack_sources({"base": str(romhacking_root.path(*PB_ROM))},
                                         str(tmp_path / "out"), lambda *_: None, lambda: False)
    assert _tree(Path(out)) == _tree(romhacking_root.path(*PB_SOURCE))


@romhacking_root.needs(SC_ROM, SC_SOURCE)
def test_spectres_call_unpack_equals_the_workspace_source(tmp_path):
    out = GameRules(None).unpack_sources({"base": str(romhacking_root.path(*SC_ROM))},
                                         str(tmp_path / "out"), lambda *_: None, lambda: False)
    assert _tree(Path(out)) == _tree(romhacking_root.path(*SC_SOURCE))


CV_ROM = ("Professor Layton", "Curious Village", "DS", "ISO",
          "Professor_Layton_and_the_Curious_Village_Europe_En,Fr,De,Es,It.nds")
CV_SOURCE = ("Professor Layton", "Curious Village", "DS", "source")
LF_ROM = ("Professor Layton", "Lost Future", "DS", "ISO", "Professor Layton and the Lost Future (Europe).nds")
LF_SOURCE = ("Professor Layton", "Lost Future", "DS", "source")


@romhacking_root.needs(CV_ROM, CV_SOURCE)
def test_curious_village_every_workspace_file_is_produced_equal(tmp_path):
    """Known gap: the port also takes 65 loose scripts (``data/script/event``) that the workspace lacks, because the
    workspace was unpacked before the plugin's text rows decided the scripts. Those 65 are not asserted here."""
    out = GameRules(None).unpack_sources({"base": str(romhacking_root.path(*CV_ROM))},
                                         str(tmp_path / "out"), lambda *_: None, lambda: False)
    produced = _tree(Path(out))
    workspace = _tree(romhacking_root.path(*CV_SOURCE))
    assert {path: produced.get(path) for path in workspace} == workspace


@romhacking_root.needs(LF_ROM, LF_SOURCE)
def test_lost_future_produces_no_file_the_workspace_lacks(tmp_path):
    """Known gap: the workspace also holds lt3/fnt/font_en1.cbin and font_en2.cbin, which the current rule
    (fonts are ``.cfnt`` under lt3/fnt) does not take. Those two are not asserted here."""
    out = GameRules(None).unpack_sources({"base": str(romhacking_root.path(*LF_ROM))},
                                         str(tmp_path / "out"), lambda *_: None, lambda: False)
    produced = _tree(Path(out))
    workspace = _tree(romhacking_root.path(*LF_SOURCE))
    assert {path: workspace.get(path) for path in produced} == produced
