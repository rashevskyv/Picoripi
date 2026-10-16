"""Silent Hill (PAL disc) text: map overlays with high text bytes and the ITEM_*.BIN tables.

Synthetic bytes only: the layouts are built here at the PAL link bases the port uses.
"""
import struct

from plugins.silent_hill_ps1 import doc

MESSAGE_TABLE = 0x100


def pal_overlay(messages, size=0x400):
    out = bytearray(size)
    out[0x34:0x38] = struct.pack("<I", doc.PAL_OVERLAY_BASE + MESSAGE_TABLE)
    cursor = 0x200
    for i, text in enumerate(messages):
        pointer = doc.PAL_OVERLAY_BASE + cursor
        out[MESSAGE_TABLE + 4 * i:MESSAGE_TABLE + 4 * i + 4] = struct.pack("<I", pointer)
        raw = text + b"\0"
        out[cursor:cursor + len(raw)] = raw
        cursor += len(raw) + 2                       # two zero bytes of padding after each string
    return bytes(out)


def pal_items(count=10):
    out = bytearray(4 + 8 * count)
    cursor = 4 + 8 * count
    for k in range(count):
        for which, text in ((0, b"\x01Wi\x90\xa3 %d" % k), (4, b"\xc0\xc1 %d" % k)):
            raw = text + b"\0"
            out[cursor:cursor + len(raw)] = raw
            struct.pack_into("<I", out, 4 + 8 * k + which, doc.PAL_ITEM_BASE + cursor)
            cursor += len(raw)
    return bytes(out)


def test_pal_overlay_messages_keep_their_high_bytes_and_round_trip():
    data = pal_overlay([b"\x9a\x8b\x90 one", b"two", b"\xd3\xd4", b"four"])
    groups = doc.parse(data)
    assert [g.label for g in groups] == ["messages"]
    texts = [slot.text for slot in groups[0].slots]
    assert len(texts) == 4
    assert texts[1] == "two"
    rebuilt, problems = doc.build(data, [texts])
    assert problems == []
    assert rebuilt == data


def test_pal_overlay_edit_within_room_changes_only_its_string():
    data = pal_overlay([b"\x9a\x8b\x90 one", b"two", b"\xd3\xd4", b"four"])
    groups = doc.parse(data)
    texts = [[slot.text for slot in groups[0].slots]]
    texts[0][1] = "UA"
    edited, problems = doc.build(data, texts)
    assert problems == []
    assert doc.parse(edited)[0].slots[1].text == "UA"
    assert doc.parse(edited)[0].slots[0].text == texts[0][0]


def test_pal_item_table_reads_names_and_descriptions_and_round_trips():
    data = pal_items()
    groups = doc.parse(data)
    assert [g.label for g in groups] == ["item names", "item descriptions"]
    assert len(groups[0].slots) == 10 and len(groups[1].slots) == 10
    texts = [[s.text for s in g.slots] for g in groups]
    rebuilt, problems = doc.build(data, texts)
    assert problems == []
    assert rebuilt == data


def test_pal_item_table_needs_a_minimum_of_names():
    short = pal_items(count=3)
    assert doc._pal_item_starts(short) is None
