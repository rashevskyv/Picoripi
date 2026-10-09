"""Animal Crossing: New Horizons plugin without game data: named tags (colours, item forms), an MSBT and a
Yaz0-compressed MSBT (the keyboard's) that save back byte for byte with only the edited message re-encoded."""
import struct

from core.containers import yaz0
from plugins.animal_crossing_nh.rules import GameRules, TagManager
from plugins.animal_crossing_nh.tags import TAGS, from_editor, to_editor
from plugins.common.msbt import Msbt, Tag


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


def _forms(*words):
    return b"".join(struct.pack("<H", 2 * len(w)) + w.encode("utf-16-le") for w in words)


def test_system_tags_colours_and_item_forms_are_named():
    names = {name for name, _types, _desc in TAGS.values()}
    assert {"Ruby", "Size", "Color", "PageBreak", "Item7", "Item8", "Player0", "Var20"} <= names
    assert to_editor([Tag(0, 3, b"\x03\x00"), "Hi", Tag(0, 3, b"\xff\xff")]) == "{Color:Npc}Hi{Color:Reset}"
    he_she = Tag(50, 7, _forms("He", "She"))
    plural = Tag(50, 8, struct.pack("<H", 512) + _forms("years", "year", "years"))
    assert to_editor([he_she, plural]) == "{Item7:He:She}{Item8:512:years:year:years}"
    assert from_editor("{Item7:Він:Вона}") == [Tag(50, 7, _forms("Він", "Вона"))]


def test_an_msbt_saves_back_byte_for_byte_and_takes_an_edit():
    raw = _msbt([["Press "], [Tag(0, 2, b"\x64\x00"), "Hello", Tag(0, 4, b"")]])
    rules = GameRules()
    assert rules.get_display_name() == "Animal Crossing: New Horizons (Switch)"
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks == [["Press ", "{Size:100}Hello{PageBreak}"]]
    assert rules.save_data_to_json_obj(blocks, names) == raw
    blocks[0][0] = "UA TEST "
    saved = Msbt(rules.save_data_to_json_obj(blocks, names))
    assert saved.messages[0] == ["UA TEST "]
    assert saved.messages[1] == Msbt(raw).messages[1]


def test_a_yaz0_msbt_stays_the_same_file_until_edited():
    raw = yaz0.compress(_msbt([["OK"], ["Space"]]))
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks == [["OK", "Space"]]
    assert rules.save_data_to_json_obj(blocks, names) == raw
    blocks[0][1] = "Пробіл"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved[:4] == b"Yaz0" and Msbt(yaz0.decompress(saved)).messages == [["OK"], ["Пробіл"]]


def test_the_tag_manager_accepts_this_games_tags_only():
    manager = TagManager()
    assert manager.is_tag_legitimate("{Color:Reset}")
    assert manager.is_tag_legitimate("{Item7:He:She}")
    assert not manager.is_tag_legitimate("{Font:4}")
