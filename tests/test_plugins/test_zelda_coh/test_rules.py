"""Cadence of Hyrule plugin: localization.xml load/save, tags, speakers, hooks; the real file when it is here."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.zelda_coh import rules as coh_rules
from plugins.zelda_coh.locxml import LocalizationFile
from plugins.zelda_coh.tags import TAG_RE, describe, from_editor, to_editor

REAL = Path(r"E:\Emulators\RomHacking\Zelda\Cadence of Hyrule\source\localization.xml")


def _text(string_id, key, en, ja="ja"):
    english = '<string lang="en" />' if en is None else f'<string lang="en">{en}</string>'
    return (f'  <text description="{key}" id="{string_id}">\r\n    {english}\r\n'
            f'    <string lang="ja">{ja}</string>\r\n  </text>\n')


def sample() -> bytes:
    """Mixed line endings, a self-closing string, an entity and a raw line break, as in the real file."""
    body = "".join([
        _text(0, "no_string", None),
        _text(22, "mainmenu_newgame", "NEW GAME"),
        _text(1096, "zora_0", "What's up, friend?[p]Get [c:s]flippers[/c] &amp; swim![n]Bye."),
        _text(1097, "zora_1", "Ha![n]"),
        _text(1170, "error_1", "I AM ERROR.\r\n"),
        _text(1330, "deku_butler_yves", "Welcome, [i:yves]!"),
        _text(3000, "ability_spin_attack_flyaway", "Spin Attack"),
        _text(4000, "antifairy_1", "Bomb Fairy"),
        _text(6500, "character_link", "Link"),
        _text(6600, "character_link_explanation", "[c:b]Link[/c] can use shields."),
    ])
    return ("<?xml version='1.0' encoding='utf8'?>\n<strings>\n  <!-- UI TEXT (0-999) -->\n"
            + body + "</strings>\r\n").encode("utf-8")


def test_plugin_loads_and_validates():
    rules = check_loads("zelda_coh")
    assert rules.get_display_name() == "Zelda: Cadence of Hyrule"
    assert ".xml" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator("zelda_coh")


def test_sample_round_trip_and_unedited_save_is_byte_exact():
    check_round_trip("zelda_coh", sample())
    rules = load_rules("zelda_coh")
    blocks, names = rules.load_data_from_json_obj(sample())
    assert [names[str(i)] for i in range(len(blocks))] == [
        "Menus and options", "NPC dialogue", "Item names", "Enemy names", "Playable characters"]
    assert blocks[0] == ["", "NEW GAME"]
    assert blocks[1][0] == "What's up, friend?[p]\nGet [c:s]flippers[/c] & swim!\nBye."
    assert blocks[1][2] == "I AM ERROR.[cr][lf]"
    assert rules.save_data_to_json_obj(blocks, names) == sample()


def test_edits_touch_only_the_english_strings():
    rules = load_rules("zelda_coh")
    blocks, names = rules.load_data_from_json_obj(sample())
    blocks[0][0] = "Порожньо"                       # a self-closing string gets content
    blocks[0][1] = "НОВА ГРА"
    blocks[1][0] = "Як справи?[p]\nВізьми [c:s]ласти[/c] & <пливи>!"
    saved = rules.save_data_to_json_obj(blocks, names)
    text = saved.decode("utf-8")
    assert '<string lang="en">Порожньо</string>' in text
    assert "Візьми [c:s]ласти[/c] &amp; &lt;пливи&gt;!" in text and "[p]Візьми" in text
    assert text.count('<string lang="ja">ja</string>') == 10 and text.endswith("</strings>\r\n")
    assert load_rules("zelda_coh").load_data_from_json_obj(saved)[0] == blocks


def test_save_builds_on_the_newest_version_that_parses():
    rules = load_rules("zelda_coh")
    blocks, names = rules.load_data_from_json_obj(sample())
    blocks[0][1] = "НОВА ГРА"
    translated = rules.save_data_to_json_obj(blocks, names)
    rules.reset_runtime_state()
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([b"broken", translated, sample()])))
    blocks[3][0] = "Бомбофея"
    again = load_rules("zelda_coh").load_data_from_json_obj(rules.save_data_to_json_obj(blocks, names))[0]
    assert again[0][1] == "НОВА ГРА" and again[3][0] == "Бомбофея"


def test_other_files_give_one_empty_block():
    assert load_rules("zelda_coh").load_data_from_json_obj(b"<?xml version='1.0'?><credits/>") == ([[]], {})


CREDITS = ('﻿<?xml version="1.0"?>\r\n<credits>\r\n  <line type="header">Brace Yourself Games</line>\r\n'
           '  <line type="header2">GAME DESIGN</line>\r\n  <line type="name">Álex &amp; Co</line>\r\n'
           '  <line type="header"></line>\r\n'
           '  <line type="header" textKey="credits_job27">Thanks for grooving!</line>\r\n</credits>\r\n').encode("utf-8")


def test_credits_roll_is_one_block_of_the_drawn_lines():
    check_round_trip("zelda_coh", CREDITS)
    rules = load_rules("zelda_coh")
    blocks, names = rules.load_data_from_json_obj(CREDITS)
    # empty spacer lines and lines whose text comes from localization.xml (textKey) are not strings
    assert names == {"0": "Credits roll"} and blocks == [["Brace Yourself Games", "GAME DESIGN", "Álex & Co"]]
    assert rules.save_data_to_json_obj(blocks, names) == CREDITS
    blocks[0][1] = "ДИЗАЙН ГРИ"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved == CREDITS.replace(b"GAME DESIGN", "ДИЗАЙН ГРИ".encode("utf-8"))
    rules.reset_runtime_state()
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([saved, CREDITS])))
    blocks[0][2] = "Алекс & Ко"
    assert b"\xd0\x94\xd0\x98" in rules.save_data_to_json_obj(blocks, names)    # built on the newest version


@pytest.mark.parametrize("text", ["a[n]b[p]c", "[p][n]x", "x[p]", "tail\r\n", "[n][n]", "plain"])
def test_editor_form_is_reversible(text):
    assert from_editor(to_editor(text)) == text


def test_tags():
    for tag in ("[c:b]", "[/c]", "[i:button_a]", "[i:buttons,3]", "[s:9]", "[z]", "[f]", "[p]"):
        assert TAG_RE.fullmatch(tag) and describe(tag)
    assert not TAG_RE.fullmatch("[c:x]") and describe("[c:x]") == ""
    manager = load_rules("zelda_coh").tag_manager
    assert manager.is_tag_legitimate("[i:link]") and not manager.is_tag_legitimate("[bogus]")


@pytest.mark.parametrize("key,speaker,addressee", [
    ("zora4_1", "Zora", None), ("deku_king_yves", "Deku King", "Yves"), ("fortune2_flavor", "Fortune Teller", None),
    ("dark_fairy_1_octavo", "npc:dark_fairy", "Octavo"), ("cutscene_2_Cadence1", "Cadence", None),
    ("octavo_0_dungeonmode", "Octavo", None), ("deku_tree_skullkid_first", "Great Deku Tree", "Skull Kid"),
    ("TUTORIAL_PLAYER_INTRO1", None, None), ("postcharacterunlockcutscene_link_yves", None, None),
])
def test_speaker_and_addressee_from_the_string_key(key, speaker, addressee):
    assert coh_rules.speaker_of(key) == speaker
    assert coh_rules.addressee_of(key) == addressee


# -- hooks that read the project's file ------------------------------------------------------

class _ProjectManager:
    def __init__(self, root: Path):
        self.root = root
        self.project = SimpleNamespace(blocks=[SimpleNamespace(source_file="localization.xml"),
                                               SimpleNamespace(source_file="credits.xml")])

    def get_absolute_path(self, rel, is_translation=False):
        return str(self.root / rel)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "localization.xml").write_bytes(sample())
    (tmp_path / "credits.xml").write_bytes(CREDITS)
    mw = SimpleNamespace(project_manager=_ProjectManager(tmp_path),
                         block_to_project_file_map={**{i: 0 for i in range(5)}, 5: 1},
                         font_map={"N": {"width": 10}, "E": {"width": 9}, "W": {"width": 12}, " ": {"width": 5},
                                   "G": {"width": 10}, "A": {"width": 10}, "M": {"width": 12}})
    return load_rules("zelda_coh", mw)


def test_dialogue_hooks(project):
    assert project.get_speaker_for_string(1, 0) == "Zora"
    assert project.get_addressee_for_string(1, 3) == "Yves"
    assert project.get_speaker_for_string(2, 0) is None                    # item names are not spoken
    assert project.get_ai_flow_group_for_string(1, 0) == project.get_ai_flow_group_for_string(1, 1) == "coh:zora"
    assert project.get_message_attributes(1, 2) == {"id": 1170, "key": "error_1", "block": "NPC dialogue"}
    assert project.get_scene_context_for_string(1, 0)["label"] == "zora_0"
    assert project.is_placeholder_speaker("npc:mellan") and not project.is_placeholder_speaker("Zora")
    assert project.get_message_attributes(5, 1) == {"id": 1, "key": "header2", "block": "Credits roll"}
    assert project.get_scene_context_for_string(5, 1)["resource"] == "credits.xml"
    assert project.get_speaker_for_string(5, 0) is None


def test_context_layout_and_glossary_seed(project):
    assert project.get_translation_context_for_string(3, 0) == {
        "content_role": "Enemy name", "has_speaker": False, "glossary_section": "Enemies"}
    assert "glossary_section" not in project.get_translation_context_for_string(4, 1)
    # NEW GAME: 3 x N/E/W + space + G/A/M/E = 10+9+12+5+10+10+12+9 = 77
    assert project.get_string_layout(0, 1) == {"warn_width": 101, "max_width": 124}
    assert project.get_string_layout(1, 0) is None                         # wrapped by the game
    assert [(e["term"], e["section"]) for e in project.get_glossary_seed_entries()] == [
        ("Spin Attack", "Items"), ("Bomb Fairy", "Enemies"), ("Link", "Characters")]
    assert project.calculate_string_width_override("[c:b]NEW[/c]", project.mw.font_map) == 31


# -- the game's own file ---------------------------------------------------------------------

@pytest.mark.skipif(not REAL.exists(), reason="Cadence of Hyrule romfs not extracted here")
def test_real_file_round_trips_byte_exact():
    data = REAL.read_bytes()
    rules = load_rules("zelda_coh")
    blocks, names = rules.load_data_from_json_obj(data)
    assert sum(map(len, blocks)) == len(LocalizationFile(data).entries) == 1809 and len(blocks) == 15
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[1][0] = "Ґанон і Гайрул — «їжак»[p]\nдругий рядок"
    edited = rules.save_data_to_json_obj(blocks, names)
    assert load_rules("zelda_coh").load_data_from_json_obj(edited)[0] == blocks
    assert len(edited) != len(data) and edited.count(b'<string lang="ja">') == data.count(b'<string lang="ja">')


@pytest.mark.skipif(not (REAL.parent / "credits.xml").exists(), reason="Cadence of Hyrule credits.xml not here")
def test_real_credits_round_trip_byte_exact():
    data = (REAL.parent / "credits.xml").read_bytes()
    rules = load_rules("zelda_coh")
    blocks, names = rules.load_data_from_json_obj(data)
    assert names == {"0": "Credits roll"} and "GAME DESIGN" in blocks[0] and len(blocks[0]) > 300
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][blocks[0].index("GAME DESIGN")] = "ДИЗАЙН ГРИ"
    assert load_rules("zelda_coh").load_data_from_json_obj(rules.save_data_to_json_obj(blocks, names))[0] == blocks


@pytest.mark.skipif(not (REAL.parent / "textures_bin" / "texture_pack.bin").exists(),
                    reason="Cadence of Hyrule texture_pack.bin not in source")
def test_real_text_textures_write_into_the_zlib_pack(tmp_path):
    import json
    import zlib

    from core.texture_formats import sources
    descriptors = json.loads((Path(coh_rules.__file__).parent / "texture_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(REAL.parent), "translation_path": str(tmp_path)})
    assert [s.name for s in found] == ["TitleLogo"] + [f"UI_BorderNames_English_{n}"
                                                       for n in ("Charms", "Items", "Map", "Weapons")]
    assert all(s.pixel_format == "RGBA8" for s in found)
    logo = found[0]
    image = logo.read_original().image.convert("RGBA")
    image.paste((255, 0, 255, 255), (0, 0, 40, 40))
    assert logo.write(image)
    written = tmp_path / "textures_bin" / "texture_pack.bin"
    original = zlib.decompress((REAL.parent / "textures_bin" / "texture_pack.bin").read_bytes())
    plain = zlib.decompress(written.read_bytes())
    start, size = logo.params["file_offset"], logo.params["file_size"]
    assert len(plain) == len(original) and plain[:start] == original[:start]
    assert plain[start + size:] == original[start + size:] and plain[start:start + size] != original[start:start + size]
    assert logo.read_current().image.getpixel((5, 5)) == (255, 0, 255, 255)
    sources.write_many([(logo, None)])                     # revert: the pack holds the game's own textures again
    assert zlib.decompress(written.read_bytes()) == original
