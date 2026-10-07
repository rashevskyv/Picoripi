"""Paper Mario: The Thousand-Year Door plugin: message format, tags, translation map, hooks; the real files when present."""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.formats import SaveContext
from plugins.paper_mario_gc import msgfile
from plugins.paper_mario_gc.rules import LAYOUTS
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "paper_mario_gc"
PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN
WORKSPACE = Path(r"E:\Emulators\RomHacking\Paper Mario\Thousand-Year Door\GC\source")
MSG = WORKSPACE / "files" / "msg" / "US"
UKRAINIAN = "Ґанок і їжак, «є» п’ять ЩЮЯ"
# a Japanese leftover as the US files keep it: UTF-16LE kana with single-byte line breaks and tags
LEFTOVER = "シンニュウシャ".encode("utf-16-le") + b"\x01\xff\n<k>"


def area_file() -> bytes:
    """A small area file: dialogue with tags, a tattle keyed by a Japanese NPC name, a leftover."""
    return msgfile.build([
        msgfile.Entry(b"stg1_nok_01", b"Mail call!<wait 250> Hey!\n<k>\n<p>\nIt's <col c00000ff>Mario</col>!\n<k>"),
        msgfile.Entry("村長".encode("cp932"), b"<keyxon>\nThat's Kroop, the mayor.\n<k>"),
        msgfile.Entry(b"stg1_nok_02", LEFTOVER),
        msgfile.Entry(b"stg1_nok_03", b"<kanban>\n\xb3 To Petal Meadows \xd8\n<k>"),
    ])


def global_file() -> bytes:
    return msgfile.build([
        msgfile.Entry(b"name_mario", b"Mario"),
        msgfile.Entry(b"in_kinoko", b"Mushroom"),
        msgfile.Entry(b"msg_kinoko", b"A dried mushroom.\nRestores 5 HP."),
        msgfile.Entry(b"msg_menu_mario", b"Check Mario's stats here."),
        msgfile.Entry(b"btl_un_kuriboo", b"Goomba"),
        msgfile.Entry(b"btl_hlp_kuriboo", b"<keyxon>\nThat's a Goomba.\n<k>"),
        msgfile.Entry(b"sys_no_coin", b"<system>\nYou don't have enough coins!\n<k>"),
    ])


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert ".txt" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_samples_survive_load_and_save():
    check_round_trip(PLUGIN, area_file())
    check_round_trip(PLUGIN, global_file())


def test_format_round_trip_and_errors():
    data = area_file()
    assert msgfile.build(msgfile.parse(data)) == data
    assert msgfile.parse(b"\0") == []
    with pytest.raises(ValueError):
        msgfile.parse(b"key\0text")
    with pytest.raises(ValueError):
        msgfile.parse(b"key\0text\0\0junk")
    assert load_rules(PLUGIN).load_data_from_json_obj(b"not a message file") == ([[]], {})


def test_tags_symbols_and_raw_bytes_are_shown_readably_and_written_back():
    raw = b"<wait 250>Hi!\n<col c00000ff>Red</col> \xb3\xd8\xde\xd0 caf\xe9\x01"
    text = msgfile.decode(raw)
    assert text == "{wait 250}Hi!\n{col c00000ff}Red{/col} ↓♪☆♡ café{x01}"
    assert msgfile.encode(text) == raw
    missing = set()
    assert msgfile.encode("日", missing=missing) == b"?" and missing == {"日"}


def test_leftovers_are_japanese_only():
    assert msgfile.is_leftover(LEFTOVER)
    assert msgfile.is_leftover("ムーン".encode("utf-16-le"))
    for english in (b"<!STG0_00,GSWF_STARPIECE_03>\nI see...<wait 250>a Star Piece.\n<k>",
                    b"Catch the GLISPO today?\nThey had some hilarious\nheadlines\x01\xff\n<k>",
                    b"<diary>\nMonth \xde Day \xa4\xd8\n<wait 250>", b"Jes\xfas Es<shake>p</shake>\xed Tinoco"):
        assert not msgfile.is_leftover(english)


def test_area_file_blocks_leave_out_leftovers_and_save_exactly():
    rules = load_rules(PLUGIN)
    data = area_file()
    blocks, names = rules.load_data_from_json_obj(data)
    assert names == {"0": "Messages"} and len(blocks[0]) == 3
    assert blocks[0][0] == "Mail call!{wait 250} Hey!\n{k}\n{p}\nIt's {col c00000ff}Mario{/col}!\n{k}"
    assert blocks[0][2] == "{kanban}\n↓ To Petal Meadows ♪\n{k}"
    assert rules.save_data_to_json_obj(blocks, names) == data


