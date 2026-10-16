"""The C-built name tables of the Generation III plugin: entries as fixed units, padded, refused when longer.

The real-ROM tests read the FireRed rev 0 image from ``PICORIPI_FIRERED_ROM`` or the owner's workspace and skip
when it is not there. Nothing from the image is copied into the repository.
"""
import json
import os
from pathlib import Path

import pytest

from plugins.pokemon_fr import rom_text
from plugins.pokemon_fr.rom_text import CodecError, RomError

FACTS = rom_text.FACTS_DIR / "firered_usa_rev0.json"
ROM = Path(os.environ.get("PICORIPI_FIRERED_ROM",
                          "E:/Emulators/RomHacking/Pokemon/FireRed and LeafGreen/ISO/"
                          "Pokemon - FireRed Version (USA, Europe).gba"))


def test_species_table_units_come_from_the_facts():
    table = json.loads(FACTS.read_text(encoding="utf-8"))["c_tables"][0]
    units = rom_text.load_tables(FACTS)
    assert len(units) == table["count"] == 412
    assert units[1] == rom_text.Unit("gSpeciesName_1", table["offset"] + 11, 11, True, 0)
    assert all(unit.fixed and unit.size == 11 for unit in units)
    assert rom_text.table_files(FACTS) == {"species_names.inc": [unit.label for unit in units]}


@pytest.mark.skipif(not ROM.is_file(), reason="FireRed rev 0 ROM is not on this machine")
def test_fixed_entries_round_trip_and_refuse_a_longer_name():
    rom = ROM.read_bytes()
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    units = rom_text.load_tables(FACTS)
    texts = rom_text.read_all(rom, units, charmap)
    assert texts["gSpeciesName_1"] == "BULBASAUR"
    assert rom_text.write_all(rom, units, charmap, 0, texts) == rom
    fitting = rom_text.write_all(rom, units, charmap, 0, {"gSpeciesName_1": "UA-BULBASA"})
    assert fitting[units[1].offset:units[1].offset + 11] == charmap.encode("UA-BULBASA")
    with pytest.raises(RomError, match="13 bytes long"):
        rom_text.write_all(rom, units, charmap, 0, {"gSpeciesName_1": "UA-BULBASAUR"})
    with pytest.raises(CodecError):
        rom_text.write_all(rom, units, charmap, 0, {"gSpeciesName_1": "ЙО"})


def test_every_default_alias_targets_a_charmap_control_name():
    """Each alias in config.json names a control code of the Generation III charmap (no typo ships)."""
    import json

    from plugins.pokemon_fr import rom_text

    config = json.loads((rom_text.FACTS_DIR.parent / "config.json").read_text(encoding="utf-8"))
    charmap = json.loads((rom_text.FACTS_DIR / "charmap_gen3.json").read_text(encoding="utf-8"))
    names = {name for name, _ in charmap["names"]}
    for alias, raw in config["default_tag_mappings"].items():
        assert alias.startswith("{") and alias.endswith("}")
        assert raw.startswith("{") and raw.endswith("}")
        assert raw[1:-1] in names, raw
