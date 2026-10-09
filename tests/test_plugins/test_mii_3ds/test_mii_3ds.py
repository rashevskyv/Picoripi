"""Tomodachi Life / Miitopia plugin: the A Link Between Worlds rules with Tomodachi Life's tags (Game.msbp), the
text-to-speech files and no width model. Synthetic files only (real files: test_mii_3ds_real.py)."""
import struct
from types import SimpleNamespace

from plugins.common.msbt import Msbt
from plugins.mii_3ds import tags
from plugins.mii_3ds.rules import GameRules
from plugins.mii_3ds.tag_manager import TagManager
from plugins.testing import check_round_trip, check_validator

PLUGIN = "mii_3ds"


def _section(magic: bytes, body: bytes) -> bytes:
    data = magic + struct.pack("<I", len(body)) + b"\x00" * 8 + body
    return data + b"\xab" * (-len(data) % 16)


def text(*parts) -> bytes:
    """A TXT2 entry (UTF-16LE): str parts and (group, type, params) tags."""
    out = b""
    for part in parts:
        out += part.encode("utf-16-le") if isinstance(part, str) else \
            struct.pack("<HHHH", 0x0E, part[0], part[1], len(part[2])) + part[2]
    return out + b"\x00\x00"


def msbt(entries) -> bytes:
    """An MSBT with LBL1, ATR1 (empty) and TXT2; ``entries`` is ``[(label, text bytes)]``."""
    labels = b"".join(bytes([len(name)]) + name.encode() + struct.pack("<I", i) for i, (name, _t) in enumerate(entries))
    lbl1 = struct.pack("<III", 1, len(entries), 12) + labels
    offsets, position = [], 4 + 4 * len(entries)
    for _label, entry in entries:
        offsets.append(position)
        position += len(entry)
    txt2 = struct.pack(f"<I{len(entries)}I", len(entries), *offsets) + b"".join(entry for _l, entry in entries)
    body = _section(b"LBL1", lbl1) + _section(b"ATR1", struct.pack("<II", len(entries), 0)) + _section(b"TXT2", txt2)
    return b"MsgStdBn\xff\xfe\x00\x00\x01\x03" + struct.pack("<HHI", 3, 0, 0x20 + len(body)) + bytes(10) + body


PAGE, RED, WHITE = (0, 4, b""), (0, 3, b"\xff\x00\x00\xff"), (0, 3, b"\xff\xff\xff\xff")   # Color: R, G, B, A
NICKNAME = (1, 10, b"\x01\x00")          # Mii.MyNickname (list, list): the game's own bytes
FOOD = (4, 3, b"\x00\x00\x01\xcd")       # Reference.Food (u8, list, list) + the odd-length pad
PLURAL = (9, 3, b"\x00\x01" + b"\x04\x00" + "is".encode("utf-16-le") + b"\x06\x00" + "are".encode("utf-16-le"))
PAUSE = (12, 2, b"\xf4\x01")             # Nuance.CS_Pause (u16): a text-to-speech pause of 500 ms
SAMPLE = msbt([
    ("0004", text("Welcome, ", NICKNAME, " lookalike!", PAGE, RED, "Yes", WHITE)),
    ("0005", text("I'm so mad", PAUSE, " about ", FOOD, " ", PLURAL, "!")),
])
SAMPLE_TEXT = ["Welcome, {MyNickname:Voice:None} lookalike!{PageBreak}{Color:255:0:0:255}Yes{Color:255:255:255:255}",
               "I'm so mad{CS_Pause:500} about {Food:0:Name:Plural} {SingularPluralFood:0:Plural:is:are}!"]


class _Project:
    def __init__(self, path):
        self.project = SimpleNamespace(blocks=[SimpleNamespace(source_file=path)])

    def get_absolute_path(self, rel):
        return rel


def test_the_plugin_validates_and_round_trips():
    check_validator(PLUGIN)
    check_round_trip(PLUGIN, SAMPLE)


def test_tags_are_named_by_the_games_message_project():
    messages = Msbt(SAMPLE).messages
    assert [tags.to_editor(message) for message in messages] == SAMPLE_TEXT
    assert [tags.from_editor(shown) for shown in SAMPLE_TEXT] == messages
    assert [group["name"] for group in tags.PROJECT["tag_groups"]][:3] == ["System", "Mii", "MiiTalk"]
    assert "Nuance" in [group["name"] for group in tags.PROJECT["tag_groups"]]
    assert TagManager().is_tag_legitimate("{Speaker:0:0}")
    assert not TagManager().is_tag_legitimate("{Cursor:0:0}")


def test_an_edit_changes_one_message_only():
    rules = GameRules()
    blocks, _names = rules.load_data_from_json_obj(SAMPLE)
    assert rules.save_data_to_json_obj(blocks, {}) == SAMPLE
    again = Msbt(rules.save_data_to_json_obj([["UA TEST", blocks[0][1]]], {}))
    assert tags.to_editor(again.messages[0]) == "UA TEST"
    assert again.messages[1] == Msbt(SAMPLE).messages[1]


def test_voice_files_are_spoken_text_and_nothing_has_a_width_limit(tmp_path):
    for folder, spoken in (("ArcVoice", True), ("ArcBase", False), ("LayoutMsg", False)):
        path = tmp_path / folder / "TalkUsual_Msg.msbt"
        path.parent.mkdir()
        path.write_bytes(SAMPLE)
        rules = GameRules(SimpleNamespace(project_manager=_Project(str(path)), block_to_project_file_map={}))
        context = rules.get_translation_context_for_string(0, 0)
        assert context.get("content_role", "").startswith("Spoken text") is spoken, folder
        assert rules.get_string_layout(0, 0) is None
        assert rules.get_ai_flow_context_for_string(0, 0) == "Message 0004 in TalkUsual_Msg.msbt ()"
