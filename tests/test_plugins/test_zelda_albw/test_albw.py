"""A Link Between Worlds plugin: little-endian MSBT with tags named by the game's MSBP (version 3), byte-exact
save, widths from the message project's styles. Synthetic files only (real files: test_albw_real.py)."""
import struct
from types import SimpleNamespace

from plugins.common import msbp
from plugins.common.lms_tags import TagCodec, catalogue_from_msbp
from plugins.common.msbt import Msbt, Tag
from plugins.testing import check_round_trip, check_validator
from plugins.zelda_albw import tags
from plugins.zelda_albw.rules import DIALOGUE_WIDTH, GameRules

PLUGIN = "zelda_albw"


def _section(magic: bytes, body: bytes, pad: bytes = b"\xab") -> bytes:
    data = magic + struct.pack("<I", len(body)) + b"\x00" * 8 + body
    return data + pad * (-len(data) % 16)


def text(*parts) -> bytes:
    """A TXT2 entry (UTF-16LE): str parts and (group, type, params) tags."""
    out = b""
    for part in parts:
        out += part.encode("utf-16-le") if isinstance(part, str) else \
            struct.pack("<HHHH", 0x0E, part[0], part[1], len(part[2])) + part[2]
    return out + b"\x00\x00"


def msbt(entries) -> bytes:
    """An ALBW MSBT: LBL1, ATR1 of size 0, TXT2; ``entries`` is ``[(label, text bytes)]``."""
    labels = b"".join(bytes([len(name)]) + name.encode() + struct.pack("<I", i) for i, (name, _t) in enumerate(entries))
    lbl1 = struct.pack("<III", 1, len(entries), 12) + labels
    offsets, position = [], 4 + 4 * len(entries)
    for _label, entry in entries:
        offsets.append(position)
        position += len(entry)
    txt2 = struct.pack(f"<I{len(entries)}I", len(entries), *offsets) + b"".join(entry for _l, entry in entries)
    body = _section(b"LBL1", lbl1) + _section(b"ATR1", struct.pack("<II", len(entries), 0)) + _section(b"TXT2", txt2)
    return b"MsgStdBn\xff\xfe\x00\x00\x01\x03" + struct.pack("<HHI", 3, 0, 0x20 + len(body)) + bytes(10) + body


NAME, RESET = (0, 3, b"\x09\x00"), (0, 3, b"\xff\xff")
PLAYER, WAIT = (1, 0, b""), (1, 8, b"\x1e\x00")
HAMMER = (2, 2, b"\x07\x01\x00\xcd")          # ItemName: item 7, Coloring Yes, ToUpper No
NUMBER = (1, 5, b"\x02\x00\xff\xff\x00\xcd")  # IntNumberN: 2 figures, Nth 0, runtime value, no unit
SAMPLE = msbt([
    ("lgt_NpcRavio_00", text("Hey, ", PLAYER, "! Rent the ", HAMMER, "?", WAIT)),
    ("T_Rupee_00", text(NAME, "Shadow Link", RESET, " paid ", NUMBER, ".")),
])
SAMPLE_TEXT = ["Hey, {PlayerName}! Rent the {ItemName:hammer:Yes:No}?{Wait:30}",
               "{Color:Name}Shadow Link{Color:Reset} paid {IntNumberN:2:0:-1:None}."]


def test_the_plugin_validates_and_round_trips():
    check_validator(PLUGIN)
    check_round_trip(PLUGIN, SAMPLE)


def test_tags_are_named_by_the_message_project():
    messages = Msbt(SAMPLE).messages
    assert [tags.to_editor(message) for message in messages] == SAMPLE_TEXT
    assert [tags.from_editor(shown) for shown in SAMPLE_TEXT] == messages
    assert tags.from_editor("{tag:9:1:0102}") == [Tag(9, 1, b"\x01\x02")]
    assert "ItemName" in tags.describe("{ItemName:hammer:Yes:No}")


