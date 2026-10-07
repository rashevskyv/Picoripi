"""Hyrule Warriors DE plugin hooks: load/save, save context, speakers, attributes, layout; real files."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.zelda_hwde import ktbin
from plugins.zelda_hwde.textfile import LANGUAGES, TextFile

from .test_formats import sample_file, xl

ROMFS = Path(r"E:\Emulators\RomHacking\Zelda\Hyrule Warriors DE\Switch\romfs\data")
REAL_FILES = (
    "common/msgdata.bin", "common/MovieSubtitle.bin", "common/VoiceMes.bin", "common/VoiceMesChange.bin",
    "event/EventSubtitle.bin", "intermission/IMSubtitle.bin", "battle/btlmessage.bin",
    "battle/scenario/snstr000.bin", "battle/scenario/snstrADV000.bin", "battle/scenario/snstrSTG000.bin",
)


def test_plugin_loads_and_validates():
    rules = check_loads("zelda_hwde")
    assert rules.get_display_name() == "Zelda: Hyrule Warriors Definitive Edition"
    assert {".bin"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator("zelda_hwde")


def test_sample_round_trip():
    check_round_trip("zelda_hwde", sample_file())


def test_other_binary_files_give_one_empty_block():
    rules = load_rules("zelda_hwde")
    assert rules.load_data_from_json_obj(b"\x01\x02\x03") == ([[]], {})


def test_save_builds_on_the_newest_version_that_parses():
    rules = load_rules("zelda_hwde")
    source = sample_file()
    blocks, _names = rules.load_data_from_json_obj(source)
    blocks[0][0] = "Здолай!"
    translated = rules.save_data_to_json_obj(blocks, {})
    rules.reset_runtime_state()
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([b"broken", translated, source])))
    blocks[2][0] = "Пан Фея"
    again = load_rules("zelda_hwde").load_data_from_json_obj(rules.save_data_to_json_obj(blocks, {}))[0]
    assert again[0][0] == "Здолай!" and again[2][0] == "Пан Фея"


# -- hooks that read the project's files --------------------------------------

class _ProjectManager:
    def __init__(self, root: Path, files):
        self.root = root
        self.project = SimpleNamespace(blocks=[SimpleNamespace(source_file=f) for f in files])

    def get_absolute_path(self, rel, is_translation=False):
        return str(self.root / rel)


def _msgdata() -> bytes:
    names = xl([0] * 8, [[n.encode() + b"\0"] * 8 for n in ("Link", "Zelda", "Sheik")])
    plain = xl([0], [[b"Menu\0"]])
    section = ktbin.build_container([plain] * 6 + [names])
    return ktbin.build_container([section] * len(LANGUAGES))


def _voice_mes() -> bytes:
    lines = xl([1, 0], [[-1, b"Good work, Link!\0"], [-1, b"\0"], [-1, b"Leave it to me!\0"]])
    return ktbin.build_container([lines] * len(LANGUAGES))


@pytest.fixture
def project(tmp_path):
    common = tmp_path / "data" / "common"
    common.mkdir(parents=True)
    (common / "msgdata.bin").write_bytes(_msgdata())
    (common / "VoiceMes.bin").write_bytes(_voice_mes())
    (common / "VoiceInf.bin.gz").write_bytes(xl([2, 3, 3], [[0, 3, 0], [-1, 0, 0], [20, 0, 0]]))
    subtitles = xl([2, 2, 2, 2, 2, 0], [[3, 0, 10, 20, 0, b"Who are you?\0"], [3, 1, 30, 40, 0, b"Nobody.\0"],
                                         [3, 2, 10, 20, 8, b"Impa\0"]])
    (tmp_path / "data" / "event").mkdir()
    (tmp_path / "data" / "event" / "EventSubtitle.bin").write_bytes(ktbin.build_container([subtitles] * 12))
    files = ["data/common/msgdata.bin", "data/common/VoiceMes.bin", "data/event/EventSubtitle.bin"]
    # data blocks: msgdata has 7 tables (0..6), VoiceMes one -> data block 7, EventSubtitle -> 8
    block_map = {i: 0 for i in range(7)}
    block_map[7] = 1
    block_map[8] = 2
    mw = SimpleNamespace(project_manager=_ProjectManager(tmp_path, files), block_to_project_file_map=block_map,
                         font_map={"L": {"width": 10}, "i": {"width": 5}, "n": {"width": 10}, "k": {"width": 10}})
    return load_rules("zelda_hwde", mw)


def test_speakers_come_from_voice_info_and_the_names_table(project):
    assert project.get_speaker_for_string(7, 0) == "Link"
    assert project.get_speaker_for_string(7, 1) == "chara_020"      # id outside the verified range
    assert project.is_placeholder_speaker("chara_020") and not project.is_placeholder_speaker("Link")
    assert project.get_speaker_for_string(6, 0) is None              # not a voice file


def test_speakers_of_every_line_parse_each_file_once_and_never_rebuild(project, monkeypatch):
    """Opening a project asks the speaker of every line: each file is parsed once, nothing is rebuilt."""
    parse, build = ktbin.parse_xl, ktbin.build_xl
    parsed, built = [], []
    monkeypatch.setattr(ktbin, "parse_xl", lambda data: parsed.append(1) or parse(data))
    monkeypatch.setattr(ktbin, "build_xl", lambda table: built.append(1) or build(table))
    for _round in range(2):
        speakers = [project.get_speaker_for_string(b, s) for b in range(9) for s in range(12)]
    assert "Link" in speakers and "Impa" in speakers
    # msgdata: English only (7 tables, no speakers there; its names table is English too); VoiceMes: all 12
    # languages; EventSubtitle: English to find the subtitles, then all 12; VoiceInf: one table
    assert len(parsed) == 7 + 12 + (1 + 12) + 1
    assert built == []


def test_subtitle_speaker_is_the_name_row_with_the_same_timing(project):
    assert project.get_speaker_for_string(8, 0) == "Impa"
    assert project.get_speaker_for_string(8, 1) is None              # no name row for 30..40
    assert project.get_message_attributes(8, 2)["speaker_label"] is True
    assert project.get_translation_context_for_string(8, 2)["content_role"] == "Speaker name"
    assert project.is_placeholder_speaker("???")


def test_attributes_context_and_glossary_seed(project):
    attributes = project.get_message_attributes(6, 9)
    assert attributes["file"] == "data/common/msgdata.bin"
    assert (attributes["table"], attributes["row"], attributes["form"]) == (6, 1, 1)
    context = project.get_translation_context_for_string(6, 9)
    assert context["content_role"] == "Names (forms)" and "form 1" in context["role_instruction"]
    assert project.get_scene_context_for_string(7, 0)["resource"] == "data/common/VoiceMes.bin"
    seed = project.get_glossary_seed_entries()
    assert [e["term"] for e in seed] == ["Link", "Zelda", "Sheik"]


def test_string_layout_is_the_widest_english_line_of_the_table(project):
    # "Zelda": no glyph in the map, 5 x 26 -- wider than "Link" (35) and "Sheik" (93)
    assert project.get_string_layout(6, 0) == {"warn_width": 130, "max_width": 136}
    assert project.calculate_string_width_override("{c:0}Link%1s", project.mw.font_map) == 35


# -- the game's own files ------------------------------------------------------

@pytest.mark.skipif(not (ROMFS / "common/msgdata.bin").exists(), reason="Hyrule Warriors DE romfs not extracted here")
@pytest.mark.parametrize("rel", REAL_FILES)
def test_real_file_round_trips_byte_exact(rel):
    data = (ROMFS / rel).read_bytes()
    rules = load_rules("zelda_hwde")
    blocks, names = rules.load_data_from_json_obj(data)
    assert sum(map(len, blocks)) > 0 and len(names) == len(blocks)
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][0] = "Ґанон і Гайрул — «їжак»"
    rules.load_data_from_json_obj(data)
    edited = rules.save_data_to_json_obj(blocks, names)
    again, _ = load_rules("zelda_hwde").load_data_from_json_obj(edited)
    assert again == blocks
    original = TextFile(data)
    assert [s for i, s in enumerate(TextFile(edited).tree) if i not in (1, 6)] == \
        [s for i, s in enumerate(original.tree) if i not in (1, 6)]      # other languages untouched
