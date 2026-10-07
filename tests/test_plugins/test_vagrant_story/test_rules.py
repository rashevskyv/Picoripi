"""Vagrant Story plugin hooks: load/save, the translation copy, layout, context, reference; the real files when present."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.vagrant_story import codec, formats, russian
from plugins.vagrant_story import doc as docs

from .samples import area_file, event_file, item_names, program_file, room_file

WS = Path(r"E:\Emulators\RomHacking\Vagrant Story\PS1")
SOURCE, REFERENCE = WS / "source", WS / "reference" / "RU"
UKRAINIAN = "Ґанок і їжак — «є» п’ять"


def test_plugin_loads_and_validates():
    rules = check_loads("vagrant_story")
    assert rules.get_display_name() == "Vagrant Story"
    assert {".evt", ".mpd", ".bin", ".prg", ".hf0", ".arm", ".znd", ".40"} <= {
        e for f in rules.get_file_formats() for e in f.extensions}
    check_validator("vagrant_story")


def test_samples_round_trip():
    check_round_trip("vagrant_story", event_file(["Don't move, Sydney!"]))
    check_round_trip("vagrant_story", item_names(["Battle Knife", "Dirk"]))


def test_other_files_give_one_empty_block():
    assert load_rules("vagrant_story").load_data_from_json_obj(b"\x01\x02\x03\x04\x05\x06\x07\x08") == ([[]], {})


def test_every_letter_of_the_map_reaches_the_game_and_reads_back():
    rules = load_rules("vagrant_story")
    rules.load_translation_map()
    letters = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
    assert set(letters) <= set(rules.char_codes)
    source = event_file(["Have you found Sydney?"])
    blocks, names = rules.load_data_from_json_obj(source)
    blocks[0][0] = UKRAINIAN + " " + letters
    out = rules.save_data_to_json_obj(blocks, names)
    again, _ = load_rules("vagrant_story").load_data_from_json_obj(out)
    assert again[0][0] == UKRAINIAN.replace("—", "—").replace("«", '"').replace("»", '"').replace("’", "'") + " " + letters


def test_translation_copy_is_read_with_the_source_layout_and_saved_from_the_source():
    rules = load_rules("vagrant_story")
    source = program_file(["Fireball", "Heal Panel"], ["Check the container?", "Yes", "No"])
    blocks, names = rules.load_data_from_json_obj(source)
    blocks[1][0] = "Вогонь"
    out = rules.save_data_to_json_obj(blocks, names)
    fresh = load_rules("vagrant_story")
    fresh.restore_runtime_state(json.loads(json.dumps(rules.export_runtime_state())))
    again, _ = fresh.load_data_from_json_obj(out)
    assert again[1] == ["Вогонь", "Heal Panel"]
    fresh.prepare_save_context(SaveContext(relative_path="SLUS_010.40", existing_versions=lambda: iter([out, source])))
    assert fresh.save_data_to_json_obj(again, names) == out


def test_too_long_text_is_refused_with_the_file_and_group():
    rules = load_rules("vagrant_story")
    source = item_names(["Dirk"])
    blocks, names = rules.load_data_from_json_obj(source)
    blocks[0][0] = "Дуже довга назва предмета"
    rules.prepare_save_context(SaveContext(relative_path="MENU/ITEMNAME.BIN", existing_versions=lambda: iter([source])))
    with pytest.raises(formats.FormatError, match="MENU/ITEMNAME.BIN: Item names"):
        rules.save_data_to_json_obj(blocks, names)


@pytest.fixture
def project(tmp_path):
    files = {"EVENT/0004.EVT": event_file(["Don't move, Sydney!", "Bind your legs\nwith that rope."],
                                          boxes=((13, 3), (14, 4))),
             "MAP/MAP001.MPD": room_file(["Have you found Sydney?"]),
             "MENU/ITEMNAME.BIN": item_names(["Battle Knife", "Dirk"]),
             "SMALL/SCEN001.ARM": area_file([(9, 1, "Entrance to Darkness")]),
             "SLUS_010.40": program_file(["Fireball", "Heal Panel"], ["Check the container?", "Yes", "No"])}
    for rel, data in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(data)
    (tmp_path / "vs_index.json").write_text(json.dumps(
        {"rooms": {"MAP/MAP001.MPD": {"zone": 9, "room_number": 1, "area": "Wine Cellar", "room": "The Gallows"}}}),
        encoding="utf-8")
    rel_paths = list(files)
    block_map = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 4}
    manager = SimpleNamespace(project=SimpleNamespace(blocks=[SimpleNamespace(source_file=f) for f in rel_paths]),
                              project_dir=None,
                              get_absolute_path=lambda rel, is_translation=False: str(tmp_path / rel))
    mw = SimpleNamespace(project_manager=manager, block_to_project_file_map=block_map, font_map={})
    rules = load_rules("vagrant_story", mw)
    for rel in rel_paths:
        rules.load_data_from_json_obj(files[rel])
    return rules


def test_dialog_layout_is_the_balloon_and_widths_use_the_italic_font(project):
    assert project.get_string_layout(0, 0) == {"warn_width": 156, "max_width": 156, "lines_per_page": 3}
    assert project.get_string_layout(0, 1)["max_width"] == 168
    # italic widths come from the project's font file; without one every glyph is 6 pixels
    assert project.calculate_string_width_override("{>12}Bind", {}) == 12 + 4 * 6
    layout = project.get_string_layout(2, 0)
    assert layout["max_width"] == len("Battle Knife") * 6


def test_attributes_context_scene_and_flow(project):
    attributes = project.get_message_attributes(0, 1)
    assert attributes["kind"] == "dialog" and attributes["chars_per_line"] == 14 and attributes["box_lines"] == 4
    assert project.get_message_attributes(2, 1)["bytes_available"] == 23
    assert project.get_translation_context_for_string(0, 0)["content_role"] == "Spoken dialogue"
    assert project.get_translation_context_for_string(5, 0)["content_role"] == "Name in game data"
    scene = project.get_scene_context_for_string(1, 0)
    assert scene["location_candidates"] == ["Wine Cellar -- The Gallows"]
    assert project.get_ai_flow_context_for_string(1, 0) == "Spoken dialogue -- MAP001 (Wine Cellar -- The Gallows)"
    assert project.get_ai_flow_group_for_string(0, 0) != project.get_ai_flow_group_for_string(1, 0)


def test_glossary_seed_has_items_rooms_spells_and_named_characters(project):
    seed = {(e["term"], e["section"]) for e in project.get_glossary_seed_entries()}
    assert ("Battle Knife", "Items") in seed and ("Entrance to Darkness", "Places") in seed
    assert ("Fireball", "Spells and arts") in seed
    assert ("Sydney Losstarot", "Characters") in seed and not any(s == "Characters" and t == "Samantha"
                                                                   for t, s in seed)


def test_russian_reference_is_aligned_by_file_and_place(project, tmp_path):
    ru = tmp_path / "ru"
    ru_event = event_file(["Há c mecta, Cáßhá!", "Cböœá cboá hoÜá\nbepebkoâ."], boxes=((13, 3), (14, 4)))
    (ru / "EVENT").mkdir(parents=True)
    (ru / "EVENT" / "0004.EVT").write_bytes(ru_event)
    (ru / "MENU").mkdir()
    (ru / "MENU" / "ITEMNAME.BIN").write_bytes(item_names(["Kopták", "Kykpá"]))
    reference = project.load_reference_patch(str(ru))
    assert reference[(0, 0)] == "Ни с места, Сидни!"
    assert reference[(0, 1)] == "Свяжи свои ноги\nверевкой."
    assert reference[(2, 0)] == "Кортик" and reference[(2, 1)] == "Кукри"
    assert (1, 0) not in reference                    # no Russian room file


def test_russian_letters_follow_the_fan_font():
    raw = codec.encode("Bï haìäá Cáßhá?")
    assert russian.decode(raw) == "Вы нашли Сидни?"
    assert russian.decode(codec.encode("Gold Key")) == "Gold Key"


# -- the game's own files ------------------------------------------------------

REAL = ["EVENT/0004.EVT", "MAP/MAP001.MPD", "MENU/ITEMNAME.BIN", "MENU/ITEMHELP.BIN", "MENU/MCMAN.BIN",
        "MENU/MENU12.BIN", "MENU/MENU9.PRG", "SMALL/HELP01.HF0", "SMALL/MON.BIN", "SMALL/SCEN001.ARM",
        "MAP/ZONE009.ZND", "BATTLE/BATTLE.PRG", "SLUS_010.40"]
needs_disc = pytest.mark.skipif(not (SOURCE / "SLUS_010.40").exists(), reason="Vagrant Story not unpacked here")


@needs_disc
@pytest.mark.parametrize("rel", REAL)
def test_real_file_round_trips_byte_exact_and_takes_ukrainian(rel):
    data = (SOURCE / rel).read_bytes()
    rules = load_rules("vagrant_story")
    blocks, names = rules.load_data_from_json_obj(data)
    assert sum(map(len, blocks)) > 0
    rules.prepare_save_context(SaveContext(relative_path=rel, existing_versions=lambda: iter([data])))
    assert rules.save_data_to_json_obj(blocks, names) == data
    first = next(i for i, block in enumerate(blocks) if block)
    blocks[first][0] = "Ґава"
    edited = rules.save_data_to_json_obj(blocks, names)
    again, _ = rules.load_data_from_json_obj(edited)
    assert again[first][0] == "Ґава" and again[first][1:] == blocks[first][1:]


@needs_disc
def test_real_text_uses_no_code_the_translation_map_takes():
    """The census behind translation_map.md: no English line of the game uses a reassigned cell."""
    rules = load_rules("vagrant_story")
    rules.load_translation_map()
    taken = {code for letter, code in rules.char_codes.items() if letter.isalpha() and not codec.CHARS[code].isascii()}
    used = {}
    for path in sorted(SOURCE.rglob("*")):
        if not path.is_file() or path.suffix.upper() in (".FNT", ".JSON"):
            continue
        parsed = docs.parse(path.read_bytes())
        for group in parsed.groups:
            for line in group.lines:
                if line.kind == docs.HUD:
                    continue                    # ASCII words of the HUD sheet, not the text font
                for code, param in codec.tokens(line.raw):
                    if param is None and code in taken:
                        used.setdefault(code, path.name)
    assert used == {}, {f"{code:#x}": name for code, name in used.items()}
    assert len(taken) == 46


@needs_disc
def test_real_reference_reads_russian():
    if not (REFERENCE / "MAP" / "MAP001.MPD").exists():
        pytest.skip("Russian reference not unpacked")
    english = docs.parse((SOURCE / "MAP" / "MAP001.MPD").read_bytes())
    ru = (REFERENCE / "MAP" / "MAP001.MPD").read_bytes()
    sections = formats.mpd_header(ru)
    table = formats.read_script(ru, *sections[2]).table
    line = english.groups[0].lines[0]
    assert "Сидни" in russian.decode(table.string_at(ru, line.place)[:-1])
