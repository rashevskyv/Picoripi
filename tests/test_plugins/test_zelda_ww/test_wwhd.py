"""Wind Waker HD in the zelda_ww plugin: big-endian MSBT with readable tags, attributes as speakers,
box widths and conversations, and a source folder project end to end. Synthetic files only."""
import struct
from types import SimpleNamespace

import pytest

from core.data_state_processor import DataStateProcessor
from core.project_manager import ProjectManager
from core.project_models import Project
from handlers.project_action.load_worker import ProjectLoadWorker
from plugins.testing import check_round_trip
from plugins.common.msbt import Msbt
from core.containers import yaz0
from plugins.zelda_ww import messages, reference, tags
from plugins.zelda_ww.rules import GameRules
from ..test_zelda_totk.samples import sarc

PLUGIN = "zelda_ww"


def _section(magic: bytes, body: bytes) -> bytes:
    data = magic + struct.pack(">I", len(body)) + b"\x00" * 8 + body
    return data + b"\xab" * (-len(data) % 16)


def text(*parts) -> bytes:
    """A TXT2 entry (UTF-16BE): str parts and ("tag", group, type, params)."""
    out = b""
    for part in parts:
        out += part.encode("utf-16-be") if isinstance(part, str) else \
            struct.pack(">HHHH", 0x0E, part[1], part[2], len(part[3])) + part[3]
    return out + b"\x00\x00"


def attribute(character: str, balloon: str, next_no: int = 0) -> bytes:
    raw = bytearray(messages.ATTRIBUTE_SIZE)
    raw[0], raw[1] = messages.CHARACTER_NAMES.index(character), messages.BALLOON_TYPES.index(balloon)
    struct.pack_into(">H", raw, 6, next_no)
    return bytes(raw)


def msbt(entries) -> bytes:
    """A Wii U MSBT; ``entries`` is ``[(label, text bytes, attribute bytes)]``."""
    labels = b"".join(bytes([len(label)]) + label.encode() + struct.pack(">I", index)
                      for index, (label, _text, _attr) in enumerate(entries))
    lbl1 = struct.pack(">III", 1, len(entries), 12) + labels
    atr1 = struct.pack(">II", len(entries), messages.ATTRIBUTE_SIZE) + b"".join(attr for _l, _t, attr in entries)
    tsy1 = b"".join(struct.pack(">I", 0) for _ in entries)
    texts = [entry_text for _label, entry_text, _attr in entries]
    offsets, position = [], 4 + 4 * len(texts)
    for entry_text in texts:
        offsets.append(position)
        position += len(entry_text)
    txt2 = struct.pack(f">I{len(texts)}I", len(texts), *offsets) + b"".join(texts)
    body = _section(b"LBL1", lbl1) + _section(b"ATR1", atr1) + _section(b"TSY1", tsy1) + _section(b"TXT2", txt2)
    header = b"MsgStdBn" + b"\xfe\xff" + b"\x00\x00" + bytes([1, 3]) + struct.pack(">HHI", 4, 0, 0x20 + len(body))
    return header + b"\x00" * 10 + body


RED, DEFAULT = ("tag", 0, 3, b"\x00\x01"), ("tag", 0, 3, b"\xff\xff")
MESSAGE = msbt([
    ("00102", text("You got a ", RED, "Green Rupee", DEFAULT, "!"), attribute("GettingItems", "GettingItems")),
    ("03001", text("Big Brother, ", ("tag", 2, 0, b""), "!", ("tag", 1, 6, b"\x00\x0a")), attribute("Aryll", "Text", 3002)),
    ("03002", text("Wait for me!"), attribute("Aryll", "Text")),
    ("00401", text("Telescope"), attribute("ItemName", "QuestStatusScreen")),
])
MESSAGE_TEXT = ["You got a [Red]Green Rupee[/C]!", "Big Brother, [Name]![Wait:10]", "Wait for me!", "Telescope"]


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, MESSAGE)


def test_tags_read_from_the_msbp_catalogue_round_trip():
    tokens = Msbt(MESSAGE).messages
    assert [tags.to_editor(message) for message in tokens] == MESSAGE_TEXT
    assert [tags.from_editor(shown) for shown in MESSAGE_TEXT] == tokens
    for shown in ("[SE:259]", "[Camera:SpeakerFront]", "[Action:Laugh]", "[SetValue0:2:No:FullSize]",
                  "[Ruby:4:かんじ]", "[A]", "[Size:150]", "[Tag:9:1:0102]"):
        assert tags.render_tag(tags.parse_tag(shown)) == shown
    assert tags.from_editor("[not a tag] text") == ["[not a tag] text"]
    assert "frame" in tags.describe("[Wait:10]")


def test_unchanged_messages_keep_their_bytes_and_edits_keep_labels_and_attributes():
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(MESSAGE)
    assert blocks == [MESSAGE_TEXT]
    assert rules.save_data_to_json_obj(blocks, names) == MESSAGE
    saved = Msbt(rules.save_data_to_json_obj([["Ти отримав [Red]Зелену рупію[/C]!", *MESSAGE_TEXT[1:]]], names))
    assert saved.labels == Msbt(MESSAGE).labels and saved.section(b"ATR1") == Msbt(MESSAGE).section(b"ATR1")
    assert tags.to_editor(saved.messages[0]) == "Ти отримав [Red]Зелену рупію[/C]!"


