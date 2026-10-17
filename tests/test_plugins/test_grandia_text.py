"""Grandia II dialogue (plugins/grandia/text.py, archive.py): tags, message records and an AFS archive of messages,
synthetic and, when the owner's disc is on disk, one real MAP archive. Every unchanged archive comes back byte for byte."""
import os

import pytest

import romhacking_root

from core.containers import afs
from core.containers.gdrom import GdRomImage, GdRomStream
from plugins.grandia import archive, text
from test_core.test_afs_container import make_afs

REAL_CUE = romhacking_root.under(r"Grandia\Grandia II\Dreamcast\ISO\Grandia II (USA).cue")


def _record(header_pad: bytes, body: bytes) -> bytes:
    return text.MARK + b"\x08\x24\xa1\x02\x00\x03\x10\x16\x03" + header_pad + text.TEXT_START + body


def test_every_byte_survives_the_tag_text():
    body = bytes(range(256))
    assert text.from_text(text.to_text(body)) == body


def test_braces_are_tags_and_plain_text_is_kept():
    assert text.to_text(b"a{b}") == "a{7B}b{7D}"
    assert text.to_text(b"Your Maj esty.\x00") == "Your Maj esty.{00}"


def test_a_character_without_a_glyph_is_refused():
    with pytest.raises(ValueError):
        text.from_text("Привіт")


def test_a_record_with_a_long_header_is_not_a_message():
    binary = text.MARK + b"\x00" * 60 + text.TEXT_START + b"Looks like text"
    assert text.message_parts(binary) is None


def test_a_record_with_a_binary_body_is_not_a_message():
    binary = text.MARK + b"\x08\x01" + text.TEXT_START + bytes(range(0x80, 0xC0)) * 4
    assert text.message_parts(binary) is None


def test_a_message_record_splits_into_header_and_body():
    header, body = text.message_parts(_record(b"", b"Hello\x00there"))
    assert header.endswith(text.TEXT_START)
    assert body == b"Hello\x00there"


def test_a_synthetic_archive_of_messages_reads_and_rebuilds():
    entry = b"\x01\x02\x03" + _record(b"", b"Hello \x1fworld") + _record(b"", b"Second line.")
    data = make_afs([entry, b"binary-without-marker"])
    texts, names = archive.blocks(data)
    assert texts == ["Hello {1F}world", "Second line."]
    assert names["0"].startswith("entry 0")
    same, missing = archive.build(data, texts)
    assert same == data and not missing
    edited, missing = archive.build(data, ["Hello, Ukraine, longer than before.", "Second line."])
    assert archive.blocks(edited)[0][0] == "Hello, Ukraine, longer than before."
    assert afs.parse(edited)[1].size == len(b"binary-without-marker")
    assert missing == set()


def test_an_unknown_character_is_written_as_a_question_mark_and_reported():
    entry = _record(b"", b"abc")
    data = make_afs([entry])
    edited, missing = archive.build(data, ["ab\u0456c"])
    assert archive.blocks(edited)[0][0] == "ab?c"
    assert missing == {"\u0456"}


@pytest.mark.skipif(not os.path.isfile(REAL_CUE), reason="the owner's Grandia II image is not on disk")
def test_a_real_map_archive_round_trips_and_takes_a_longer_line():
    stream = GdRomStream(REAL_CUE)
    try:
        image = GdRomImage(stream)
        data = image.read({e.path: e for e in image.entries()}["files/MAP/A000.AFS"])
    finally:
        stream.close()
    texts, _names = archive.blocks(data)
    assert len(texts) >= 20
    same, _missing = archive.build(data, texts)
    assert same == data
    edited = list(texts)
    edited[0] = "UA TEST: a longer line that the original text never had, with more words."
    out, _missing = archive.build(data, edited)
    assert archive.blocks(out)[0][0] == edited[0]
    assert len(out) % 0x800 == 0