def test_an_unedited_file_saves_byte_for_byte_and_an_edit_changes_one_message():
    rules = GameRules()
    blocks, _names = rules.load_data_from_json_obj(SAMPLE)
    assert rules.save_data_to_json_obj(blocks, {}) == SAMPLE
    edited = rules.save_data_to_json_obj([["UA TEST {PlayerName}", blocks[0][1]]], {})
    again = Msbt(edited)
    assert tags.to_editor(again.messages[0]) == "UA TEST {PlayerName}"
    assert again.messages[1] == Msbt(SAMPLE).messages[1]
    assert again.labels == Msbt(SAMPLE).labels


def _msbp_v3() -> bytes:
    """An MSBP version 3 (3DS) with one tag group: TGG2 entries have no group id."""
    def table(entries):
        offsets, position = [], 4 + 4 * len(entries)
        for entry in entries:
            offsets.append(position)
            position += len(entry)
        return struct.pack("<HH", len(entries), 0) + struct.pack(f"<{len(entries)}I", *offsets) + b"".join(entries)
    tgl = table([b"No\x00", b"Yes\x00"])
    tgp = table([b"\x01Frames\x00", b"\x09\x00" + struct.pack("<HHH", 2, 0, 1) + b"Fast\x00"])
    tag = table([struct.pack("<HHH", 2, 0, 1) + b"Wait\x00"])
    tgg = table([struct.pack("<HH", 1, 0) + b"Control\x00"])
    body = b"".join(_section(m, b) for m, b in ((b"TGG2", tgg), (b"TAG2", tag), (b"TGP2", tgp), (b"TGL2", tgl)))
    return b"MsgPrjBn\xff\xfe\x00\x00\x00\x03" + struct.pack("<HHI", 4, 0, 0x20 + len(body)) + bytes(10) + body


def test_a_3ds_message_project_gives_the_catalogue():
    project = msbp.read(_msbp_v3())
    assert project["tag_groups"] == [{"id": 0, "name": "Control", "tags": [
        {"name": "Wait", "params": [{"name": "Frames", "type": "u16"},
                                    {"name": "Fast", "type": "list", "items": ["No", "Yes"]}]}]}]
    catalogue, names = catalogue_from_msbp(project)
    codec = TagCodec(catalogue, names)
    tag = Tag(0, 0, b"\x1e\x00\x01\xcd")
    assert codec.render_tag(tag) == "{Wait:30:Yes}"
    assert codec.parse_tag("{Wait:30:Yes}") == tag


def test_widths_count_the_player_name_and_numbers():
    rules = GameRules()
    font = {char: {"width": 10} for char in "Link0a"}
    assert rules.calculate_string_width_override("{PlayerName}{Color:Name}a{IntNumberN:2:0:-1:None}", font) == 70


class _Project:
    def __init__(self, path):
        self.project = SimpleNamespace(blocks=[SimpleNamespace(source_file=path)])

    def get_absolute_path(self, rel):
        return rel


def test_layout_texts_take_their_text_box_and_dialogue_the_widest_english_line(tmp_path):
    layout = tmp_path / "Mn_TitleB.msbt"
    layout.write_bytes(msbt([("T_PressButton_00", text("Press "))]))
    dialogue = tmp_path / "Field.msbt"
    dialogue.write_bytes(SAMPLE)
    for path, expected in ((layout, (tags.PROJECT, "Mn_TitleB_T_PressButton_00")), (dialogue, None)):
        rules = GameRules(SimpleNamespace(project_manager=_Project(str(path)), block_to_project_file_map={}))
        found = rules.get_string_layout(0, 0)
        if expected is None:
            assert found["max_width"] == DIALOGUE_WIDTH and found["lines_per_page"] == 3
        else:
            style = next(s for s in tags.PROJECT["styles"] if s["name"] == expected[1])
            assert found["warn_width"] == style["region_width"]
