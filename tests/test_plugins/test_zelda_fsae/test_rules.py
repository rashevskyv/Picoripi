"""Four Swords Anniversary Edition plugin: KMSG load/save, control-code tags, speakers, widths, references; the real
files of the workspace when they are here."""
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.zelda_fsae import kmsg
from plugins.zelda_fsae.tags import TAG_RE, describe, from_editor, to_editor

FSAE = Path(r"E:\Emulators\RomHacking\ZELDA\FSAE_UA")


def _text(*parts) -> bytes:
    return kmsg.encode([*parts, (0,)])


def sample(english_slot=kmsg.EN_EU, cyrillic=False) -> bytes:
    """Five messages; English (EU) and German slots; one German text shared with another message."""
    hello = "Ми прибули." if cyrillic else "We have arrived."
    messages = {
        1: [(7, 1), hello, (1,), (3, 90), (1,), "That is the blade.", (2, 120), (4,)],
        3: ["Ready?", (1,), (6,), "   No", (1,), (6,), "   Yes"],
        201: ["You got the Shield", (11, 2), (8, 11), " !"],
        301: ["I am the Great Fairy of Forest,", (3, 120), (1,), (5, 4)],
        2203: [(17, 3), "Vaati's Palace", (17, 0), " has appeared!"],
    }
    rows = bytearray(struct.pack("<4sIII", b"KMSG", 1, 0, 0))
    file = kmsg.Kmsg(bytes(rows))
    for message_id, parts in messages.items():
        texts = [None] * kmsg.SLOTS
        texts[english_slot] = _text(*parts)
        texts[3] = _text("Gleich" if message_id != 3 else "Bereit?")
        file.ids.append(message_id)
        file.texts.append(texts)
    return file.build()


def test_plugin_loads_and_validates():
    rules = check_loads("zelda_fsae")
    assert rules.get_display_name() == "Zelda: Four Swords Anniversary Edition"
    assert ".kmsg" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator("zelda_fsae")


def test_kmsg_layout_and_shared_texts():
    data = sample()
    file = kmsg.Kmsg(data)
    assert file.ids == [1, 3, 201, 301, 2203]
    german = [struct.unpack_from("<II", data, 16 + 84 * i + 4 + 8 * 3) for i in range(5)]
    assert len({offset for offset, _ in german}) == 2                     # "Gleich" is stored once
    assert kmsg.Kmsg(file.build(share=False)).texts == file.texts
    assert all(offset % 4 == 0 for offset, _ in german)
    with pytest.raises(kmsg.FormatError):
        kmsg.Kmsg(b"KMSX" + data[4:])


def test_control_codes_are_aligned_as_the_game_reads_them():
    assert kmsg.encode(["ab", (1,)]) == b"ab\x7f\x00\x01\x00"              # 0x7F at an even offset: a pad
    assert kmsg.encode(["abc", (1,)]) == b"abc\x7f\x01\x00"                # odd: the code follows at once
    assert kmsg.tokens(b"abc\x7f\x01\x00x\x7f\x00\x00") == ["abc", (1,), "x", (0,)]
    with pytest.raises(kmsg.FormatError):
        kmsg.tokens(b"\x7f\x00\x55\x00")


def test_sample_round_trip_and_unedited_save_is_byte_exact():
    check_round_trip("zelda_fsae", sample())
    rules = load_rules("zelda_fsae")
    blocks, names = rules.load_data_from_json_obj(sample())
    assert [names[str(i)] for i in range(len(blocks))] == [
        "Prologue", "Items", "Great Fairies", "System and menus"]
    assert blocks[0][0] == "[speaker:1]We have arrived.\n[next:90]\nThat is the blade.[wait:120][close]"
    assert blocks[0][1] == "Ready?\n[choice]   No\n[choice]   Yes"
    assert blocks[1][0] == "You got the Shield[space:2][icon:11] !"
    assert rules.save_data_to_json_obj(blocks, names) == sample()


def test_edits_touch_only_the_english_slot():
    rules = load_rules("zelda_fsae")
    blocks, names = rules.load_data_from_json_obj(sample())
    blocks[3][0] = "[color:3]Палац Ваті[color:0] з’явився! Ґ Є І Ї"
    saved = rules.save_data_to_json_obj(blocks, names)
    again = load_rules("zelda_fsae").load_data_from_json_obj(saved)[0]
    assert again == blocks
    assert [t[3] for t in kmsg.Kmsg(saved).texts] == [t[3] for t in kmsg.Kmsg(sample()).texts]


def test_save_builds_on_the_newest_version_that_parses():
    rules = load_rules("zelda_fsae")
    blocks, names = rules.load_data_from_json_obj(sample())
    blocks[1][0] = "Ви отримали Щит[space:2][icon:11] !"
    translated = rules.save_data_to_json_obj(blocks, names)
    rules.reset_runtime_state()
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([b"broken", translated, sample()])))
    blocks[3][0] = "Палац!"
    again = load_rules("zelda_fsae").load_data_from_json_obj(rules.save_data_to_json_obj(blocks, names))[0]
    assert again[1][0].startswith("Ви отримали") and again[3][0] == "Палац!"


def test_other_files_give_one_empty_block():
    assert load_rules("zelda_fsae").load_data_from_json_obj(b"RTFN\xff\xfe") == ([[]], {})


