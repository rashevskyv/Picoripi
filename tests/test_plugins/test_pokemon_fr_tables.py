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
    table = next(item for item in json.loads(FACTS.read_text(encoding="utf-8"))["c_tables"]
                 if item["name"] == "species")
    units = [unit for unit in rom_text.load_tables(FACTS) if unit.label.startswith("gSpeciesName_")]
    assert len(units) == table["count"] == 412
    assert units[1] == rom_text.Unit("gSpeciesName_1", table["offset"] + 11, 11, True, 0)
    assert all(unit.fixed and unit.size == 11 for unit in units)
    assert rom_text.table_files(FACTS)["species_names.inc"] == [unit.label for unit in units]


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
        assert raw[1:-1].split()[0] in names, raw     # the control name; its arguments are checked by the round trip


def test_an_alias_builds_the_same_bytes_as_its_raw_tag_and_reads_back():
    """An alias with an argument (``{COLOR:Red}``) builds the bytes of its raw tag (``{COLOR RED}``), and the raw tag
    reads back as itself."""
    import json

    from core.tag_utils import apply_default_mappings_only
    from plugins.pokemon_fr import rom_text

    config = json.loads((rom_text.FACTS_DIR.parent / "config.json").read_text(encoding="utf-8"))
    mappings = config["default_tag_mappings"]
    charmap = rom_text.Charmap.load()
    for alias, raw in mappings.items():
        applied, changed = apply_default_mappings_only(f"A{alias}B", mappings)
        assert changed and applied == f"A{raw}B", alias
        assert charmap.encode(applied) == charmap.encode(f"A{raw}B"), alias
        assert charmap.decode(charmap.encode(raw)[:-1]) == raw, raw


EXPECTED_COUNTS = {
    "firered_usa_rev0": {"species": 412, "moves": 355, "abilities": 78, "types": 18, "items": 375,
                         "trainer_classes": 107, "trainer_names": 743, "berries": 43},
    "emerald_usa": {"species": 412, "moves": 355, "abilities": 78, "types": 18, "items": 377,
                    "trainer_classes": 66, "trainer_names": 855, "berries": 43},
    "ruby_usa_rev0": {"species": 412, "moves": 355, "abilities": 78, "types": 18, "items": 349,
                      "trainer_classes": 58, "trainer_names": 694, "berries": 43},
}


@pytest.mark.parametrize("facts_name", sorted(EXPECTED_COUNTS))
def test_tables_have_the_decompilation_counts(facts_name):
    """Each name table of a facts file has the count its decompilation declares (checked when it was written)."""
    data = json.loads((rom_text.FACTS_DIR / f"{facts_name}.json").read_text(encoding="utf-8"))
    counts = {table["name"]: table["count"] for table in data["c_tables"]}
    assert {name: counts[name] for name in EXPECTED_COUNTS[facts_name]} == EXPECTED_COUNTS[facts_name]


def test_a_table_field_is_read_and_written_inside_its_own_size():
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    table = next(item for item in facts["c_tables"] if item["name"] == "trainer_names")
    units = rom_text.load_tables(FACTS)
    trainer = next(unit for unit in units if unit.label == "gTrainerName_25")
    assert (trainer.offset, trainer.size, trainer.fixed) == (table["offset"] + 25 * table["stride"], 12, True)
    assert trainer.size < table["stride"]        # the name is a field of a 40-byte struct, not the struct


@pytest.mark.skipif(not ROM.is_file(), reason="FireRed rev 0 ROM is not on this machine")
def test_a_struct_field_write_changes_only_its_own_bytes():
    rom = ROM.read_bytes()
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    units = rom_text.load_tables(FACTS)
    unit = next(item for item in units if item.label == "gTrainerName_25")
    patched = rom_text.write_all(rom, units, charmap, 0, {unit.label: "ROCKY"})
    changed = [at for at in range(len(rom)) if rom[at] != patched[at]]
    assert changed and all(unit.offset <= at < unit.offset + unit.size for at in changed)
    assert patched[unit.offset:unit.offset + 6] == charmap.encode("ROCKY")


