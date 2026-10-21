"""Conker: Live & Reloaded CAFF text: the dialogue strings are read, skipped keys are kept, writes keep the size."""
import struct

import pytest

from plugins.conker_lr import caff_text


def _caff(texts):
    head = bytearray(b"CAFF".ljust(0x40, b"\x00"))
    lsbl = bytearray(b"LSBL" + b"\x00" * 44)
    struct.pack_into("<I", lsbl, 32, len(texts))
    body = b"".join(t.encode("utf-16le") + b"\x00\x00" for t in texts)
    key = "cutscene_TEST_1".encode("utf-16le") + b"\x00\x00"
    return bytes(head + lsbl + body + key)


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


def test_a_shorter_text_is_padded_and_a_longer_one_is_refused():
    data = _caff(["Hello there", "Bye."])
    out = caff_text.write_slots(data, ["Hi", "OK"])
    assert [s.text for s in caff_text.read_slots(out)] == ["Hi", "OK"]
    assert len(out) == len(data)
    with pytest.raises(caff_text.SlotOverflow) as info:
        caff_text.write_slots(data, ["Hello there, my friend", "OK"])
    assert info.value.index == 0


def test_a_file_without_caff_or_lsbl_is_refused():
    with pytest.raises(caff_text.CaffError):
        caff_text.read_slots(b"XXXX" + b"\x00" * 100)
    with pytest.raises(caff_text.CaffError):
        caff_text.read_slots(b"CAFF" + b"\x00" * 100)


def test_a_wrong_count_is_refused():
    data = bytearray(_caff(["One text"]))
    struct.pack_into("<I", data, 0x40 + 32, 5)
    with pytest.raises(caff_text.CaffError):
        caff_text.read_slots(bytes(data))
