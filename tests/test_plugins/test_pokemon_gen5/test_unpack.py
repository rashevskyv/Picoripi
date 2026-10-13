"""Pokémon Gen 5 unpack (plugins/pokemon_gen5/unpack.py): message files with lines split per member, NFTR fonts,
NCGR pictures and gfl_font.dat kept whole.

The synthetic ROMs are built here (tests/nds_rom.py); the real-data test needs PICORIPI_ROMHACKING.
"""
from pathlib import Path

import romhacking_root
from nds_rom import narc, nds_rom
from plugins.common import gen5msg
from plugins.pokemon_gen5 import unpack
from plugins.pokemon_gen5.rules import GameRules

FONT = b"RTFN" + bytes(12)
PICTURE = b"RGCN" + bytes(12)


def _lines(*units_per_line):
    return gen5msg.write([gen5msg.Line(list(units)) for units in units_per_line])


def _tree(folder: Path):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def test_text_files_are_split_and_fonts_pictures_and_root_font_are_kept_whole(tmp_path):
    rom = tmp_path / "rom.nds"
    rom.write_bytes(nds_rom({
        "a/0/0/2": narc([_lines([0x41]), b"", _lines()]),       # member 0 has a line; 1 and 2 have none
        "a/0/0/3": narc([FONT]),
        "a/0/1/0": narc([PICTURE]),
        "a/9/9/9": narc([b"junk"]),
        "gfl_font.dat": b"font table",
    }, code=b"IRBO"))
    out = tmp_path / "out"
    assert unpack.extract(str(rom), str(out), lambda *_: None, lambda: False) == str(out)
    assert _tree(out) == {
        "text/a_0_0_2/0000.msg": _lines([0x41]),
        "a/0/0/3": narc([FONT]),
        "a/0/1/0": narc([PICTURE]),
        "gfl_font.dat": b"font table",
    }


def test_plugin_identifies_the_cartridge(tmp_path):
    rules = GameRules(None)
    rom = tmp_path / "rom.nds"
    rom.write_bytes(nds_rom({"gfl_font.dat": b"x"}, code=b"IREO"))
    assert rules.get_platforms()[0]["id"] == "nds"
    assert rules.identify_source(str(rom)) == {"role": "base", "platform": "nds"}
    assert rules.unpack_sources({"base": str(rom)}, str(tmp_path / "out"), lambda *_: None, lambda: False) == \
        str(tmp_path / "out")
    assert set(_tree(tmp_path / "out")) == {"gfl_font.dat"}


BW_ROM = ("Pokemon", "Black and White", "ISO", "Pokemon - Black Version (DSi Enhanced)(USA) (E)(SweeTnDs).nds")
BW_SOURCE = ("Pokemon", "Black and White", "source")


@romhacking_root.needs(BW_ROM, BW_SOURCE)
def test_black_unpack_equals_the_workspace_source(tmp_path):
    out = GameRules(None).unpack_sources({"base": str(romhacking_root.path(*BW_ROM))},
                                         str(tmp_path / "out"), lambda *_: None, lambda: False)
    unpacked = _tree(Path(out))
    assert unpacked == _tree(romhacking_root.path(*BW_SOURCE))