def test_ukrainian_is_written_into_font_slots_and_read_back():
    rules = load_rules(PLUGIN)
    source = area_file()
    blocks, names = rules.load_data_from_json_obj(source)
    blocks[0][1] = "{keyxon}\n" + UKRAINIAN + "\n{k}"
    translated = rules.save_data_to_json_obj(blocks, names)
    entry = msgfile.parse(translated)[1]
    assert entry.key == "村長".encode("cp932") and b"?" not in entry.text
    assert msgfile.parse(translated)[2].text == LEFTOVER            # the leftover is kept as it was
    fresh = load_rules(PLUGIN)
    fresh.load_data_from_json_obj(source)
    again, _ = fresh.load_data_from_json_obj(translated)
    # look-alike letters share the Latin glyph and read back as Latin; the others read back as Ukrainian
    shown = again[0][1]
    assert "Ґ" in shown and "ї" in shown and "є" in shown and "’" in shown and "ЩЮЯ" in shown
    fresh.prepare_save_context(SaveContext(existing_versions=lambda: iter([translated, source])))
    assert fresh.save_data_to_json_obj(again, names) == translated


def test_translation_map_covers_the_alphabet_with_distinct_slots():
    mapping = json.loads((PLUGIN_DIR / "translation_map.json").read_text(encoding="utf-8"))
    alphabet = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя’"
    assert set(alphabet) <= set(mapping)
    drawn = {letter: slot for letter, slot in mapping.items() if not slot.isascii() and letter not in "Її’"}
    assert len(set(drawn.values())) == len(drawn) == 44
    assert not set(drawn.values()) & set(msgfile.SYMBOLS.values())
    for slot in mapping.values():
        assert msgfile.encode(slot) != b"?"


def test_global_file_is_grouped_by_kind():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(global_file())
    assert list(names.values()) == ["Names", "Item and badge names", "Enemy names", "Battle tattles",
                                    "Descriptions and menu help", "Other"]
    assert blocks[1] == ["Mushroom"] and blocks[4] == ["A dried mushroom.\nRestores 5 HP.", "Check Mario's stats here."]
    assert rules.save_data_to_json_obj(blocks, names) == global_file()
    with pytest.raises(ValueError):
        rules.save_data_to_json_obj(blocks[:-1], names)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "nok_00.txt").write_bytes(area_file())
    (tmp_path / "global.txt").write_bytes(global_file())
    files = ["nok_00.txt", "global.txt"]
    manager = SimpleNamespace(project=SimpleNamespace(blocks=[SimpleNamespace(source_file=f) for f in files]),
                              project_dir=None, get_absolute_path=lambda rel, is_translation=False: str(tmp_path / rel))
    mw = SimpleNamespace(project_manager=manager, block_to_project_file_map={0: 0, **{i: 1 for i in range(1, 7)}})
    return load_rules(PLUGIN, mw)


def test_speakers_scenes_windows_and_layout(project):
    assert project.get_speaker_for_string(0, 1) == "Goombella"                 # a tattle
    assert project.get_message_attributes(0, 2) == {"file": "nok_00.txt", "key": "stg1_nok_03", "area": "nok",
                                                    "window": "kanban"}
    assert project.get_translation_context_for_string(0, 0)["content_role"] == "Dialogue"
    assert project.get_scene_context_for_string(0, 0)["label"] == "Chapter 1: Petalburg"
    assert project.get_string_layout(0, 0) == {"warn_width": 336, "max_width": 342, "lines_per_page": 3}
    item_name = project.get_string_layout(2, 0)
    assert item_name["max_width"] == LAYOUTS["item_name"][1] and item_name["lines_per_page"] == 1
    assert project.get_speaker_for_string(4, 0) == "Goombella"                 # battle tattle block
    assert project.is_placeholder_speaker("村長") and not project.is_placeholder_speaker("Mario")


def test_glossary_seed_has_party_items_enemies_places(project):
    seed = {(e["term"], e["section"]) for e in project.get_glossary_seed_entries()}
    assert {("Mario", "Party"), ("Mushroom", "Items"), ("Goomba", "Enemies"), ("Rogueport", "Places")} <= seed
    assert ("Professor Frankly", "Characters") in seed


def test_width_counts_scale_icons_and_placeholders(project):
    font = {"a": {"width": 10}, "{X}": {"width": 7}}
    width = project.calculate_string_width_override
    assert width("aa", font) == 20
    assert width("a{scale 0.5}aa", font) == 20
    assert width("{icon PAD_A 0.5 1 0 6}a", font) == 28
    assert width("{ITEM}{X}{k}", font) == 137


# -- the game's own files ------------------------------------------------------

@pytest.mark.skipif(not (MSG / "global.txt").exists(), reason="Paper Mario TTYD not unpacked here")
def test_every_real_file_loads_and_saves_byte_for_byte():
    for path in sorted(MSG.glob("*.txt")):
        data = path.read_bytes()
        rules = load_rules(PLUGIN)
        blocks, names = rules.load_data_from_json_obj(data)
        assert rules.save_data_to_json_obj(blocks, names) == data, path.name


