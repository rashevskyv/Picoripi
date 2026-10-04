"""Age of Calamity plugin hooks: load/save, save context, speakers, attributes, glossary, layout; real files."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.zelda_aoc.aoctext import TextBundle

from .test_formats import bundle, sample_battle, sample_text, table

SOURCE = Path(r"E:\Emulators\RomHacking\ZELDA\HWAOC_UA\source")


def test_plugin_loads_and_validates():
    rules = check_loads("zelda_aoc")
    assert rules.get_display_name() == "Zelda: Hyrule Warriors Age of Calamity"
    assert {".bin"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    assert {s["format"] for s in rules.get_font_sources()} == {"g1n"}
    check_validator("zelda_aoc")


def test_sample_round_trip():
    check_round_trip("zelda_aoc", sample_text())
    check_round_trip("zelda_aoc", sample_battle())


def test_other_binary_files_give_one_empty_block():
    assert load_rules("zelda_aoc").load_data_from_json_obj(b"\x01\x02\x03") == ([[]], {})


def test_save_builds_on_the_newest_version_that_parses():
    rules = load_rules("zelda_aoc")
    source = sample_text()
    blocks, _names = rules.load_data_from_json_obj(source)
    blocks[0][0] = "Гілка"
    translated = rules.save_data_to_json_obj(blocks, {})
    rules.reset_runtime_state()
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([b"broken", translated, source])))
    blocks[0][1] = "Опис"
    again = load_rules("zelda_aoc").load_data_from_json_obj(rules.save_data_to_json_obj(blocks, {}))[0]
    assert again[0][:2] == ["Гілка", "Опис"]


# -- hooks that read the project's files --------------------------------------

class _ProjectManager:
    def __init__(self, root: Path, files):
        self.root = root
        self.project = SimpleNamespace(blocks=[SimpleNamespace(source_file=f) for f in files])

    def get_absolute_path(self, rel, is_translation=False):
        return str(self.root / rel)


def _names() -> bytes:
    rows = [[""]] + [[f"[cs][es]1_1_1______{n}[cm][es]5_5_1______{n}s[ce]"] for n in
                     ("Link", "Zelda", "King Rhoam", "Mipha")] + [["Hylian"]] * 20
    en = table(rows)
    return bundle([en] * 12, key=0x3000)


@pytest.fixture
def project(tmp_path):
    files = {"text/04051_names.bin": _names(), "battle/battle_018.bin": sample_battle(),
             "text/07549_weapons.bin": sample_text(),
             "text/07404_subtitles.bin": bundle([table([[""]] * 40 + [["I must protect...everyone!"]])] * 12, 0x4000),
             "text/04027_memories.bin": bundle([table([[""], ["Across Time"], ["King on the Eve of Battle"]])] * 12, 0x5000)}
    for rel, data in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(data)
    mw = SimpleNamespace(project_manager=_ProjectManager(tmp_path, list(files)),
                         block_to_project_file_map={0: 0, 1: 1, 2: 2, 3: 3, 4: 4},
                         font_map={"T": {"width": 20}, "r": {"width": 10}, "e": {"width": 12}})
    return load_rules("zelda_aoc", mw)


def test_battle_speakers_come_from_the_names_table(project):
    assert project.get_speaker_for_string(1, 0) == "Zelda"           # speaker id 2
    assert project.get_speaker_for_string(1, 1) == "chara_070"       # a soldier id that is not tied to a name
    assert project.is_placeholder_speaker("chara_070") and not project.is_placeholder_speaker("Zelda")
    assert project.get_speaker_for_string(2, 0) is None              # not a dialogue table
    attributes = project.get_message_attributes(1, 0)
    assert (attributes["speaker_id"], attributes["seconds"], attributes["languages"]) == (2, 26.5, 13)


def test_context_scene_and_glossary_seed(project):
    assert project.get_translation_context_for_string(1, 0)["content_role"] == "Battle dialogue"
    names = project.get_translation_context_for_string(0, 0)
    assert names["content_role"] == "Name forms" and names["glossary_section"] == "Characters"
    assert project.get_translation_context_for_string(2, 1)["content_role"] == "Description"
    assert project.get_message_attributes(3, 0)["scene"] == 1
    assert project.get_ai_flow_context_for_string(3, 0).endswith('cutscene 1 "King on the Eve of Battle"')
    seed = project.get_glossary_seed_entries()
    terms = [(e["term"], e["section"]) for e in seed]
    assert ("Link", "Characters") in terms and ("Tree Branch", "Items") in terms
    assert len([t for t, _s in terms if t == "Hylian"]) == 1


def test_string_layout_is_the_widest_english_line_of_the_table(project):
    layout = project.get_string_layout(2, 0)
    assert layout["warn_width"] > 0 and layout["max_width"] == round(layout["warn_width"] * 1.05)
    assert project.calculate_string_width_override("[v]Tree[/]%s", project.mw.font_map) == 20 + 10 + 12 + 12


# -- the game's own files ------------------------------------------------------

REAL = sorted(SOURCE.glob("*/*.bin")) if SOURCE.is_dir() else []


@pytest.mark.skipif(not REAL, reason="Age of Calamity source\\ not unpacked here")
def test_every_real_bundle_round_trips_and_takes_an_edit():
    rules = load_rules("zelda_aoc")
    total = 0
    for path in REAL:
        data = path.read_bytes()
        blocks, names = rules.load_data_from_json_obj(data)
        assert rules.save_data_to_json_obj(blocks, names) == data, path.name
        total += len(blocks[0])
    assert total > 18000
    data = (SOURCE / "text" / "07495_results.bin").read_bytes()
    blocks, names = rules.load_data_from_json_obj(data)
    blocks[0][0] = "Ґанон і Гайрул — «їжак» [cdb]"
    edited = rules.save_data_to_json_obj(blocks, names)
    assert load_rules("zelda_aoc").load_data_from_json_obj(edited)[0] == blocks
    assert TextBundle(edited).slots[1:] == TextBundle(data).slots[1:]          # other languages untouched
