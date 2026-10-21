"""Conker: Live & Reloaded CAFF text: the dialogue strings are read, skipped keys are kept, writes and growth read back."""
import struct

import pytest

from plugins.conker_lr import caff_text


def _caff(texts, table=True):
    """A CAFF text file: header to 0x180 (section base), an LSBL block with its (id, value) table, the strings,
    then a key name that must be skipped. Table values are UTF-16 unit offsets from the first string."""
    head = bytearray(b"CAFF".ljust(0x180, b"\x00"))
    body_strings = [t.encode("utf-16le") + b"\x00\x00" for t in texts]
    records = []
    if table:
        offsets = []
        pos = 0
        for raw in body_strings:
            offsets.append(pos // 2)
            pos += len(raw)
        for index, value in enumerate(offsets):
            records.append(struct.pack("<HI", index, value))
        records.append(struct.pack("<HI", 0xFFFF, pos // 2))
    lsbl = bytearray(b"LSBL" + b"\x00" * 44)
    struct.pack_into("<I", lsbl, 32, len(texts))
    key = "cutscene_TEST_1".encode("utf-16le") + b"\x00\x00"
    body = bytes(lsbl) + b"".join(records) + b"".join(body_strings) + key
    data = bytearray(head) + bytearray(body)
    struct.pack_into("<I", data, 0x50, len(data) - 0x180)
    struct.pack_into("<I", data, 0x64, len(data) - 0x180)
    return bytes(data)


def test_the_dialogue_strings_are_read_and_keys_skipped():
    data = _caff(["Hello there", "Bye.", "...."])
    slots = caff_text.read_slots(data)
    assert [s.text for s in slots] == ["Hello there", "Bye.", "...."]
    assert [s.capacity for s in slots] == [22, 8, 8]
    assert caff_text.translatable(slots) == [0, 1]  # "...." has no letter: a code, not text


def test_writing_the_same_texts_gives_the_same_bytes():
    data = _caff(["Hello there", "Bye."])
    slots = caff_text.read_slots(data)
    assert caff_text.write_slots(data, [slots[0].text, slots[1].text]) == data


def test_a_shorter_and_a_longer_text_both_read_back():
    data = _caff(["Hello there", "Bye.", "...."])
    short = caff_text.write_slots(data, ["Hi", "OK"])
    assert [s.text for s in caff_text.read_slots(short)] == ["Hi", "OK", "...."]
    assert len(short) < len(data)
    long = caff_text.write_slots(data, ["Hello there, my dear friend", "Good bye for now, see you"])
    assert [s.text for s in caff_text.read_slots(long)] == ["Hello there, my dear friend", "Good bye for now, see you", "...."]
    assert len(long) > len(data)


def test_the_size_fields_and_the_table_follow_the_growth():
    data = _caff(["Hello there", "Bye."])
    grown = caff_text.write_slots(data, ["A much longer first line of text", "Bye."])
    assert struct.unpack_from("<I", grown, 0x50)[0] == len(grown) - 0x180
    assert struct.unpack_from("<I", grown, 0x64)[0] == len(grown) - 0x180
    lsbl = grown.find(b"LSBL")
    slots = caff_text.read_slots(grown)
    first = slots[0].offset
    # the table points at each new string start, and the end record just past the last string
    values = []
    pos = lsbl + 0x30
    while True:
        rid, value = struct.unpack_from("<HI", grown, pos)
        values.append((rid, value))
        pos += 6
        if rid == 0xFFFF:
            break
    assert [first + 2 * v for _, v in values[:-1]] == [s.offset for s in slots]
    last = slots[-1]
    assert values[-1] == (0xFFFF, (last.offset + last.capacity + 2 - first) // 2)


def test_a_file_without_caff_or_lsbl_is_refused():
    with pytest.raises(caff_text.CaffError):
        caff_text.read_slots(b"XXXX" + b"\x00" * 100)
    with pytest.raises(caff_text.CaffError):
        caff_text.read_slots(b"CAFF" + b"\x00" * 100)


def test_a_wrong_count_is_refused():
    data = bytearray(_caff(["One text"]))
    struct.pack_into("<I", data, data.find(b"LSBL") + 32, 5)
    with pytest.raises(caff_text.CaffError):
        caff_text.read_slots(bytes(data))
