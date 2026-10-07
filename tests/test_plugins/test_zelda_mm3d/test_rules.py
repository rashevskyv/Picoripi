"""Majora's Mask 3D plugin: GMSG load/save, control-code tags, references; the real files of the workspace when
they are here."""
import struct
from pathlib import Path

import pytest

from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.zelda_mm3d import gmsg
from plugins.zelda_mm3d.rules import split_blocks

MM3D = Path(r"E:\Emulators\RomHacking\Zelda\Majoras Mask\3D - 3DS")
ENGLISH = {
    0x0002: "{quicktext-on}You got a {color:blue}Blue Rupee{color:default}!{quicktext-off}\n{delay:10}Worth 5.{flow:wait}",
    0x0100: "{sfx:0x01006858}Look, {name}!{flow:continue}{box-break}\nNext box {btn:A}.{event:1}",
    0x571C: "{center}New Game",
    0x5780: "st",
    0x6018: "You have {plural:0x0007}one fairy{plural-else}fairies{plural-end}.",
}


def sample(english=None) -> bytes:
    english = english or ENGLISH
    file = gmsg.Gmsg(gmsg.HEADER.pack(b"GMSG", 1, 0, 0x10))
    for message_id, text in english.items():
        file.entries.append(gmsg.ENTRY.pack(message_id, 0xFFFF, 0x3FFFFFFF, 0x20, 0x01, 0xFF, 0, 0, 0))
        file.ids.append(message_id)
        file.texts.append(gmsg.from_editor(text))
    data = bytearray(file.build())
    struct.pack_into("<I", data, 8, len(english))
    return bytes(data)


def test_plugin_loads_and_validates():
    rules = check_loads("zelda_mm3d")
    assert rules.get_display_name() == "Zelda: Majora's Mask 3D"
    assert ".gmsg" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator("zelda_mm3d")


def test_gmsg_layout():
    data = sample()
    file = gmsg.Gmsg(data)
    assert file.ids == list(ENGLISH) and file.build() == data
    assert file.attributes(1) == {"message_id": 0x0100, "next_id": 0xFFFF, "textbox_type": 0x20,
                                  "textbox_position": 1, "item_icon": 0xFF}
    first = struct.unpack_from("<I", data, 16 + 12)[0]
    assert first == 16 + 5 * 20 and all(struct.unpack_from("<I", data, 16 + 20 * i + 12)[0] % 4 == 0 for i in range(5))
    with pytest.raises(gmsg.FormatError):
        gmsg.Gmsg(b"GMSX" + data[4:])


def test_control_codes_are_aligned_like_the_game():
    raw = gmsg.from_editor("a{color:red}b\n{sfx:0x01000001}")
    # 'a' 7F 3A00 0100 'b' 7F 0100, then 7F [00] (the code would start at an odd offset) 3200 [0000] (u32 aligned)
    # 01000001, then the end code 7F [00] 0000
    assert raw == (b"a\x7f\x3a\x00\x01\x00b\x7f\x01\x00\x7f\x00\x32\x00\x00\x00\x01\x00\x00\x01"
                   b"\x7f\x00\x00\x00")


def test_sample_round_trip_and_unedited_save_is_byte_exact():
    check_round_trip("zelda_mm3d", sample())
    rules = load_rules("zelda_mm3d")
    blocks, names = rules.load_data_from_json_obj(sample())
    assert [names[str(i)] for i in range(len(blocks))] == [
        "Items received", "Messages 0x0100", "File select and system", "Ordinal suffixes", "Objectives"]
    assert blocks[1][0] == ENGLISH[0x0100]
    assert rules.save_data_to_json_obj(blocks, names) == sample()


def test_edits_follow_block_names():
    rules = load_rules("zelda_mm3d")
    blocks, names = rules.load_data_from_json_obj(sample())
    order = [2, 0]       # a project of one block per range saves the blocks of the file in its own order
    data = [list(blocks[i]) for i in order]
    data[0][0] = "{center}Нова гра: Ґ Є І Ї, м’ята"
    saved = rules.save_data_to_json_obj(data, {str(n): names[str(i)] for n, i in enumerate(order)})
    again = load_rules("zelda_mm3d").load_data_from_json_obj(saved)[0]
    assert again[2] == data[0] and again[:2] == blocks[:2] and again[3:] == blocks[3:]


