"""Pokémon Gen 4 unpack (plugins/pokemon_gen4/unpack.py): message banks split per member, fonts and pictures whole.

The synthetic ROMs are built here (tests/nds_rom.py); the real-data test needs PICORIPI_ROMHACKING.
"""
import struct
from pathlib import Path

import romhacking_root
from nds_rom import narc, nds_rom
from plugins.common import gen4msg
from plugins.pokemon_gen4 import unpack
from plugins.pokemon_gen4.rules import GameRules

END = 0xFFFF
FONT = struct.pack("<IIIBBBB", 16, 48, 2, 8, 8, 1, 1) + bytes(32) + bytes(2)   # one 8x8 glyph bin, 2 glyphs
PICTURE = b"RGCN" + bytes(12)


def _bank(units):
    return gen4msg.encode_bank(gen4msg.Bank(key=0x1234, lines=[[*units, END]]))


def _write(tmp_path, files, code=b"ADAE"):
    path = tmp_path / "rom.nds"
    path.write_bytes(nds_rom(files, code=code))
    return str(path)


def _tree(folder: Path):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def test_banks_are_split_and_fonts_and_pictures_are_kept_whole(tmp_path):
    rom = _write(tmp_path, {
        "msgdata/msg.narc": narc([_bank([0x41]), b"not a bank", _bank([0x42, 0x43])]),
        "fielddata/font.narc": narc([FONT]),
        "graphic/pic.narc": narc([PICTURE]),
        "data/plain.narc": narc([b"plain"]),
        "readme.bin": b"hello",
    })
    out = tmp_path / "out"
    assert unpack.extract(rom, str(out), lambda *_: None, lambda: False) == str(out)
    assert _tree(out) == {
        "text/msgdata+msg.narc/0000.msg": _bank([0x41]),
        "text/msgdata+msg.narc/0002.msg": _bank([0x42, 0x43]),
        "fielddata/font.narc": narc([FONT]),
        "graphic/pic.narc": narc([PICTURE]),
    }


def test_pictures_above_the_size_cap_are_not_kept(tmp_path, monkeypatch):
    rom = _write(tmp_path, {"graphic/pic.narc": narc([PICTURE]), "fielddata/font.narc": narc([FONT])})
    monkeypatch.setattr(unpack, "TEXTURE_NARC_MAX", 8)
    out = tmp_path / "out"
    unpack.extract(rom, str(out), lambda *_: None, lambda: False)
    assert set(_tree(out)) == {"fielddata/font.narc"}


def test_cancel_returns_none(tmp_path):
    rom = _write(tmp_path, {"msgdata/msg.narc": narc([_bank([0x41])])})
    assert unpack.extract(rom, str(tmp_path / "out"), lambda *_: None, lambda: True) is None


def test_plugin_identifies_the_cartridge_and_unpacks_it(tmp_path):
    rules = GameRules(None)
    rom = _write(tmp_path, {"msgdata/msg.narc": narc([_bank([0x41])])})
    other = tmp_path / "other.nds"
    other.write_bytes(nds_rom({}, code=b"TEST"))
    assert rules.get_platforms()[0]["id"] == "nds"
    assert rules.identify_source(rom) == {"role": "base", "platform": "nds"}
    assert rules.identify_source(str(other)) is None
    out = rules.unpack_sources({"base": rom}, str(tmp_path / "out"), lambda *_: None, lambda: False)
    assert out == str(tmp_path / "out")
    assert set(_tree(tmp_path / "out")) == {"text/msgdata+msg.narc/0000.msg", "rom/base.nds"}
    assert rules.unpack_sources({}, str(tmp_path / "none"), lambda *_: None, lambda: False) is None


DIAMOND_ROM = ("Pokemon", "Diamond and Pearl", "ISO", "Pokemon - Diamond Version (USA) (Rev 5).nds")
DIAMOND_SOURCE = ("Pokemon", "Diamond and Pearl", "source")


@romhacking_root.needs(DIAMOND_ROM, DIAMOND_SOURCE)
def test_diamond_unpack_equals_the_workspace_source(tmp_path):
    out = GameRules(None).unpack_sources({"base": str(romhacking_root.path(*DIAMOND_ROM))},
                                         str(tmp_path / "out"), lambda *_: None, lambda: False)
    unpacked = _tree(Path(out))
    unpacked.pop("rom/base.nds")       # the build keeps the clean image in the source folder
    workspace = _tree(romhacking_root.path(*DIAMOND_SOURCE))
    assert len(unpacked) == 720
    assert {path: workspace.get(path) for path in unpacked} == unpacked
