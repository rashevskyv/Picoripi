"""Paper Mario TTYD (Switch) plugin without game data: tag names from the game's MSBP, list and string
arguments, and an MSBT that saves back byte for byte with only the edited message re-encoded."""
import struct

from plugins.common.msbt import EndTag, Msbt, Tag
from plugins.paper_mario_nx.rules import GameRules
from plugins.paper_mario_nx.tags import TAGS, from_editor, parse_tag, to_editor


def _msbt(texts):
    """A minimal little-endian UTF-16 MSBT with one TXT2 section."""
    bodies = [Msbt.encode_text(_Fake(), tokens) for tokens in texts]
    table = 4 + 4 * len(bodies)
    offsets, at = [], table
    for body in bodies:
        offsets.append(at)
        at += len(body)
    txt2 = struct.pack(f"<I{len(bodies)}I", len(bodies), *offsets) + b"".join(bodies)
    out = bytearray(b"MsgStdBn\xff\xfe\x00\x00\x01\x03\x01\x00" + bytes(16))
    out += b"TXT2" + struct.pack("<I", len(txt2)) + bytes(8) + txt2
    out += b"\xab" * (-len(out) % 16)
    struct.pack_into("<I", out, 0x12, len(out))
    return bytes(out)


class _Fake:
    endian, little = "<", True


def test_tags_take_their_msbp_names_and_later_groups_keep_theirs_apart():
    names = {name for name, _types, _desc in TAGS.values()}
    assert {"wait", "key_wait", "PageBreak", "Color", "center", "param", "Karaoke_wait", "Plural_N"} <= names
    assert to_editor([Tag(1, 0, struct.pack("<i", 250))]) == "{wait:250}"
    assert to_editor([Tag(0, 3, b"\xff\xff\xff\xcc")]) == "{Color:255:255:255:204}"
    assert to_editor([Tag(2, 0, b""), "Hi", EndTag(2, 0)]) == "{center}Hi{/center}"


def test_a_list_argument_is_named_and_a_string_after_it_starts_on_an_even_byte():
    tag = Tag(3, 13, b"\x02\xcd" + struct.pack("<H", 4) + "AB".encode("utf-16-le"))
    text = to_editor([tag])
    assert not text.startswith("{tag:")
    assert parse_tag(text) == tag
    assert from_editor("x" + text + "y") == ["x", tag, "y"]


def test_unknown_bytes_stay_raw_and_round_trip():
    tag = Tag(3, 13, b"\x02\x00\x00\x00")          # no 0xCD pad: not the game's layout
    assert to_editor([tag]).startswith("{tag:3:13:")
    assert from_editor(to_editor([tag])) == [tag]


def test_an_msbt_saves_back_byte_for_byte_and_takes_an_edit():
    raw = _msbt([["Press any button"], ["Hey!", Tag(1, 0, struct.pack("<i", 250)), Tag(1, 5, b"")]])
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks == [["Press any button", "Hey!{wait:250}{key_wait}"]]
    assert rules.save_data_to_json_obj(blocks, names) == raw
    blocks[0][0] = "UA TEST"
    saved = Msbt(rules.save_data_to_json_obj(blocks, names))
    assert saved.messages[0] == ["UA TEST"]
    assert saved.messages[1] == Msbt(raw).messages[1]
