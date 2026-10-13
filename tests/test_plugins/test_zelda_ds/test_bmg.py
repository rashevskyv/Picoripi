"""BMG message files of the DS Zelda games: byte-exact rebuild, edits, control codes, odd file sizes."""
import struct

import pytest

from plugins.zelda_ds.bmg import Bmg, BmgError, build, decode_text, encode_text


def utf16(text: str) -> bytes:
    return text.encode("utf-16-le") + b"\x00\x00"


def make_bmg(raws, lead=b"", extra_section=None, tail=b""):
    """A BMG with one INF1 entry per raw text (entry size 8: offset, 4 attribute bytes) and a DAT1 body."""
    body = bytearray(lead)
    offsets = []
    for raw in raws:
        offsets.append(len(body))
        body += raw
    inf = struct.pack("<HHI", len(offsets), 8, 1) + b"".join(
        struct.pack("<I", off) + b"\x00\x01\x03\x00" for off in offsets)
    sections = [(b"INF1", inf), (b"DAT1", bytes(body))]
    if extra_section:
        sections.append(extra_section)
    out = bytearray(b"MESGbmg1" + struct.pack("<II", 0, len(sections)) + struct.pack("<I", 2) + bytes(12))
    for magic, data in sections:
        out += magic + struct.pack("<I", 8 + len(data)) + data
    struct.pack_into("<I", out, 8, len(out))
    return bytes(out) + tail


def test_unchanged_file_comes_back_byte_for_byte():
    data = make_bmg([utf16("Link"), utf16("Hello\nthere")], lead=b"\x00\x00")
    assert build(data, {}) == data
    assert build(data, {0: "Link"}) == data


def test_texts_read_back_in_message_order():
    data = make_bmg([utf16("Link"), utf16("Hello\nthere")], lead=b"\x00\x00")
    assert Bmg(data).texts() == ["Link", "Hello\nthere"]


def test_edit_changes_only_that_message():
    raws = [utf16("first"), utf16("second"), utf16("third")]
    data = make_bmg(raws)
    out = build(data, {1: "second, longer now"})
    assert Bmg(out).texts() == ["first", "second, longer now", "third"]
    assert len(out) > len(data)
    assert build(out, {1: "second"}) != out  # the edit can be undone as well


def test_control_code_round_trip():
    text = "[tag:01:0a001400]Our story[tag:ff:00000300]Tetra[tag:ff:00000000]."
    raw = encode_text(text)
    assert decode_text(raw) == text
    assert raw[:2] == b"\x00\x00" or raw.endswith(b"\x00\x00")


def test_control_code_length_is_checked():
    with pytest.raises(BmgError):
        decode_text(b"\x1a\x00\x02\x01")  # length 2 is shorter than the code itself


def test_shared_place_keeps_the_other_text():
    raws = [utf16("same"), utf16("other")]
    data = make_bmg(raws)
    bmg = Bmg(data)
    # two messages point at the first text (one place in DAT1)
    inf_body = bytearray(bmg.sections[bmg.inf_index][1])
    struct.pack_into("<I", inf_body, 8 + 8, bmg.offsets[0])
    sections = [(b"INF1", bytes(inf_body)), (b"DAT1", bytes(bmg.sections[bmg.dat_index][1]))]
    out = bytearray(b"MESGbmg1" + struct.pack("<II", 0, 2) + struct.pack("<I", 2) + bytes(12))
    for magic, body in sections:
        out += magic + struct.pack("<I", 8 + len(body)) + body
    struct.pack_into("<I", out, 8, len(out))
    shared_file = bytes(out)
    assert Bmg(shared_file).texts() == ["same", "same"]
    edited = build(shared_file, {1: "changed"})
    assert Bmg(edited).texts() == ["same", "changed"]


def test_file_longer_than_its_size_field_keeps_its_tail():
    data = make_bmg([utf16("Link")], tail=b"\xaa\xbb\xcc\xdd")
    assert build(data, {}) == data


def test_size_field_longer_than_the_entry_is_read_and_written_back_unchanged():
    data = make_bmg([utf16("Link"), utf16("Zelda")])
    cut = data[:-4]  # the NitroFS entry is 4 bytes shorter than the size field says
    struct.pack_into("<I", bytearray(cut), 8, len(data))
    fixed = bytearray(cut)
    struct.pack_into("<I", fixed, 8, len(data))
    assert build(bytes(fixed), {}) == bytes(fixed)


def test_not_a_bmg_file_is_refused():
    with pytest.raises(BmgError):
        Bmg(b"RIFF" + b"\x00" * 64)


def test_nul_in_a_text_is_refused():
    with pytest.raises(BmgError):
        encode_text("bad\x00text")
