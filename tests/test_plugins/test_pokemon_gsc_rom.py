"""ROM mode of the Pokemon Gold, Silver and Crystal plugin: the Generation II codec and the real ROMs.

The real-ROM tests read the images from ``PICORIPI_GSC_ROMS`` (a folder) or the owner's workspace and skip when they
are not there. Nothing from an image is copied into the repository.
"""
import hashlib
from pathlib import Path

import pytest

from plugins.pokemon_gen1 import rom_project, rom_text
from plugins.pokemon_gsc import rules as gsc_rules

WORKSPACE = Path("E:/Emulators/RomHacking/Pokemon")
ROMS = {
    "gold": WORKSPACE / "Gold and Silver/ISO/Pokemon - Gold Version (UE) [!].gbc",
    "silver": WORKSPACE / "Gold and Silver/ISO/Pokemon - Silver Version (UE) [!].gbc",
    "crystal": WORKSPACE / "Crystal/ISO/Pokemon - Crystal Version (UE) (V1.0) [!].gbc",
}
FACTS = gsc_rules.ROM_FACTS_DIR


def _rom(name):
    path = ROMS[name]
    if not path.is_file():
        pytest.skip(f"{name} ROM is not on this machine")
    return path


def _names():
    charmap = [["<PLAYER>", 0x52], ["@", 0x50], ["!", 0xE7], [" ", 0x7F], ["a", 0xA0], ["b", 0xA1], ["c", 0xA2],
               ["d", 0xA3], ["e", 0xA4]]
    return rom_text.Names(charmap, {"wStringBuffer": 0xCF4B}, {"_Target": (0x64, 0x4567)}, gen2=True)


def test_generation_two_far_reference_uses_opcode_0x16():
    names = _names()
    raw = bytes([0x00, 0xA0, 0x57, 0x16, 0x67, 0x45, 0x64, 0x00, 0x58])
    lines = rom_text.decode(raw, names)
    assert lines == [("text", '"a"'), ("done", ""), ("text_far", "_Target"), ("text_start", ""), ("prompt", "")]
    assert rom_text.encode(lines, names) == raw


def test_generation_two_sounds_and_buffer_codes_round_trip():
    names = _names()
    raw = bytes([0x00, 0xA0, 0x14, 0x01, 0x0F, 0x15, 0x12, 0x50])   # buffer 1, item sound, day, fanfare
    lines = rom_text.decode(raw, names)
    assert lines[1] == ("text_buffer", "1")
    assert rom_text.encode(lines, names) == raw


def test_generation_two_facts_are_present_for_every_image():
    for name in ("pokegold", "pokesilver", "pokecrystal", "pokecrystal11"):
        facts = FACTS / f"{name}.json"
        assert facts.is_file(), name


@pytest.mark.parametrize("name", ["gold", "silver", "crystal"])
def test_real_rom_unpacks_and_builds_back_to_the_same_bytes(name, tmp_path):
    rom_path = _rom(name)
    assert rom_project.identify(str(rom_path), FACTS) == {"role": "rom", "platform": "gb"}
    project = tmp_path / "project"
    rom_project.unpack(str(rom_path), str(project), lambda *_: None, lambda: False, FACTS)
    built = Path(rom_project.build(str(project / rom_project.SOURCE_DIR), str(tmp_path / "translation"),
                                   str(tmp_path / "out"), lambda *_: None, lambda: False, FACTS))
    assert hashlib.sha1(built.read_bytes()).hexdigest() == hashlib.sha1(rom_path.read_bytes()).hexdigest()
