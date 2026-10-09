"""Tests of the Pokémon Gold, Silver and Crystal (pret) plugin: asm text units, editor text, writing back."""
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.pokemon_gsc import pret_context, pret_text
from plugins.pokemon_gsc.rules import text_tiles
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "pokemon_gsc"
SAMPLE = """Route30_MapScripts:
	def_scene_scripts

TrainerYoungsterJoey:
	trainer YOUNGSTER, JOEY1, EVENT_BEAT_YOUNGSTER_JOEY, YoungsterJoey1SeenText, YoungsterJoey1BeatenText, 0, .Script

.Script:
	opentext
	writetext YoungsterJoey1AfterText
	waitbutton
	end

Route30SignScript:
	jumptext Route30SignText

YoungsterJoey1SeenText:
	text "I just lost, so"
	line "I'm trying to find"
	cont "more #MON."

	para "Wait! You look"
	line "weak! Come on,"
	cont "let's battle!"
	done

YoungsterJoey1BeatenText:
	text "Hey! It's"
	line "@"
	text_ram wStringBuffer3
	text "!"
	prompt

YoungsterJoey1AfterText: ; a comment
	text "Do you have any"
	line "RATTATA? I do!"
	done

Route30SignText:
	text "ROUTE 30"
	done

.Strings:
	db "NEW GAME@"
	db "OPTION@"

	dname "BULBASAUR"
	li "POUND"
	npctrade TRADE_DIALOGSET_COLLECTOR, ABRA, MACHOP, "MUSCLE", $37, $66, GOLD_BERRY, 37460, "MIKE", 0

	def_object_events
	object_event  5, 26, SPRITE_YOUNGSTER, SPRITEMOVEDATA_STANDING_UP, 0, 0, -1, -1, PAL_NPC_BLUE, OBJECTTYPE_TRAINER, 3, TrainerYoungsterJoey, -1
	def_bg_events
	bg_event  9, 43, BGEVENT_READ, Route30SignScript
"""
DEX = """	db "SEED@" ; species name
	dw 204, 150 ; height, weight

	db   "While it is young,"
	next "it uses the"

	page "stored in the"
	next "in order to grow.@"
"""


def test_the_plugin_loads_validates_and_round_trips():
    check_loads(PLUGIN)
    check_validator(PLUGIN)
    check_round_trip(PLUGIN, SAMPLE)


def test_units_and_editor_text():
    texts = pret_text.load(SAMPLE)
    assert texts[0] == "I just lost, so\nI'm trying to find\nmore #MON.\n\nWait! You look\nweak! Come on,\nlet's battle!"
    assert texts[1] == "Hey! It's\n@[text_ram wStringBuffer3]!"
    assert texts[4:10] == ["NEW GAME", "OPTION", "BULBASAUR", "POUND", "MUSCLE", "MIKE"]
    assert pret_text.load(DEX) == ["SEED", "While it is young,\nit uses the\n\nstored in the\nin order to grow."]


def test_unchanged_write_is_byte_exact():
    for text in (SAMPLE, DEX):
        assert pret_text.write(text, pret_text.load(text)) == text


def test_changed_units_are_written_in_place():
    texts = pret_text.load(SAMPLE)
    texts[0] = "Один рядок\nдругий\nтретій\n\nнова сторінка"
    texts[4] = "НОВА ГРА"
    texts[6] = "БУЛЬБА"
    out = pret_text.write(SAMPLE, texts)
    assert '\ttext "Один рядок"\n\tline "другий"\n\tcont "третій"\n\n\tpara "нова сторінка"\n\tdone' in out
    assert '\tdb   "НОВА ГРА@"' in out
    assert 'dname "БУЛЬБА"' in out
    again = pret_text.load(out)
    assert again[0] == texts[0] and again[4] == "НОВА ГРА" and again[6] == "БУЛЬБА"
    assert len(again) == len(texts)


def test_structure_survives_odd_edits():
    texts = pret_text.load(SAMPLE + DEX)
    count = len(texts)
    texts[0] = ""                               # an empty message keeps one string
    texts[4] = "A@\nB"                          # an inner "@" would end a db message early
    texts[-1] = "[line]tagged\n[text_ram wX]x"
    assert len(pret_text.load(pret_text.write(SAMPLE + DEX, texts))) == count


def test_quotes_are_escaped():
    texts = pret_text.load(SAMPLE)
    texts[3] = 'Say "hi"'
    out = pret_text.write(SAMPLE, texts)
    assert '\ttext "Say \\"hi\\""' in out


def test_save_is_built_from_the_source_file():
    rules = load_rules(PLUGIN)
    blocks, _names = rules.load_data_from_json_obj(SAMPLE)
    blocks[0][3] = "ROUTE 30 UA"
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([b"stale", SAMPLE.encode()])))
    out = rules.save_data_to_json_obj(blocks)
    assert '\ttext "ROUTE 30 UA"' in out and out.count("\n") == SAMPLE.count("\n")


def test_map_context_names_speakers_and_scripts():
    labels = {u.label for u in pret_text.parse(SAMPLE)}
    context = pret_context.map_context(SAMPLE, labels)
    assert context["YoungsterJoey1SeenText"]["speakers"] == ["Youngster Joey"]
    assert context["Route30SignText"]["speakers"] == ["Sign"]
    assert context["YoungsterJoey1AfterText"]["scripts"] == ["TrainerYoungsterJoey"]


def test_width_counts_tiles():
    assert text_tiles("Hello") == 5
    assert text_tiles("<PLAYER>'s #") == 7 + 1 + 1 + 4
    assert text_tiles("[text_ram wX]ab") == 2


DECOMPS = [Path(r"E:\Emulators\RomHacking\Pokemon\Crystal\port\pokecrystal"),
           Path(r"E:\Emulators\RomHacking\Pokemon\Gold and Silver\port\pokegold")]


@pytest.mark.parametrize("root", DECOMPS, ids=["pokecrystal", "pokegold"])
def test_real_decompilation_round_trip(root):
    """Every asm file: an unchanged save is byte-exact, and a message written again reads back the same."""
    if not root.is_dir():
        pytest.skip("pret decompilation not on this machine")
    units = 0
    for path in sorted(root.rglob("*.asm")):
        if path.relative_to(root).parts[0] in ("macros", "constants"):
            continue
        source = path.read_text(encoding="utf-8")
        parsed = pret_text.parse(source)
        if not parsed:
            continue
        texts = [pret_text.to_editor(u) for u in parsed]
        assert pret_text.write(source, texts) == source, path
        lines = source.split("\n")
        for unit, text in sorted(zip(parsed, texts), key=lambda pair: -pair[0].start):
            if unit.is_message:
                tokens = pret_text.from_editor(text, unit.kind, unit.hidden_at)
                lines[unit.start:unit.end] = pret_text._render(unit, tokens)
        assert pret_text.load("\n".join(lines)) == texts, path
        units += len(parsed)
    assert units > 7000