def test_a_fixed_field_over_its_budget_is_flagged_by_the_analyzer():
    from plugins.pokemon_fr.config import PROBLEM_BYTE_BUDGET
    from plugins.pokemon_fr.problem_analyzer import ProblemAnalyzer
    from plugins.pokemon_fr.rules import ProblemIDs

    class Rules:
        def exceeds_byte_budget(self, block_idx, string_idx, text):
            return (block_idx, string_idx, len(text)) == (3, 7, 14)

    analyzer = ProblemAnalyzer(None, None, {PROBLEM_BYTE_BUDGET: {}}, ProblemIDs)
    analyzer.game_rules = Rules()
    analyzer._current_scan_block_idx = 3
    analyzer._current_scan_string_idx = 7
    flagged = analyzer.analyze_data_string("ABCDEFGHIJKLMN", {}, 100, None)
    assert any(PROBLEM_BYTE_BUDGET in found for found in flagged)
    analyzer._current_scan_string_idx = 8
    assert not any(PROBLEM_BYTE_BUDGET in found for found in analyzer.analyze_data_string("ABCDEFGHIJKLMN", {}, 100, None))


@pytest.mark.skipif(not ROM.is_file(), reason="FireRed rev 0 ROM is not on this machine")
def test_a_pointer_text_that_grows_moves_and_its_pointer_follows():
    """A move description longer than its unit moves to free space; the table pointer names the new place."""
    rom = ROM.read_bytes()
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    units = rom_text.load_tables(FACTS)
    table = next(item for item in facts["c_tables"] if item["name"] == "move_descriptions")
    unit = next(item for item in units if item.label == "gMoveDescription_0")
    assert not unit.fixed
    grown = rom_text.read_all(rom, [unit], charmap)[unit.label] + "\\nAND A LONGER LINE WITH MORE WORDS"
    patched = rom_text.write_all(rom, units, charmap, facts["free_start"], {unit.label: grown})
    pointer = int.from_bytes(patched[table["offset"]:table["offset"] + 4], "little") - 0x08000000
    assert pointer != unit.offset and pointer >= facts["free_start"]
    assert rom_text.read_all(patched, [rom_text.Unit(unit.label, pointer, len(charmap.encode(grown)))],
                             charmap)[unit.label] == grown


@pytest.mark.skipif(not ROM.is_file(), reason="FireRed rev 0 ROM is not on this machine")
def test_a_c_text_that_grows_moves_and_every_pointer_to_it_follows():
    """A C-built text longer than its unit moves; each pointer the code holds to it is rewritten."""
    rom = ROM.read_bytes()
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    charmap = rom_text.Charmap.load(rom_text.FACTS_DIR / facts["charmap"])
    units = rom_text.load_tables(FACTS)
    unit = next(item for item in units if item.label == "gText_PkmnsXPreventsSwitching")
    assert not unit.fixed
    old = (0x08000000 + unit.offset).to_bytes(4, "little")
    refs = []
    at = rom.find(old)
    while at >= 0:
        refs.append(at)
        at = rom.find(old, at + 1)
    assert refs
    grown = rom_text.read_all(rom, [unit], charmap)[unit.label] + "\\nAND A LONGER LINE"
    patched = rom_text.write_all(rom, units, charmap, facts["free_start"], {unit.label: grown})
    new = int.from_bytes(patched[refs[0]:refs[0] + 4], "little") - 0x08000000
    assert new != unit.offset and new >= facts["free_start"]
    assert all(patched[at:at + 4] == (0x08000000 + new).to_bytes(4, "little") for at in refs)
    assert rom_text.read_all(patched, [rom_text.Unit(unit.label, new, len(charmap.encode(grown)))],
                             charmap)[unit.label] == grown
