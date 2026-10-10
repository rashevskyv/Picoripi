"""Animal Crossing 3DS plugin without game data: a UMSBT (several languages) opens as its English MSBT, saves back byte
for byte, grows only the English slot when edited, picks the right tag catalogue per file; UTF-8 and Latin-1 MSBT."""
import struct

from plugins.animal_crossing_3ds.rules import GameRules, umsbt_join, umsbt_split
from plugins.animal_crossing_3ds.tags import CODECS
from plugins.common.msbt import Msbt, Tag


class _Fake:
    endian, little, utf8 = "<", True, False


def _msbt(texts, encoding=1, fake=_Fake()):
    """A minimal little-endian MSBT with one TXT2 section (encoding 1 = UTF-16, 0 = one byte per character)."""
    bodies = [Msbt.encode_text(fake, tokens) for tokens in texts]
    offsets, at = [], 4 + 4 * len(bodies)
    for body in bodies:
        offsets.append(at)
        at += len(body)
    txt2 = struct.pack(f"<I{len(bodies)}I", len(bodies), *offsets) + b"".join(bodies)
    out = bytearray(b"MsgStdBn\xff\xfe\x00\x00" + bytes([encoding, 3, 1, 0]) + bytes(16))
    out += b"TXT2" + struct.pack("<I", len(txt2)) + bytes(8) + txt2
    out += b"\xab" * (-len(out) % 16)
    struct.pack_into("<I", out, 0x12, len(out))
    return bytes(out)


def _umsbt(*files):
    return umsbt_join(list(files), 0x30)


def test_a_umsbt_splits_into_its_languages_and_joins_back():
    english, spanish = _msbt([["Hello"]]), _msbt([["Hola"]])
    raw = _umsbt(english, spanish)
    assert struct.unpack_from("<IIII", raw, 0) == (0x30, len(english), 0x30 + len(english), len(spanish))
    assert umsbt_split(raw) == [english, spanish]
    assert umsbt_split(english) is None                       # a plain MSBT is not a UMSBT
    assert umsbt_split(b"\x30\x00\x00\x00" + bytes(60)) is None


def test_the_english_slot_opens_saves_back_and_grows_alone():
    english = _msbt([["Press "], [Tag(0, 2, b"\x64\x00"), "Hello", Tag(0, 4, b"")]])
    spanish = _msbt([["Pulsa "], ["Hola"]])
    raw = _umsbt(english, spanish)
    rules = GameRules()
    assert rules.get_display_name() == "Animal Crossing: New Leaf / Happy Home Designer (3DS)"
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks == [["Press ", "{size:100}Hello{pageBreak}"]]
    assert rules.save_data_to_json_obj(blocks, names) == raw
    blocks[0][0] = "UA TEST, a longer line "
    saved = rules.save_data_to_json_obj(blocks, names)
    slots = umsbt_split(saved)
    assert slots[1] == spanish
    assert Msbt(slots[0]).messages[0] == ["UA TEST, a longer line "]
    assert Msbt(slots[0]).messages[1] == Msbt(english).messages[1]
    assert struct.unpack_from("<I", saved, 8)[0] == 0x30 + len(slots[0])


def test_the_catalogue_is_picked_per_file():
    # Group 5 tag 0 has no arguments in New Leaf and two u16 in Happy Home Designer.
    rules = GameRules()
    rules.load_data_from_json_obj(_msbt([[Tag(5, 0, b""), "x"]]))
    assert rules.codec is CODECS["new_leaf"]
    blocks, _ = rules.load_data_from_json_obj(_msbt([[Tag(5, 0, b"\x03\x00\x00\x00"), "x"]]))
    assert rules.codec is CODECS["happy_home"]
    assert blocks == [["{delay:3}x"]]          # the same tag is Happy Home Designer's delay
    assert "{tag:" not in blocks[0][0]


def test_tags_have_the_msbt_editor_names_and_old_names_still_read():
    codec = CODECS["new_leaf"]
    delay, npc = Tag(7, 0, bytes([8, 0, 0, 0])), Tag(0, 3, bytes([4, 0]))
    assert codec.to_editor([delay, Tag(3, 37, b""), Tag(5, 7, b""), npc]) == "{delay:8}{anim37}{catchphrase}{color:NPC}"
    assert codec.from_editor("{G5_7}{Color:NPC}{PageBreak}{G7_0:8}") == [Tag(5, 7, b""), npc, Tag(0, 4, b""), delay]
    assert "MSBT tag 7:0" in codec.describe("{delay:8}")


def test_one_byte_msbt_files_read_and_rebuild():
    class Utf8(_Fake):
        utf8, byte_codec = True, "utf-8"

    raw = _msbt([["Cyrano\nSirrahno"], ["Ćma", Tag(1, 2, b"\x07\x00"), "x"]], encoding=0, fake=Utf8())
    msbt = Msbt(raw)
    assert msbt.utf8 and msbt.byte_codec == "utf-8"
    assert msbt.messages == [["Cyrano\nSirrahno"], ["Ćma", Tag(1, 2, b"\x07\x00"), "x"]]
    assert msbt.build(msbt.messages) == raw

    class Latin(Utf8):
        byte_codec = "latin-1"

    raw = _msbt([["Gorbach\xe9"], ["Tut\xfa"]], encoding=0, fake=Latin())
    msbt = Msbt(raw)
    assert msbt.byte_codec == "latin-1" and msbt.messages == [["Gorbach\xe9"], ["Tut\xfa"]]
    assert msbt.build(msbt.messages) == raw
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks == [["Gorbach\xe9", "Tut\xfa"]]
    assert rules.save_data_to_json_obj(blocks, names) == raw
