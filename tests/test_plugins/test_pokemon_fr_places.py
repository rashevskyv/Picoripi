"""A text the image holds in two places is one unit: an edit writes both places and each pointer follows its copy."""
import json

from plugins.common import gba_rom
from plugins.pokemon_fr import rom_text
from plugins.pokemon_fr.rom_text import Charmap


def test_a_longer_text_in_two_places_moves_both_and_rewrites_both_pointers():
    charmap = Charmap.load()
    short = charmap.encode("ABC")
    rom = bytearray(b"\xff" * 0x200)
    rom[0x10:0x10 + len(short)] = short
    rom[0x40:0x40 + len(short)] = short
    rom[0x80:0x84] = (gba_rom.ROM_BASE + 0x10).to_bytes(4, "little")
    rom[0x84:0x88] = (gba_rom.ROM_BASE + 0x40).to_bytes(4, "little")
    units = [rom_text.Unit("t", 0x10, len(short), places=(0x40,))]

    patched = rom_text.write_all(bytes(rom), units, charmap, 0x100, {"t": "LONGER TEXT"})

    first = int.from_bytes(patched[0x80:0x84], "little") - gba_rom.ROM_BASE
    second = int.from_bytes(patched[0x84:0x88], "little") - gba_rom.ROM_BASE
    assert first != second
    assert charmap.decode(patched[first:first + 12]) == "LONGER TEXT"
    assert charmap.decode(patched[second:second + 12]) == "LONGER TEXT"
    assert patched[0x10:0x10 + len(short)] == b"\xff" * len(short)
    assert patched[0x40:0x40 + len(short)] == b"\xff" * len(short)


def test_a_shorter_text_is_written_at_both_places_in_place():
    charmap = Charmap.load()
    short = charmap.encode("ABC")
    rom = bytearray(b"\xff" * 0x100)
    rom[0x10:0x10 + len(short)] = short
    rom[0x40:0x40 + len(short)] = short
    units = [rom_text.Unit("t", 0x10, len(short), places=(0x40,))]

    patched = rom_text.write_all(bytes(rom), units, charmap, 0x80, {"t": "XY"})

    assert charmap.decode(patched[0x10:0x10 + 3]) == "XY"
    assert charmap.decode(patched[0x40:0x40 + 3]) == "XY"


def test_a_c_text_with_places_loads_every_place(tmp_path):
    facts = {"c_texts": [{"name": "c_x", "file": "c_x.inc",
                          "units": [["L1", 0x10, 4, "", [0x40, 0x80]], ["L2", 0x100, 3]]}]}
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(facts), encoding="utf-8")

    units = rom_text.c_text_units(path)

    assert units == [rom_text.Unit("L1", 0x10, 4, places=(0x40, 0x80)), rom_text.Unit("L2", 0x100, 3)]
