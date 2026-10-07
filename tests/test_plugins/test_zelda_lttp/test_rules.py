"""A Link to the Past (zelda3 PC port) plugin: dialogue.txt round trip, line codes, letters, context, real files."""
import json
from pathlib import Path

import pytest

from core import font_formats, texture_formats
from plugins.testing import check_loads, check_round_trip, check_validator
from plugins.zelda_lttp import rules as lttp

PLUGIN = "zelda_lttp"
SAMPLE = ("1: \n2: [Speed 00][3]      [2]    >[Choose]\n"
          "3: Meet the elder of the village[2]and get the Master Sword.[Waitkey][Scroll]Go![Scroll]Now!\n")
WORKSPACE = Path(r"E:\Emulators\RomHacking\Zelda\A Link to the Past")
SOURCE = WORKSPACE / "source"


def test_the_plugin_loads_round_trips_and_validates():
    check_loads(PLUGIN)
    check_round_trip(PLUGIN, SAMPLE)
    check_validator(PLUGIN)


def test_line_codes_show_as_breaks_and_go_back_unchanged():
    message = "I sense[2]that a[3]mighty evil[Waitkey][Scroll]force[Scroll]guides him."
    shown = lttp.to_editor(message)
    assert shown == "I sense\n[2]that a\n[3]mighty evil[Waitkey]\n[Scroll]force\n[Scroll]guides him."
    assert lttp.from_editor(shown) == message
    assert lttp.to_editor("[2]first") == "[2]first"


def test_a_typed_break_gets_the_code_of_its_line():
    assert lttp.from_editor("one\ntwo\nthree\nfour") == "one[2]two[3]three[Scroll]four"
    assert lttp.from_editor("one\n[3]two\nthree") == "one[3]two[Scroll]three"


def test_letters_save_as_their_glyph_and_tags_stay():
    rules = check_loads(PLUGIN)
    rules.translation_map = lambda: {"Б": "Q", "А": "A"}
    saved = rules.save_data_to_json_obj([["Бах [Name]А"]], {})
    assert saved == "1: Qах [Name]A\n"
    assert rules.load_data_from_json_obj(saved)[0][0][0] == "Бах [Name]A"   # a look-alike stays Latin


def test_the_dialogue_file_must_be_numbered_line_by_line():
    with pytest.raises(ValueError):
        lttp.parse_dialogue("1: a\n3: b\n")


def test_context_from_the_port_code_names_speakers_and_source_lines():
    rules = check_loads(PLUGIN)
    assert "speaker_attribution" in rules.get_capabilities()
    assert rules.get_speaker_for_string(0, 30) == "Zelda"          # line 31: "[Name], be careful out there!"
    scene = rules.get_scene_context_for_string(0, 31)               # line 32: her telepathy, from the uncle scene
    assert scene["resource"].startswith("src/sprite_main.c:") and scene["flow_ids"] == ["Uncle_AtHouse"]
    assert "Uncle_AtHouse" in rules.get_ai_flow_context_for_string(0, 31)
    assert rules.get_translation_context_for_string(0, 274)["content_role"] == "Narration"
    assert rules.get_speaker_for_string(1, 30) is None


def test_the_context_scanner_reads_message_calls_and_tables():
    from plugins.zelda_lttp import port_context
    assert port_context._ints("(minigame_credits == 0) ? 0x163 : 0x17f") == [0x163, 0x17F]
    assert port_context._ints("kWishPondMsgs[sprite_head_dir[k] - 1]") == []
    assert port_context.speaker_of("Sprite_1F_SickKid") == "SickKid"
    assert port_context.speaker_of("Zelda_InCell") == "Zelda"


# -- the workspace's real files (skipped where they are not on disk) -------------------------------

needs_source = pytest.mark.skipif(not (SOURCE / "dialogue.txt").is_file(), reason="LttP workspace not unpacked")


@needs_source
def test_real_dialogue_saves_back_unchanged():
    rules = check_loads(PLUGIN)
    text = (SOURCE / "dialogue.txt").read_text(encoding="utf-8")
    blocks, _names = rules.load_data_from_json_obj(text)
    assert len(blocks[0]) == 397
    assert rules.save_data_to_json_obj(blocks, {}) == text


@needs_source
def test_real_font_and_text_sheets_write_back_byte_exact():
    folder = Path(lttp.__file__).parent
    font = json.loads((folder / "font_sources.json").read_text(encoding="utf-8"))[0]
    data = (SOURCE / font["path"]).read_bytes()
    metadata, sheets = font_formats.extract(font["format"], data, font["params"])
    assert font_formats.pack(font["format"], metadata, sheets, data, font["params"]) == data
    assert font_formats.char_map(metadata)["A"] == 0
    for entry in json.loads((folder / "texture_sources.json").read_text(encoding="utf-8")):
        data = (SOURCE / entry["path"]).read_bytes()
        textures = texture_formats.read(entry["format"], data, entry["params"])
        assert texture_formats.write(entry["format"], data, {0: textures[0].image}, entry["params"]) == data
