"""Glossary seeds of the Pokémon plugins from their name tables (synthetic tables only: the names are invented).

The shared collector (plugins/common/name_seeds.py) decides what a term is; each plugin's reader decides which rows
are the names. The tables here are written by the codecs themselves, so the readers see real file layouts.
"""
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.common import gfmsg
from plugins.common.name_seeds import INFLECTED_FORM, SECTION_RANK, TermCollector, role_of

CHARMAP = Path(__file__).resolve().parents[2] / "plugins" / "pokemon_gen4" / "charmaps" / "charmap_dp_hgss.txt"


def _project(root: Path, rels):
    """A stand-in for the project manager: the blocks it lists, and the files under ``root``."""
    blocks = [SimpleNamespace(source_file=rel) for rel in rels]
    return SimpleNamespace(project=SimpleNamespace(blocks=blocks), get_absolute_path=lambda rel: str(root / rel))


class TestCollector:
    def test_a_term_is_seeded_once_and_the_first_section_keeps_it(self):
        collector = TermCollector()
        collector.add_table("a", ["Zorblet", "Quaxly"], "Pokémon", "a table")
        collector.add_table("b", ["ZORBLET", "Frimble"], "Items", "b table")
        assert [(e["term"], e["section"]) for e in collector.entries] == [
            ("Zorblet", "Pokémon"), ("Quaxly", "Pokémon"), ("Frimble", "Items")]

    def test_placeholders_and_long_rows_are_no_terms(self):
        collector = TermCollector()
        collector.add_table("t", ["??????????", "-", "", "₧₦ Trainer", "Plain {CHAR E447}", "A" * 41, "Okay"], "Moves", "t")
        assert [e["term"] for e in collector.entries] == ["Okay"]

    def test_a_table_without_section_is_read_for_context_only(self):
        collector = TermCollector()
        collector.add_table("t", ["Zorblet"], "", "t")
        assert collector.entries == []

    def test_the_source_reference_names_the_table_and_the_row(self):
        collector = TermCollector()
        collector.add_table("message/x/monsname.dat", ["", "Zorblet"], "Pokémon", "monsname table")
        assert collector.entries[0]["source_ref"] == "message/x/monsname.dat line 1"
        assert collector.entries[0]["description"] == "monsname table"


class TestTableRoles:
    def test_a_stem_finds_its_role_and_section(self):
        assert role_of("monsname")[3] == "Pokémon"
        assert role_of("wazaname")[3] == "Moves"
        assert role_of("unknown_stem") is None

    @pytest.mark.parametrize("stem", ["itemname_plural", "itemname_acc", "place_name_out", "place_name_indirect"])
    def test_an_inflected_table_gives_context_not_terms(self, stem):
        assert INFLECTED_FORM.fullmatch(stem)
        assert not INFLECTED_FORM.fullmatch("itemname")

    def test_specific_names_rank_before_clothing_and_places(self):
        assert SECTION_RANK["Pokémon"] < SECTION_RANK["Types"] < SECTION_RANK["Items"] < SECTION_RANK["Places"]


class TestFrReader:
    def test_c_name_tables_read_the_quoted_name_of_each_row(self):
        fr = importlib.import_module("plugins.pokemon_fr.rules")
        text = '[SPECIES_A] = _("ZORBLET"),\n[SPECIES_B] = _("??????????"),\n'
        assert fr._fr_name_texts("species_names", text) == ["ZORBLET", "??????????"]

    def test_items_read_only_the_name_field(self):
        fr = importlib.import_module("plugins.pokemon_fr.rules")
        text = '.name = _("TONIC"),\n.description = _("A long description that is not a name."),\n'
        assert fr._fr_name_texts("items", text) == ["TONIC"]

    def test_an_inc_table_reads_the_dollar_terminated_strings(self):
        fr = importlib.import_module("plugins.pokemon_fr.rules")
        assert fr._fr_name_texts("type_names", '.string "NORMAL$", 7\n.string "FIGHT$", 7\n') == ["NORMAL", "FIGHT"]

    def test_other_language_files_are_skipped(self):
        fr = importlib.import_module("plugins.pokemon_fr.rules")
        assert fr._OTHER_LANGUAGE.search("species_names_de")
        assert not fr._OTHER_LANGUAGE.search("species_names_en")


