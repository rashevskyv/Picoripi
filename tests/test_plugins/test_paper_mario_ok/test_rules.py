"""Paper Mario: The Origami King plugin without game data: this game's MSBP tag names, the stored-as-number
Font tag, and an MSBT that saves back byte for byte with only the edited message re-encoded."""
import struct

from plugins.common.msbt import Msbt, Tag
from plugins.paper_mario_nx.tags import TAGS as TTYD_TAGS
from plugins.paper_mario_ok.rules import GameRules, TagManager
from plugins.paper_mario_ok.tags import TAGS, from_editor, to_editor


class _Fake:
    endian, little = "<", True


def _msbt(texts):
    """A minimal little-endian UTF-16 MSBT with one TXT2 section."""
    bodies = [Msbt.encode_text(_Fake(), tokens) for tokens in texts]
    offsets, at = [], 4 + 4 * len(bodies)
    for body in bodies:
        offsets.append(at)
        at += len(body)
    txt2 = struct.pack(f"<I{len(bodies)}I", len(bodies), *offsets) + b"".join(bodies)
    out = bytearray(b"MsgStdBn\xff\xfe\x00\x00\x01\x03\x01\x00" + bytes(16))
    out += b"TXT2" + struct.pack("<I", len(txt2)) + bytes(8) + txt2
    out += b"\xab" * (-len(out) % 16)
    struct.pack_into("<I", out, 0x12, len(out))
    return bytes(out)


def test_the_catalogue_is_this_games_msbp_not_the_thousand_year_doors():
    names = {name for name, _types, _desc in TAGS.values()}
    assert {"Font", "PageBreak", "Color", "center", "value", "select", "dialect", "lyric", "Karaoke_wait"} <= names
    assert len(TAGS) == 26 and len(TTYD_TAGS) > len(TAGS)


def test_the_font_tag_stores_a_signed_font_number():
    assert to_editor([Tag(0, 1, b"\x04\x00"), "Hi", Tag(0, 1, b"\xff\xff")]) == "{Font:4}Hi{Font:-1}"
    assert from_editor("{Font:4}Hi{Font:-1}") == [Tag(0, 1, b"\x04\x00"), "Hi", Tag(0, 1, b"\xff\xff")]


def test_an_msbt_saves_back_byte_for_byte_and_takes_an_edit():
    raw = _msbt([["Press any button"], [Tag(0, 1, b"\x04\x00"), "MAX HP +5!", Tag(1, 0, struct.pack("<i", 250))]])
    rules = GameRules()
    assert rules.get_display_name() == "Paper Mario: The Origami King (Switch)"
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks == [["Press any button", "{Font:4}MAX HP +5!{wait:250}"]]
    assert rules.save_data_to_json_obj(blocks, names) == raw
    blocks[0][0] = "UA TEST"
    saved = Msbt(rules.save_data_to_json_obj(blocks, names))
    assert saved.messages[0] == ["UA TEST"]
    assert saved.messages[1] == Msbt(raw).messages[1]


def test_the_tag_manager_accepts_this_games_tags_only():
    manager = TagManager()
    assert manager.is_tag_legitimate("{Font:-1}")
    assert manager.is_tag_legitimate("{dialect}")
    assert not manager.is_tag_legitimate("{Plural_N:1}")          # a Thousand-Year Door tag
