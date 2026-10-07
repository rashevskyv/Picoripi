"""Ocarina of Time 3D plugin: QM load/save, control-code tags, keyboards, the default name, references; the real
files of the workspace when they are here."""
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.zelda_oot3d import qm
from plugins.zelda_oot3d.rules import CODE_BIN, read_name, write_name

OOT3D = Path(r"E:\Emulators\RomHacking\Zelda\Ocarina of Time\3D - 3DS")


def _text(text: str) -> bytes:
    return qm.from_editor(text)


def sample(english=None, german=True) -> bytes:
    """Five messages in four id ranges; English and German slots."""
    english = english or {
        0x0001: "{unskippable}{item-icon:45}You borrowed a {color:red}Pocket Egg{color:default}!",
        0x0100: "{color:light-blue}Look, {name}!{box-break}\nNext box.",
        0x0950: "{quicktext-on}{center}Please select a file.{quicktext-off}",
        0x095D: "File 1\n\n{two-choice}{color:green}Yes\nNo{color:default}",
        0x8100: "{quicktext-on}Hyrule{quicktext-off}",
    }
    file = qm.Qm(struct.pack("<4sIII", b"QM\0\0", 4, 0, 0))
    for message_id, text in english.items():
        file.entries.append(struct.pack("<IIII", message_id, 0, 2, 3) + bytes(0x50))
        file.ids.append(message_id)
        texts = [None] * qm.SLOTS
        texts[qm.ENGLISH] = _text(text)
        if german:
            texts[1] = _text("Hallo")
        file.texts.append(texts)
    data = bytearray(file.build())
    struct.pack_into("<I", data, 8, len(english))
    return bytes(data)


def test_plugin_loads_and_validates():
    rules = check_loads("zelda_oot3d")
    assert rules.get_display_name() == "Zelda: Ocarina of Time 3D"
    assert {".qm", ".list", ".bin"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator("zelda_oot3d")


def test_qm_layout():
    data = sample()
    file = qm.Qm(data)
    assert file.ids == [0x0001, 0x0100, 0x0950, 0x095D, 0x8100]
    assert file.build() == data
    assert file.attributes(0) == (2, 3)
    first = struct.unpack_from("<II", data, 16 + 0x20)
    assert first[0] == 16 + 5 * qm.ENTRY and first[0] % 4 == 0
    with pytest.raises(qm.FormatError):
        qm.Qm(b"QX\0\0" + data[4:])


def test_sample_round_trip_and_unedited_save_is_byte_exact():
    check_round_trip("zelda_oot3d", sample())
    rules = load_rules("zelda_oot3d")
    blocks, names = rules.load_data_from_json_obj(sample())
    assert [names[str(i)] for i in range(len(blocks))] == [
        "Items received", "Navi's hints", "File select, options, Boss Challenge", "Area names"]
    assert blocks[1][0] == "{color:light-blue}Look, {name}!{box-break}\nNext box."
    assert rules.save_data_to_json_obj(blocks, names) == sample()


def test_edits_touch_only_the_english_slot_and_follow_block_names():
    rules = load_rules("zelda_oot3d")
    blocks, names = rules.load_data_from_json_obj(sample())
    # A project of one block per range passes the blocks of the file it saves in its own order and names.
    order = [3, 0]
    data = [list(blocks[i]) for i in order]
    data[0][0] = "{quicktext-on}Гайрул: Ґ Є І Ї, м’ята{quicktext-off}"
    saved = rules.save_data_to_json_obj(data, {str(n): names[str(i)] for n, i in enumerate(order)})
    again = load_rules("zelda_oot3d").load_data_from_json_obj(saved)[0]
    assert again[3] == data[0] and again[:3] == blocks[:3]
    assert [t[1] for t in qm.Qm(saved).texts] == [t[1] for t in qm.Qm(sample()).texts]


def test_save_builds_on_the_newest_version_that_parses():
    rules = load_rules("zelda_oot3d")
    blocks, names = rules.load_data_from_json_obj(sample())
    blocks[0][0] = "Ви позичили {color:red}Яйце{color:default}!"
    translated = rules.save_data_to_json_obj(blocks, names)
    rules.reset_runtime_state()
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([b"broken", translated, sample()])))
    blocks[3][0] = "Гайрул"
    again = load_rules("zelda_oot3d").load_data_from_json_obj(rules.save_data_to_json_obj(blocks, names))[0]
    assert again[0][0].startswith("Ви позичили") and again[3][0] == "Гайрул"


@pytest.mark.parametrize("text", ["a\nb", "{box-break}\nx", "{box-break-delayed:30}\ny", "{textid:0x0205}",
                                  "{sfx:0x0001000558}", "{two-choice}", "{three-choice}", "{button:A}{button:28}",
                                  "{mq}northwest{mq-else}northeast{mq-end}", "{plural:1}a{plural-else}b{plural-end}",
                                  "{xpos:16}", "{background:0x010110}", "", "\n", "Ґ’є ©"])
def test_editor_form_is_reversible(text):
    assert qm.to_editor(qm.from_editor(text)) == text


def test_bad_tags_are_refused_and_tags_described():
    for bad in ("{bogus}", "{color}", "{name:3}", "{color:purple}", "a { b"):
        with pytest.raises(qm.FormatError):
            qm.from_editor(bad)
    assert qm.describe("{color:red}") == "Text colour: red" and qm.describe("not a tag") == ""
    manager = load_rules("zelda_oot3d").tag_manager
    assert manager.is_tag_legitimate("{item-icon:3}") and not manager.is_tag_legitimate("[icon]")