def test_kruptar_text_dumps_still_load_as_text():
    rules = GameRules()
    assert rules.load_data_from_json_obj([["[Red]Text[/C]"]])[0] == [["[Red]Text[/C]"]]
    assert rules.save_data_to_json_obj([["[Red]Текст[/C]"]], {}).startswith("[Red]Текст[/C]")


def test_speaker_names_come_from_the_character_attribute():
    assert messages.speaker_name("Medli-Rito-") == "Medli"
    assert messages.speaker_name("RedLionKing-Boat-") == "King of Red Lions"
    assert messages.speaker_name("GreatFairy") == "Great Fairy"
    assert messages.speaker_name("Sign") is None


def test_a_source_folder_project_gives_context_and_saves_only_the_edit(tmp_path):
    source = tmp_path / "source"
    (source / "Message").mkdir(parents=True)
    (source / "Message" / "message.msbt").write_bytes(MESSAGE)
    title = msbt([("T_Press_00", text("Press Any Button"), attribute("-", "Text"))])
    (source / "Message" / "Title_00.msbt").write_bytes(title)
    manager = ProjectManager()
    manager.project_dir = str(tmp_path)
    manager.project_file_path = str(tmp_path / "project.uiproj")
    manager.project = Project(name="WWHD", plugin_name=PLUGIN)
    manager.project.metadata = {"source_path": str(source), "translation_path": str(tmp_path / "translation"),
                                "is_directory_mode": True}
    rules = GameRules()
    manager.sync_project_files(plugin=rules)
    results = []
    worker = ProjectLoadWorker(manager, rules)
    worker.finished_with_result.connect(results.append)
    worker.run()
    loaded = results[0]
    block = int(next(index for index, name in loaded["block_names"].items() if name == "message"))
    assert loaded["data"][block] == MESSAGE_TEXT

    rules.mw = SimpleNamespace(project_manager=manager, block_to_project_file_map=loaded["block_to_project_file_map"],
                               font_map={})
    assert rules.get_speaker_for_string(block, 1) == "Aryll"
    assert rules.get_speaker_for_string(block, 0) is None
    assert rules.get_translation_context_for_string(block, 0)["has_speaker"] is False
    assert rules.get_string_layout(block, 1) == {"warn_width": 875, "max_width": 875, "lines_per_page": 4}
    assert rules.get_string_layout(block, 0)["max_width"] == 812
    assert rules.get_ai_flow_group_for_string(block, 1) == rules.get_ai_flow_group_for_string(block, 2) == "wwhd:03001"
    assert rules.get_ai_flow_group_for_string(block, 0) is None
    assert rules.get_scene_context_for_string(block, 1)["label"] == "03001"
    assert [(entry["term"], entry["section"]) for entry in rules.get_glossary_seed_entries()] == [("Telescope", "Items")]

    # Reference languages: other language packs, matched by file and label (Russian first, English skipped).
    def pack(lines: dict) -> bytes:
        entries = [(label, text(shown), attribute("-", "Text")) for label, shown in lines.items()]
        return sarc({"message_msbt.szs": yaz0.compress(sarc({"message.msbt": msbt(entries)}))})
    refs = tmp_path / "reference"
    (refs / "nested").mkdir(parents=True)
    (refs / "permanent_2d_UsFrench.pack").write_bytes(pack({"03002": "Attends-moi !", "00102": "Rubis vert"}))
    (refs / "nested" / "permanent_2d_RuRussian.pack").write_bytes(pack({"03002": "Подожди меня!"}))
    (refs / "permanent_2d_UsEnglish.pack").write_bytes(pack({"03002": "Wait for me!"}))
    (refs / "permanent_2d_UsSpanish.pack").write_bytes(b"not a pack")
    found = rules.load_multi_reference(str(refs), loaded["block_names"])
    assert list(found) == ["Russian (RU)", "French (US)"]
    assert found["Russian (RU)"] == {(block, 2): "Подожди меня!"}
    assert found["French (US)"] == {(block, 0): "Rubis vert", (block, 2): "Attends-moi !"}
    assert rules.load_reference_patch(str(refs), loaded["block_names"]) == found["Russian (RU)"]
    assert reference.label("permanent_2d_EuGerman.pack") == "German (EU)" and reference.label("other.pack") == ""

    output = [list(rows) for rows in loaded["data"]]
    output[block][2] = "Зачекай на мене!"
    mw = SimpleNamespace(state=None, project_manager=manager, current_game_rules=rules,
                         block_to_project_file_map=loaded["block_to_project_file_map"],
                         data_store=SimpleNamespace(block_names=loaded["block_names"],
                                                    edited_data={(block, 2): output[block][2]}))
    saved, _warnings, errors = DataStateProcessor(mw)._perform_save_impl(output)
    assert (saved, errors) == (True, [])
    written = Msbt((tmp_path / "translation" / "Message" / "message.msbt").read_bytes())
    assert [tags.to_editor(m) for m in written.messages] == [*MESSAGE_TEXT[:2], "Зачекай на мене!", "Telescope"]
    assert written.messages[:2] == Msbt(MESSAGE).messages[:2]


@pytest.mark.parametrize("balloon, width", [("Text", 875), ("Text-Centered", 875), ("Sign-Wood", 812),
                                            ("GettingItems", 812)])
def test_box_widths_follow_the_balloon_type(balloon, width):
    assert messages.box_width(balloon) == width
