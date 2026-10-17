"""Grandia II fixed-field text (plugins/grandia/fields.py): word rule, byte budgets, refusals, and the owner's battle and
item archives when the disc is on disk (skipped otherwise). An unchanged archive comes back byte for byte."""
import os

import pytest

import romhacking_root

from core.containers import afs
from core.containers.gdrom import GdRomImage, GdRomStream
from plugins.grandia import fields
from test_core.test_afs_container import make_afs

REAL_CUE = romhacking_root.under(r"Grandia\Grandia II\Dreamcast\ISO\Grandia II (USA).cue")


def _table():
    # a record: 2 stats bytes, a right-aligned name in 12 bytes, a binary tail, then a description in 26 bytes
    name = b"  Burnflame"
    desc = b"Attack enemy with fire".ljust(26)
    return b"\x02\x01\x00\x10" + name + b"\x05\x00\x06\x04\x28" + desc + b"\x00"


def test_words_are_text_and_fragments_are_not():
    assert fields._is_text(b"Attack enemy with fireballs")
    assert fields._is_text(b"Valmar's Tongue")
    assert fields._is_text(b"KAZUYUKI OHATA")
    assert fields._is_text(b"+50 to +800 Maximum HP")
    for junk in (b"NJCM", b"kqt", b"AAAA", b"uCpt", b"Acd", b"Bun", b"fff?", b"PVRT"):
        assert not fields._is_text(junk), junk


def test_a_table_gives_its_names_and_descriptions_with_budgets():
    found = fields.slots(_table())
    texts = [s.text for s in found]
    assert texts == ["Burnflame", "Attack enemy with fire"]
    assert found[0].budget == len(b"  Burnflame")
    assert found[0].lead == 2


def test_an_unchanged_table_is_byte_exact_and_an_edit_fits_its_budget():
    blob = _table()
    found = fields.slots(blob)
    out, refused = fields.write(blob, [s.text for s in found], found)
    assert out == blob and not refused
    out, refused = fields.write(blob, ["Hellfire", found[1].text], found)
    assert not refused
    assert fields.slots(out)[0].text == "Hellfire"
    assert len(out) == len(blob)


def test_a_text_longer_than_its_field_is_refused_and_keeps_the_original():
    blob = _table()
    found = fields.slots(blob)
    out, refused = fields.write(blob, ["Hellfire of the sky", found[1].text], found)
    assert refused == {0}
    assert fields.slots(out)[0].text == "Burnflame"


def test_an_edit_the_editor_would_not_find_again_is_refused():
    blob = _table()
    found = fields.slots(blob)
    out, refused = fields.write(blob, ["Hi", found[1].text], found)   # two letters: not a word
    assert refused == {0} and out == blob


def test_an_archive_of_fields_reads_builds_and_keeps_empty_entries():
    entry = _table()
    data = make_afs([entry, b"", b"\x00" * 16])
    texts, names = fields.archive_blocks(data)
    assert texts == ["Burnflame", "Attack enemy with fire"]
    assert names["0"] == "entry 0 field 0"
    same, refused, count = fields.archive_build(data, texts)
    assert same == data and not refused and count == 2
    edited, refused, _ = fields.archive_build(data, ["Hellfire", "Attack enemy with fire"])
    assert fields.archive_blocks(edited)[0][0] == "Hellfire"
    assert afs.parse(edited)[1].size == 0


def test_message_archives_are_told_apart_from_field_archives():
    assert not fields.has_messages(make_afs([_table()]))
    assert fields.has_messages(make_afs([b"\x17\x00\x02\x08\x24\x17\x01Hello there"]))


@pytest.mark.skipif(not os.path.isfile(REAL_CUE), reason="the owner's Grandia II image is not on disk")
def test_the_real_battle_and_item_archives_round_trip_byte_for_byte():
    stream = GdRomStream(REAL_CUE)
    try:
        image = GdRomImage(stream)
        by_path = {e.path: e for e in image.entries()}
        for path in ("files/BTL/SYS.AFS", "files/WINDOW/XLS_DATA.AFS"):
            data = image.read(by_path[path])
            texts, _names = fields.archive_blocks(data)
            assert len(texts) > 20, path
            same, refused, count = fields.archive_build(data, texts)
            assert same == data and not refused and count == len(texts), path
    finally:
        stream.close()