def test_save_builds_on_the_newest_version_that_parses():
    rules = load_rules("zelda_mm3d")
    blocks, names = rules.load_data_from_json_obj(sample())
    blocks[0][0] = "Ти отримав {color:blue}Синю Рупію{color:default}!"
    translated = rules.save_data_to_json_obj(blocks, names)
    rules.reset_runtime_state()
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([b"broken", translated, sample()])))
    blocks[2][0] = "Нова гра"
    again = load_rules("zelda_mm3d").load_data_from_json_obj(rules.save_data_to_json_obj(blocks, names))[0]
    assert again[0][0].startswith("Ти отримав") and again[2][0] == "Нова гра"


@pytest.mark.parametrize("text", ["a\nb", "{box-break}\nx", "{delay:32778}", "{sfx:0x01000976}", "{choices:3}",
                                  "{btn:A}{btn:24}", "{color:0}{color:default}", "{plural:0x2100}a{plural-else}bc{plural-end}",
                                  "{xpos:16}{indent}{right}", "{ordinal:0x8009}", "", "\n", "Ґ’є ©"])
def test_editor_form_is_reversible(text):
    assert gmsg.to_editor(gmsg.from_editor(text)) == text


def test_bad_tags_are_refused_and_tags_described():
    for bad in ("{bogus}", "{color}", "{name:3}", "{color:purple}", "a { b"):
        with pytest.raises(gmsg.FormatError):
            gmsg.from_editor(bad)
    with pytest.raises(gmsg.FormatError):
        gmsg.to_editor(b"\x7f\x00\x1a\x00\x7f\x00\x00\x00")         # code 0x1A: size unknown
    assert gmsg.describe("{color:red}") == "Text colour: red" and gmsg.describe("not a tag") == ""
    manager = load_rules("zelda_mm3d").tag_manager
    assert manager.is_tag_legitimate("{btn:3}") and not manager.is_tag_legitimate("[icon]")


def test_references_are_matched_by_message_id(tmp_path, monkeypatch):
    rules = load_rules("zelda_mm3d")
    blocks, names = rules.load_data_from_json_obj(sample())
    ids = gmsg.Gmsg(sample()).ids
    monkeypatch.setattr(rules, "_locate", lambda b: (gmsg.Gmsg(sample()), split_blocks(ids)[b]))
    folder = tmp_path / "romfs" / "message" / "eu"
    folder.mkdir(parents=True)
    (folder / "eue.gmsg").write_bytes(sample({0x571C: "{center}Новая игра", 0x0002: "Синяя рупия"}))
    (folder / "euf.gmsg").write_bytes(sample({0x571C: "{center}Nouvelle partie"}))
    found = rules.load_multi_reference(str(tmp_path), names)
    assert found["Russian (RU)"] == {(2, 0): "{center}Новая игра", (0, 0): "Синяя рупия"}
    assert found["French (FR)"] == {(2, 0): "{center}Nouvelle partie"}
    assert rules.load_reference_patch(str(folder / "eue.gmsg"), names) == found["Russian (RU)"]


# -- the real game files ----------------------------------------------------------------------------


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} is not on this machine")
    return path


def test_every_language_of_the_game_round_trips_byte_exact():
    folder = _need(MM3D / "romfs" / "message" / "eu")
    for path in sorted(folder.glob("eu?.gmsg")):
        data = path.read_bytes()
        file = gmsg.Gmsg(data)
        assert file.build() == data, path.name
        assert all(gmsg.from_editor(gmsg.to_editor(t)) == t for t in file.texts if t), path.name


def test_the_game_file_loads_and_saves_unedited_byte_exact():
    data = _need(MM3D / "source" / "romfs" / "message" / "eu" / "eue.gmsg").read_bytes()
    rules = load_rules("zelda_mm3d")
    blocks, names = rules.load_data_from_json_obj(data)
    assert sum(len(b) for b in blocks) == 6152 and len(blocks) == 17
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[10][0] = "{center}UA TEST"
    edited = rules.save_data_to_json_obj(blocks, names)
    again = gmsg.Gmsg(edited)
    assert gmsg.to_editor(again.texts[again.ids.index(0x571C)]) == "{center}UA TEST"
    assert [t for i, t in zip(again.ids, again.texts) if i != 0x571C] == \
        [t for i, t in zip(gmsg.Gmsg(data).ids, gmsg.Gmsg(data).texts) if i != 0x571C]


def test_the_imported_ukrainian_translation_loads():
    data = _need(MM3D / "translation" / "romfs" / "message" / "eu" / "eue.gmsg").read_bytes()
    blocks, _names = load_rules("zelda_mm3d").load_data_from_json_obj(data)
    assert sum(len(b) for b in blocks) == 6152
    assert sum(1 for b in blocks for t in b if any("а" <= ch <= "я" for ch in t)) > 6000
