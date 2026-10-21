"""Conker: Live & Reloaded CAFF text: the table gives the strings, keys are skipped, writes and growth read back."""
import struct

import pytest

from plugins.conker_lr import caff_text

KEY = "cutscene_TEST_1"


def _caff(texts):
    """A CAFF text file: header to 0x180 (section base), an LSBL block with its table at LSBL+0x24, the strings, then a
    key name stored as the last table entry. Table values are UTF-16 unit offsets from the first string."""
    head = bytearray(b"CAFF".ljust(0x180, b"\x00"))
    entries = list(texts) + [KEY]
    raws = [t.encode("utf-16le") + b"\x00\x00" for t in entries]
    offsets, pos = [], 0
    for raw in raws:
        offsets.append(pos // 2)
        pos += len(raw)
    records = [struct.pack("<HI", index, value) for index, value in enumerate(offsets)]
    records.append(struct.pack("<HI", 0xFFFF, pos // 2))
    lsbl = bytearray(b"LSBL" + b"\x00" * 32)
    struct.pack_into("<I", lsbl, 32, len(entries))
    body = bytes(lsbl) + b"".join(records) + b"".join(raws)
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
    # the table points at each new entry start; the end record is just past the last entry (the key)
    values = []
    pos = lsbl + 0x24
    while True:
        rid, value = struct.unpack_from("<HI", grown, pos)
        values.append((rid, value))
        pos += 6
        if rid == 0xFFFF:
            break
    entry_starts = [first + 2 * v for _, v in values[:-1]]
    assert entry_starts[:2] == [s.offset for s in slots]
    key_start = entry_starts[-1]
    assert values[-1] == (0xFFFF, (key_start + 2 * len(KEY) + 2 - first) // 2)


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


def _with_index(data: bytes, units):
    """Append a block index after the strings: header (0, count), then one (u16, u16, u32 unit) entry per table entry.
    LSBL+0x10 points at it, as in the game's files."""
    lsbl = data.find(b"LSBL")
    index_at = len(data)
    out = bytearray(data) + bytearray(struct.pack("<II", 0, len(units)))
    for k, unit in enumerate(units):
        out += struct.pack("<HHI", k, k + 4, unit)
    struct.pack_into("<I", out, lsbl + 0x10, index_at - lsbl)
    struct.pack_into("<I", out, 0x50, len(out) - 0x180)
    struct.pack_into("<I", out, 0x64, len(out) - 0x180)
    return bytes(out)


def _index_units(data: bytes):
    lsbl = data.find(b"LSBL")
    start = lsbl + struct.unpack_from("<I", data, lsbl + 0x10)[0]
    count = struct.unpack_from("<I", data, lsbl + 32)[0]
    return [struct.unpack_from("<I", data, start + 8 + 8 * k + 4)[0] for k in range(count)]


def test_the_block_index_units_follow_the_growth():
    # The index holds unit offsets that point inside strings (line starts). It is not text: it must not be read as
    # dialogue. After a string grows, the units must still point at the same characters, or the game reads the wrong
    # text (the multiplayer menu froze when such units were left behind).
    base = _caff(["Hello there", "Bye.", "...."])
    slots = caff_text.read_slots(base)
    first = slots[0].offset
    lsbl = base.find(b"LSBL")
    key_unit = struct.unpack_from("<I", base, lsbl + 0x24 + 6 * 3 + 2)[0]
    units = [0, (slots[1].offset - first) // 2 + 1, (slots[2].offset - first) // 2, key_unit]
    data = _with_index(base, units)
    assert _index_units(data) == units
    assert [s.text for s in caff_text.read_slots(data)] == ["Hello there", "Bye.", "...."]
    grown = caff_text.write_slots(data, ["A much longer first line of text", "Bye."])
    new_slots = caff_text.read_slots(grown)
    new_first = new_slots[0].offset
    new_units = _index_units(grown)
    assert new_units[0] == 0
    assert grown[new_first + 2 * new_units[1]:new_first + 2 * new_units[1] + 2] == "y".encode("utf-16le")
    assert new_first + 2 * new_units[2] == new_slots[2].offset
    assert _index_units(caff_text.write_slots(data, ["Hello there", "Bye."])) == units


def test_the_pointer_28_bytes_before_the_index_follows_the_index():
    # In the game's files LSBL+0x1C is LSBL+0x10 minus 0x1C. Growth moves the index; the pair must stay related.
    base = _caff(["Hello there", "Bye.", "...."])
    slots = caff_text.read_slots(base)
    first = slots[0].offset
    lsbl = base.find(b"LSBL")
    key_unit = struct.unpack_from("<I", base, lsbl + 0x24 + 6 * 3 + 2)[0]
    units = [0, (slots[1].offset - first) // 2 + 1, (slots[2].offset - first) // 2, key_unit]
    data = bytearray(_with_index(base, units))
    struct.pack_into("<I", data, lsbl + 0x1C, struct.unpack_from("<I", data, lsbl + 0x10)[0] - 0x1C)
    grown = caff_text.write_slots(bytes(data), ["A much longer first line of text", "Bye."])
    assert struct.unpack_from("<I", grown, lsbl + 0x1C)[0] == struct.unpack_from("<I", grown, lsbl + 0x10)[0] - 0x1C