@pytest.mark.parametrize("text", ["a\nb", "[speaker:3]x[next:60]\n\ny[wait:30][close]", "[center][color:4]- A -",
                                  "P[num:0] PAUSE!", "[code13:2,0,0]x", "\n", "", "Ґ’є"])
def test_editor_form_is_reversible(text):
    assert to_editor(from_editor(text)) == text


def test_tags():
    for tag in ("[speaker:1]", "[wait:120]", "[next:90]", "[close]", "[event:4]", "[choice]", "[center]",
                "[icon:14]", "[button:4]", "[num:2]", "[player:0]", "[space:3]", "[color:1]", "[code13:2,0,0]"):
        assert TAG_RE.fullmatch(tag) and describe(tag)
    assert describe("[speaker:3]").endswith("Vaati") and describe("[bogus]") == ""
    manager = load_rules("zelda_fsae").tag_manager
    assert manager.is_tag_legitimate("[icon:3]") and not manager.is_tag_legitimate("[icon]")


# -- hooks that read the project's file ------------------------------------------------------

class _ProjectManager:
    def __init__(self, root: Path):
        self.root = root
        self.project = SimpleNamespace(blocks=[SimpleNamespace(source_file="eu.kmsg")])

    def get_absolute_path(self, rel, is_translation=False):
        return str(self.root / rel)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "eu.kmsg").write_bytes(sample())
    mw = SimpleNamespace(project_manager=_ProjectManager(tmp_path), block_to_project_file_map={i: 0 for i in range(4)},
                         font_map={"V": {"width": 9}, "a": {"width": 7}, " ": {"width": 3}, "!": {"width": 3}})
    return load_rules("zelda_fsae", mw)


def test_speakers_and_context(project):
    assert project.get_speaker_for_string(0, 0) == "Princess Zelda"
    assert project.get_speaker_for_string(0, 1) is None                    # a prologue text without a speaker code
    assert project.get_speaker_for_string(2, 0) == "Great Fairy of Forest"
    assert project.get_speaker_for_string(1, 0) is None                    # item messages are not spoken
    assert project.get_ai_flow_group_for_string(0, 0) == project.get_ai_flow_group_for_string(0, 1) == "fsae:0"
    assert project.get_message_attributes(3, 0) == {"id": 2203, "block": "System and menus"}
    assert project.get_translation_context_for_string(1, 0) == {"content_role": "Item get message",
                                                                 "has_speaker": False}
    assert project.get_scene_context_for_string(2, 0)["candidate_actors"] == ["Great Fairy of Forest"]
    assert project.is_placeholder_speaker("npc:voice") and not project.is_placeholder_speaker("Vaati")


def test_layout_widths_and_glossary(project):
    assert project.get_string_layout(0, 0) == {"warn_width": 225, "max_width": 225, "font_file": "fsae_ltn.json"}
    assert project.get_string_layout(3, 0)["max_width"] == 240
    # V a a: 9 + 7 + 7, a space tag 2, a picture 12, then " !" 3 + 3; the widest line counts
    assert project.calculate_string_width_override("Vaa[space:2][icon:1] !\na", project.mw.font_map) == 43
    seed = {(e["term"], e["section"]) for e in project.get_glossary_seed_entries()}
    assert {("Shield", "Items"), ("Vaati's Palace", "Places"), ("Vaati", "Characters")} <= seed


def test_references_match_by_message_id(project, tmp_path):
    folder = tmp_path / "ru" / "nitrofs"
    folder.mkdir(parents=True)
    (folder / "eu.kmsg").write_bytes(sample(cyrillic=True))
    (folder / "all.kmsg").write_bytes(sample(english_slot=1))
    names = {str(i): "" for i in range(4)}
    languages = project.load_multi_reference(str(tmp_path / "ru"), names)
    assert set(languages) == {"Russian (RU)", "German (DE)", "English (US)"}
    assert languages["Russian (RU)"][(0, 0)].startswith("[speaker:1]Ми прибули.")
    assert languages["German (DE)"][(0, 1)] == "Bereit?"
    assert project.load_reference_patch(str(folder / "eu.kmsg"), names)[(3, 0)].startswith("[color:3]")


# -- the workspace's own files ---------------------------------------------------------------

@pytest.mark.skipif(not (FSAE / "source" / "eu.kmsg").exists(), reason="FSAE_UA workspace not unpacked here")
def test_real_file_round_trips_byte_exact():
    data = (FSAE / "source" / "eu.kmsg").read_bytes()
    rules = load_rules("zelda_fsae")
    blocks, names = rules.load_data_from_json_obj(data)
    assert sum(map(len, blocks)) == 220 and len(blocks) == 9
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][0] = "[speaker:1]Ми прибули. Ґанок, їжак, Єва, м’ята.[wait:120][close]"
    edited = rules.save_data_to_json_obj(blocks, names)
    assert load_rules("zelda_fsae").load_data_from_json_obj(edited)[0] == blocks


@pytest.mark.skipif(not (FSAE / "RU" / "nitrofs" / "all.kmsg").exists(), reason="FSAE_UA workspace not unpacked here")
def test_real_all_kmsg_layout_and_every_western_text_round_trip():
    data = (FSAE / "RU" / "nitrofs" / "all.kmsg").read_bytes()
    file = kmsg.Kmsg(data)
    assert file.build(share=False) == data                                # the game's own layout, byte for byte
    for texts in file.texts:
        for raw in texts[1:]:
            if raw:
                assert from_editor(to_editor(raw)) == raw