def test_keyboard_pages_and_default_name():
    rules = load_rules("zelda_oot3d")
    page = b"\xff\xfe" + "1234qwerty".encode("utf-16-le")
    blocks, _names = rules.load_data_from_json_obj(page)
    assert blocks == [["1234qwerty"]]
    assert rules.save_data_to_json_obj(blocks, {}) == page
    assert rules.save_data_to_json_obj([["1234йцукен"]], {}) == b"\xff\xfe" + "1234йцукен".encode("utf-16-le")

    size, (first, second) = next(iter(CODE_BIN.items()))
    code = bytearray(size)
    for at in (first, second):
        code[at:at + 10] = "Link\0".encode("utf-16-le")
    code = bytes(code)
    rules = load_rules("zelda_oot3d")
    assert rules.load_data_from_json_obj(code)[0] == [["Link"]]
    assert rules.save_data_to_json_obj([["Link"]], {}) == code
    renamed = rules.save_data_to_json_obj([["Лінк"]], {})
    assert read_name(renamed) == "Лінк" and renamed[second:second + 8] == "Лінк".encode("utf-16-le")
    assert read_name(write_name(code, "Ян")) == "Ян"
    with pytest.raises(ValueError):
        write_name(code, "Лінкольн")


def test_other_files_give_one_empty_block():
    assert load_rules("zelda_oot3d").load_data_from_json_obj(b"QBF1\x00\x00") == ([[]], {})


# -- hooks that read the project's file ------------------------------------------------------

class _ProjectManager:
    def __init__(self, root: Path, keys):
        self.root = root
        self.project = SimpleNamespace(blocks=[SimpleNamespace(source_file="eu.qm", internal_key=key) for key in keys])

    def get_absolute_path(self, rel, is_translation=False):
        return str(self.root / rel)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "eu.qm").write_bytes(sample())
    keys = ["Items received", "Navi's hints", "File select, options, Boss Challenge", "Area names"]
    mw = SimpleNamespace(project_manager=_ProjectManager(tmp_path, keys), block_to_project_file_map={i: i for i in range(4)})
    return load_rules("zelda_oot3d", mw)


def test_message_attributes_context_and_layout(project):
    assert project.get_message_attributes(2, 1) == {"message_id": 0x095D, "textbox_type": 2, "textbox_position": 3}
    assert project.get_translation_context_for_string(3, 0) == {"content_role": "Area name", "has_speaker": False}
    assert project.get_string_layout(0, 0)["font_file"] == "ltn16.json"
    widths = {"a": {"width": 5}, "b": {"width": 7}}
    assert project.calculate_string_width_override("{color:red}ab{color:default}\nb", widths) == 12


def test_references_match_by_message_id(project, tmp_path):
    folder = tmp_path / "ru" / "romfs" / "message" / "eu"
    folder.mkdir(parents=True)
    russian = {0x0001: "Вы одолжили яйцо!", 0x8100: "Хайрул"}
    (folder / "eu.qm").write_bytes(sample(russian))
    names = {str(i): "" for i in range(4)}
    languages = project.load_multi_reference(str(tmp_path / "ru"), names)
    assert set(languages) == {"Russian (RU)", "German (DE)"}
    assert languages["Russian (RU)"] == {(0, 0): "Вы одолжили яйцо!", (3, 0): "Хайрул"}
    assert languages["German (DE)"][(0, 0)] == "Hallo"
    assert project.load_reference_patch(str(folder / "eu.qm"), names)[(3, 0)] == "Хайрул"


# -- the workspace's own files ---------------------------------------------------------------

@pytest.mark.skipif(not (OOT3D / "source" / "romfs" / "message" / "eu" / "eu.qm").exists(),
                    reason="Ocarina of Time 3D workspace not unpacked here")
def test_real_file_round_trips_byte_exact():
    data = (OOT3D / "source" / "romfs" / "message" / "eu" / "eu.qm").read_bytes()
    file = qm.Qm(data)
    assert file.build() == data                                          # the game's own layout, byte for byte
    for texts in file.texts:
        for raw in texts:
            if raw:
                assert qm.from_editor(qm.to_editor(raw)) == raw          # every language, every code
    rules = load_rules("zelda_oot3d")
    blocks, names = rules.load_data_from_json_obj(data)
    assert sum(map(len, blocks)) == 2510 and len(blocks) == 19
    assert rules.save_data_to_json_obj(blocks, names) == data
    blocks[0][0] = "{unskippable}Ви позичили {color:red}Яйце{color:default}! Ґанок, їжак, Єва, м’ята."
    edited = rules.save_data_to_json_obj(blocks, names)
    assert load_rules("zelda_oot3d").load_data_from_json_obj(edited)[0] == blocks


@pytest.mark.skipif(not (OOT3D / "source" / "exefs" / "code.bin").exists(), reason="Ocarina of Time 3D workspace not unpacked here")
def test_real_keyboards_and_default_name():
    rules = load_rules("zelda_oot3d")
    for page in sorted((OOT3D / "source" / "romfs" / "menu").glob("ltn16_*.list")):
        data = page.read_bytes()
        assert rules.save_data_to_json_obj(rules.load_data_from_json_obj(data)[0], {}) == data
    code = (OOT3D / "source" / "exefs" / "code.bin").read_bytes()
    assert rules.load_data_from_json_obj(code)[0] == [["Link"]]
    assert rules.save_data_to_json_obj([["Link"]], {}) == code