@pytest.mark.skipif(not (MSG / "global.txt").exists(), reason="Paper Mario TTYD not unpacked here")
def test_no_english_message_uses_a_slot_a_ukrainian_letter_takes():
    mapping = json.loads((PLUGIN_DIR / "translation_map.json").read_text(encoding="utf-8"))
    slots = {msgfile.encode(slot)[0] for letter, slot in mapping.items() if not slot.isascii() and letter != "’"}
    used = {(path.name, entry.name) for path in MSG.glob("*.txt") for entry in msgfile.parse(path.read_bytes())
            if not msgfile.is_leftover(entry.text) and slots & set(entry.text)}
    assert not used


@pytest.mark.skipif(not (WORKSPACE / "files" / "f" / "papermarioset_US.bfn").exists(), reason="font not unpacked")
def test_every_slot_is_in_the_font_and_the_font_round_trips(tmp_path):
    from core.bfn_core import BfnCore, char_to_glyph
    from tools.bfn_editor.bfn_engine import extract_bfn_logic, repack_bfn_logic
    path = WORKSPACE / "files" / "f" / "papermarioset_US.bfn"
    font = BfnCore()
    font.load(path.read_bytes())
    codes = set(char_to_glyph(font.map1))
    mapping = json.loads((PLUGIN_DIR / "translation_map.json").read_text(encoding="utf-8"))
    assert all(msgfile.encode(slot)[0] in codes for slot in mapping.values())
    extract_bfn_logic(str(path), str(tmp_path))
    repack_bfn_logic(str(tmp_path), str(tmp_path / "out.bfn"))
    assert (tmp_path / "out.bfn").read_bytes() == path.read_bytes()


def test_context_names_speakers_in_english():
    context = json.loads((PLUGIN_DIR / "context.json").read_text(encoding="utf-8"))
    names = [n for area in context["speakers"].values() for n in area.values()]
    assert len(names) > 3000 and context["speakers"]["aaa"]["pro_01"] == "Luigi"
    assert sum(not n.isascii() for n in names) < 20
    assert {"item", "badge", "key_item"} == set(context["items"].values())
    assert not any(re.search(r"\.\s+[A-Z]", n) or n in ("Mr", "Ms") for n in names if n != "Ms. Mowz")


@pytest.mark.skipif(not (MSG / "global.txt").exists(), reason="Paper Mario TTYD not unpacked here")
def test_every_font_on_the_disc_opens_and_writes_into_the_translation(tmp_path):
    from core.font_formats import sources
    from tools.bfn_editor.bfn_engine import extract_bfn_logic, repack_bfn_logic
    descriptors = json.loads((PLUGIN_DIR / "font_sources.json").read_text(encoding="utf-8"))
    found = sources.resolve(descriptors, {"source_path": str(MSG), "translation_path": str(tmp_path / "files" / "msg" / "US")})
    assert sorted(s.name for s in found) == sorted(p.name for p in (WORKSPACE / "files" / "f").glob("*.bfn"))
    for source in found:
        data = source.read_original()
        folder = tmp_path / source.name
        extract_bfn_logic(source.source_path, str(folder))
        repack_bfn_logic(str(folder), str(folder / "out.bfn"))
        assert (folder / "out.bfn").read_bytes() == data, source.name
        source.write(data)
        assert (tmp_path / "files" / "f" / source.name).read_bytes() == data   # where 2_build picks it up


@pytest.mark.skipif(not (MSG / "global.txt").exists(), reason="Paper Mario TTYD not unpacked here")
def test_texture_list_round_trips_and_an_edit_lands_in_the_translation(tmp_path):
    from PIL import ImageDraw
    from core import texture_formats
    from core.texture_formats import sources
    descriptors = json.loads((PLUGIN_DIR / "texture_sources.json").read_text(encoding="utf-8"))
    trans = tmp_path / "files" / "msg" / "US"
    found = sources.resolve(descriptors, {"source_path": str(MSG), "translation_path": str(trans)})
    assert len(found) >= len(descriptors)
    for path in {s.source_path for s in found}:
        data = Path(path).read_bytes()
        textures = texture_formats.read("tpl", data, {})
        assert texture_formats.write("tpl", data, {i: t.image for i, t in enumerate(textures)}, {}) == data, path
    logo = next(s for s in found if "title logo" in s.label)
    image = logo.read_current().image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 31, 31), fill=(255, 0, 0, 255))
    assert logo.write(image)
    written = tmp_path / "files" / "mariost.tpl"
    assert written.stat().st_size == (WORKSPACE / "files" / "mariost.tpl").stat().st_size
    assert logo.read_current().image.getpixel((8, 8))[:3] == (255, 0, 0)
