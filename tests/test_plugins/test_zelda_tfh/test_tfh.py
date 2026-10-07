"""Tri Force Heroes plugin: the A Link Between Worlds rules with the game's own tags (Alice.msbp), file roles and
widths. Synthetic files only (real files: test_tfh_real.py)."""
import struct
from types import SimpleNamespace

from plugins.common.msbt import Msbt
from plugins.testing import check_round_trip, check_validator
from plugins.zelda_tfh import tags
from plugins.zelda_tfh.rules import GameRules
from plugins.zelda_tfh.tag_manager import TagManager

PLUGIN = "zelda_tfh"


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
    """A TFH MSBT: LBL1, ATR1 of size 0, TXT2; ``entries`` is ``[(label, text bytes)]``."""
    labels = b"".join(bytes([len(name)]) + name.encode() + struct.pack("<I", i) for i, (name, _t) in enumerate(entries))
    lbl1 = struct.pack("<III", 1, len(entries), 12) + labels
    offsets, position = [], 4 + 4 * len(entries)
    for _label, entry in entries:
        offsets.append(position)
        position += len(entry)
    txt2 = struct.pack(f"<I{len(entries)}I", len(entries), *offsets) + b"".join(entry for _l, entry in entries)
    body = _section(b"LBL1", lbl1) + _section(b"ATR1", struct.pack("<II", len(entries), 0)) + _section(b"TXT2", txt2)
    return b"MsgStdBn\xff\xfe\x00\x00\x01\x03" + struct.pack("<HHI", 3, 0, 0x20 + len(body)) + bytes(10) + body


NAME, RESET = (0, 3, b"\x00\x00"), (0, 3, b"\xff\xff")       # palette index 0 = Name, -1 = default colour
PLAYER, SMALL, NORMAL = (1, 0, b""), (0, 2, b"\x5a\x00"), (0, 2, b"\x64\x00")
RUBY = (0, 0, b"\x02\x00\x04\x00" + "かい".encode("utf-16-le"))   # base length, then the reading
SAMPLE = msbt([
    ("npc_msg_00", text("Hi, ", PLAYER, "! See ", NAME, "Madame Couture", RESET, ".")),
    ("npc_msg_01", text(SMALL, "psst", NORMAL, " 開", RUBY)),
])
SAMPLE_TEXT = ["Hi, {PlayerName}! See {Color:Name}Madame Couture{Color:Reset}.",
               "{Size:90}psst{Size:100} 開{Ruby:2:かい}"]


class _Project:
    def __init__(self, path):
        self.project = SimpleNamespace(blocks=[SimpleNamespace(source_file=path)])

    def get_absolute_path(self, rel):
        return rel


def test_the_plugin_validates_and_round_trips():
    check_validator(PLUGIN)
    check_round_trip(PLUGIN, SAMPLE)


def test_tags_are_named_by_alice_msbp():
    messages = Msbt(SAMPLE).messages
    assert [tags.to_editor(message) for message in messages] == SAMPLE_TEXT
    assert [tags.from_editor(shown) for shown in SAMPLE_TEXT] == messages
    assert [group["name"] for group in tags.PROJECT["tag_groups"]] == ["System", "Insert", "Action", "Kor"]
    assert TagManager().is_tag_legitimate("{CostumeName:EightBit:No}")
    assert not TagManager().is_tag_legitimate("{Cursor:0:0}")


def test_an_edit_changes_one_message_only():
    rules = GameRules()
    blocks, _names = rules.load_data_from_json_obj(SAMPLE)
    assert rules.save_data_to_json_obj(blocks, {}) == SAMPLE
    again = Msbt(rules.save_data_to_json_obj([["UA TEST", blocks[0][1]]], {}))
    assert tags.to_editor(again.messages[0]) == "UA TEST"
    assert again.messages[1] == Msbt(SAMPLE).messages[1]


def test_size_scales_the_width_until_it_changes():
    font = {char: {"width": 10} for char in "ab"}
    assert GameRules().calculate_string_width_override("{Size:90}aaaaaaaaaa\nbbbbbbbbbb{Size:100}", font) == 90
    assert GameRules().calculate_string_width_override("{Size:150}a{Size:100}b", font) == 25


def test_dialogue_has_the_message_window_and_layouts_and_credits_have_no_limit(tmp_path):
    for name, limited in (("NpcKing", True), ("LayoutTitle", False), ("StaffCredit", False)):
        path = tmp_path / f"{name}.msbt"
        path.write_bytes(SAMPLE)
        rules = GameRules(SimpleNamespace(project_manager=_Project(str(path)), block_to_project_file_map={}))
        found = rules.get_string_layout(0, 0)
        assert ("max_width" in found) is limited, name
        if limited:
            assert found["max_width"] == 344 and found["lines_per_page"] == 3