class TestGscReader:
    def test_the_name_lines_of_a_names_file(self):
        gsc = importlib.import_module("plugins.pokemon_gsc.rules")
        text = '\tdname "ZORBLET"\n\tli "POUND"\n; li "NOT A NAME"\n\tdw Normal\n'
        assert [m.group(1) for m in gsc._GSC_NAME_LINE.finditer(text)] == ["ZORBLET", "POUND"]


class TestBdspNames:
    def test_the_prefix_is_removed_from_a_name_table_stem(self):
        bdsp = importlib.import_module("plugins.pokemon_bdsp.rules")
        assert bdsp._BDSP_PREFIX.sub("", "english_ss_monsname") in bdsp._BDSP_NAME_TABLES
        assert bdsp._BDSP_PREFIX.sub("", "english_dlp_whitelist_monsname") not in bdsp._BDSP_NAME_TABLES


class TestGen4Banks:
    def test_a_bank_of_species_gives_species_terms_and_skips_its_placeholders(self, tmp_path):
        from plugins.common import gen4msg
        from plugins.pokemon_gen4.rules import GameRules
        codec = gen4msg.Codec(str(CHARMAP))
        texts = ["", "ZORBLET", "QUAXLY"]
        bank = gen4msg.encode_bank(gen4msg.Bank(key=0x1234, lines=[codec.encode_line(t) for t in texts]))
        rel = "text/msgdata+msg.narc/0362.msg"
        (tmp_path / rel).parent.mkdir(parents=True)
        (tmp_path / rel).write_bytes(bank)
        holder = SimpleNamespace(mw=SimpleNamespace(project_manager=_project(tmp_path, [rel])))
        entries = GameRules.get_glossary_seed_entries(holder)
        assert [(e["term"], e["section"]) for e in entries] == [("ZORBLET", "Pokémon"), ("QUAXLY", "Pokémon")]
        assert entries[0]["source_ref"] == f"{rel} line 1"

    def test_a_bank_outside_the_name_banks_is_not_read(self, tmp_path):
        from plugins.pokemon_gen4.rules import GameRules
        rel = "text/msgdata+msg.narc/0001.msg"
        (tmp_path / rel).parent.mkdir(parents=True)
        (tmp_path / rel).write_bytes(b"\x00" * 8)
        holder = SimpleNamespace(mw=SimpleNamespace(project_manager=_project(tmp_path, [rel])))
        assert GameRules.get_glossary_seed_entries(holder) == []


class TestSwitchTables:
    def test_a_table_of_terms_ranks_before_the_clothing_table_that_repeats_a_type(self, tmp_path):
        rules = importlib.import_module("plugins.pokemon_nx.rules")
        rels = ["message/dat/English/common/dressup_item_name.dat", "message/dat/English/common/typename.dat"]
        for rel, names in zip(rels, [["Fire Coat"], ["Fire", "Water"]]):
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel).write_bytes(gfmsg.write([(gfmsg.from_editor(n), 0) for n in names]))
        holder = SimpleNamespace(mw=SimpleNamespace(project_manager=_project(tmp_path, rels)))
        entries = rules.GameRules.get_glossary_seed_entries(holder)
        by_term = {e["term"]: e["section"] for e in entries}
        assert by_term["Fire"] == "Types"
        assert by_term["Fire Coat"] == "Items"
        assert by_term["Water"] == "Types"


class TestSunMoonLabels:
    def test_the_tables_name_the_species_and_leave_ultra_unnamed(self):
        gen7 = importlib.import_module("plugins.pokemon_gen7.rules")
        assert gen7.table_game("Pokémon Sun / Moon (3DS)") == "sm"
        assert gen7.table_game("Pokémon Ultra Sun / Ultra Moon (3DS)") == "ultra"
        assert gen7.table_name("romfs/a/0/3/2/055.dat") == "055 Species names"
        assert gen7.table_name("romfs/a/0/3/2/055.dat", "ultra") == "055 Game text"

    def test_every_pokemon_plugin_with_name_tables_declares_the_glossary_seed(self):
        for plugin in ("pokemon_gen1", "pokemon_gen4", "pokemon_gen5", "pokemon_gen6", "pokemon_gen7", "pokemon_gsc",
                       "pokemon_fr", "pokemon_bdsp", "pokemon_nx", "pokemon_trinity"):
            rules = importlib.import_module(f"plugins.{plugin}.rules")
            caps = rules.GameRules.get_capabilities(SimpleNamespace(mw=None))
            assert "glossary_seed" in caps, plugin
