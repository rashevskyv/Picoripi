"""Twin Snakes plugin hooks: load/save, the translation copy, speakers, context; the real files when present."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.formats import SaveContext
from plugins.mgs_ts import doc as docs
from plugins.mgs_ts import gcx, subtitles
from plugins.mgs_ts.rules import CODEC_TEXT_WIDTH, SCRIPT_NEIGHBOURS
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

from .samples import codec_file, gcx_file, subs_file

TEXT = Path(r"E:\Emulators\RomHacking\TWIN_SNAKES\source\text")
UKRAINIAN = "Ґанок і їжак — «є» п’ять"


def test_plugin_loads_and_validates():
    rules = check_loads("mgs_ts")
    assert rules.get_display_name() == "Metal Gear Solid: The Twin Snakes"
    assert {".dat", ".gcx", ".subs"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator("mgs_ts")


def test_samples_round_trip():
    check_round_trip("mgs_ts", codec_file())
    check_round_trip("mgs_ts", subs_file())


def test_other_files_give_one_empty_block():
    assert load_rules("mgs_ts").load_data_from_json_obj(b"\x01\x02\x03\x04\x05\x06\x07\x08") == ([[]], {})


def test_codec_blocks_are_the_english_lines_of_each_distinct_table():
    rules = load_rules("mgs_ts")
    data = codec_file()
    blocks, names = rules.load_data_from_json_obj(data)
    assert len(blocks) == 2 and names == {"0": "Codec 000", "1": "Codec 001"}
    assert blocks[0] == ["Snake, you have to find the chief.\n", "What is that?\n", "The base is on the island.\n"]
    assert rules.save_data_to_json_obj(blocks, names) == data


def test_translation_copy_reads_with_the_source_layout_and_every_copy_is_written():
    rules = load_rules("mgs_ts")
    source = codec_file()
    blocks, names = rules.load_data_from_json_obj(source)
    blocks[0][1] = UKRAINIAN + "\n"
    translated = rules.save_data_to_json_obj(blocks, names)
    assert len(translated) == len(source)
    sections = gcx.read_sections(translated, segment=False)
    assert sections[0].table.strings[1] == sections[2].table.strings[1] != gcx.read_sections(source)[0].table.strings[1]
    # a fresh session: the source is read first, then the translation copy
    fresh = load_rules("mgs_ts")
    fresh.load_data_from_json_obj(source)
    again, _ = fresh.load_data_from_json_obj(translated)
    assert again[0][1] == UKRAINIAN + "\n" and again[1] == blocks[1]
    # saving again is built from the source, the last version the save context offers
    fresh.prepare_save_context(SaveContext(existing_versions=lambda: iter([translated, source])))
    assert fresh.save_data_to_json_obj(again, names) == translated


def test_subtitle_blocks_and_save():
    rules = load_rules("mgs_ts")
    data = subs_file()
    blocks, names = rules.load_data_from_json_obj(data)
    assert names == {"0": "Cutscene 001", "1": "Cutscene 002"}
    assert blocks[0] == ["It's been a long time, Snake.", "I should have known\nit was you."]
    blocks[0][1] = "Я мав знати,\nщо це ти."
    out = rules.save_data_to_json_obj(blocks, names)
    record = subtitles.read(out)[0]
    assert record.entries[1].text.count(b"\x80|") == 1        # a subtitle keeps its own line break
    assert load_rules("mgs_ts").load_data_from_json_obj(out)[0][0][1] == "Я мав знати,\nщо це ти."


@pytest.fixture
def project(tmp_path):
    (tmp_path / "common").mkdir()
    (tmp_path / "common" / "codec.dat").write_bytes(codec_file())
    (tmp_path / "disc1").mkdir()
    (tmp_path / "disc1" / "demo.subs").write_bytes(subs_file())
    (tmp_path / "stage").mkdir()
    item = [b"SOCOM\n.45 handgun.\nPress A to aim.", b"Ration\nRestores life.\nEat it."]
    (tmp_path / "stage" / "r_cmmn.gcx").write_bytes(gcx_file(item))
    files = ["common/codec.dat", "disc1/demo.subs", "stage/r_cmmn.gcx"]
    manager = SimpleNamespace(project=SimpleNamespace(blocks=[SimpleNamespace(source_file=f) for f in files]),
                              project_dir=None, get_absolute_path=lambda rel, is_translation=False: str(tmp_path / rel))
    mw = SimpleNamespace(project_manager=manager, block_to_project_file_map={0: 0, 1: 0, 2: 1, 3: 1, 4: 2},
                         font_map={"S": {"width": 13}, "n": {"width": 10}})
    return load_rules("mgs_ts", mw)


def test_speakers_scenes_and_context(project):
    assert project.get_speaker_for_string(0, 0) == "Roy Campbell"
    assert project.get_speaker_for_string(0, 1) == "Snake"
    assert project.get_speaker_for_string(1, 0) == "Naomi Hunter"
    assert project.get_speaker_for_string(3, 0) == "Genome Soldier"
    assert project.get_speaker_for_string(2, 0) is None
    assert project.is_placeholder_speaker("speaker 1932cc") and not project.is_placeholder_speaker("Otacon")
    assert project.get_translation_context_for_string(0, 0)["content_role"] == "Codec conversation"
    assert project.get_translation_context_for_string(2, 0)["content_role"] == "Cutscene subtitle"
    assert project.get_scene_context_for_string(2, 0)["label"] == "Cutscene 001"
    assert project.get_message_attributes(2, 1)["start"] == 100
    assert project.get_ai_flow_group_for_string(0, 0) != project.get_ai_flow_group_for_string(1, 0)


def test_glossary_seed_has_characters_and_items(project):
    seed = {(e["term"], e["section"]) for e in project.get_glossary_seed_entries()}
    assert ("Roy Campbell", "Characters") in seed and ("SOCOM", "Items") in seed and ("Ration", "Items") in seed


def test_string_layout_and_width(project):
    assert project.calculate_string_width_override("Sn{x02}", project.mw.font_map) == 23
    # the codec box is a measured width, whatever the English lines are
    assert project.get_string_layout(0, 0) == {"warn_width": CODEC_TEXT_WIDTH, "max_width": CODEC_TEXT_WIDTH}
    layout = project.get_string_layout(2, 0)
    assert layout["warn_width"] > 0 and layout["max_width"] >= layout["warn_width"]


def test_script_width_comes_from_the_neighbouring_strings(tmp_path):
    """A script table mixes windows: item descriptions must not get the width of a far wide dialog."""
    narrow = [b"Ration\nYou eat the ration.\nIt is the food."] * 3
    filler = [b"It is the one you have to find."] * (SCRIPT_NEIGHBOURS + 1)
    wide = [b"This is the very long line of the memory card dialog that you see and read"]
    (tmp_path / "s.gcx").write_bytes(gcx_file(narrow + filler + wide))
    manager = SimpleNamespace(project=SimpleNamespace(blocks=[SimpleNamespace(source_file="s.gcx")]),
                              project_dir=None, get_absolute_path=lambda rel, is_translation=False: str(tmp_path / rel))
    rules = load_rules("mgs_ts", SimpleNamespace(project_manager=manager, block_to_project_file_map={0: 0},
                                                 font_map={"~": {"width": 1}}))
    width = lambda text: rules.calculate_string_width_override(text, {})  # noqa: E731
    first = rules.get_string_layout(0, 0)
    assert first == {"warn_width": width("It is the one you have to find."),
                     "max_width": width("It is the one you have to find.")}
    last = rules.get_string_layout(0, len(narrow + filler))
    assert last["max_width"] == width(wide[0].decode())


# -- the game's own files ------------------------------------------------------

REAL = ["common/codec.dat", "common/vox.subs", "common/movie.subs", "disc1/demo.subs", "disc2/demo.subs",
        "stage/n_title.gcx", "stage/r_cmmn.gcx", "stage/ending.gcx"]


@pytest.mark.skipif(not (TEXT / "common" / "codec.dat").exists(), reason="Twin Snakes text not unpacked here")
@pytest.mark.parametrize("rel", REAL)
def test_real_file_round_trips_byte_exact_and_takes_ukrainian(rel):
    data = (TEXT / rel).read_bytes()
    rules = load_rules("mgs_ts")
    blocks, names = rules.load_data_from_json_obj(data)
    assert sum(map(len, blocks)) > 0
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][0] = UKRAINIAN
    edited = rules.save_data_to_json_obj(blocks, names)
    assert len(edited) == len(data) or rel.endswith(".subs")
    again, _ = rules.load_data_from_json_obj(edited)
    assert again[0][0] == UKRAINIAN and again[1:] == blocks[1:]


@pytest.mark.skipif(not (TEXT / "common" / "codec.dat").exists(), reason="Twin Snakes text not unpacked here")
def test_real_codec_lines_have_speakers():
    parsed = docs.parse((TEXT / "common" / "codec.dat").read_bytes())
    lines = [line for block in parsed.blocks for line in block]
    assert len(lines) > 8000
    assert sum(1 for line in lines if line.speaker) > 0.99 * len(lines)
