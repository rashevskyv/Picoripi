"""Rune Factory 4 (3DS) plugin: TEXT tables (synthetic and the real game's romfs when it is unpacked here)."""
import romhacking_root
import struct

import pytest

from plugins.rune_factory_4 import text
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "rune_factory_4"
ROMFS = romhacking_root.under('Rune Factory\\4\\3DS\\romfs')


def make_table(strings) -> bytes:
    blobs = [s.encode("utf-8") for s in strings]
    at = 8 + 8 * len(blobs)
    head, body = b"TEXT" + struct.pack("<I", len(blobs)), b""
    for blob in blobs:
        head += struct.pack("<II", len(blob), at + len(body))
        body += blob + b"\0"
    return head + body


SAMPLE = make_table(["Are you turning in for the night?", "Good night,\n＠しゅじんこうくん＠.", "", "＋Lumber＋: ＠０＠"])


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert ".eng" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_table_texts_and_rebuild():
    table = text.Table(SAMPLE)
    assert table.texts()[1] == "Good night,\n＠しゅじんこうくん＠."
    assert table.build(table.texts()) == SAMPLE
    changed = text.Table(table.build(["Short", "A much longer replacement line", "now filled", "x"]))
    assert changed.texts() == ["Short", "A much longer replacement line", "now filled", "x"]
    with pytest.raises(ValueError):
        table.build(["too few"])


def test_variables_are_tags():
    from plugins.rune_factory_4.tag_manager import TAG_RE
    assert TAG_RE.findall("Hi ＠しゅじんこうくん＠, ＋Lumber＋") == ["＠しゅじんこうくん＠", "＋", "＋"]


@pytest.mark.skipif(not ROMFS.is_dir(), reason="Rune Factory 4 (3DS) is not unpacked here")
def test_every_english_table_of_the_game_round_trips_byte_for_byte():
    files = [p for p in ROMFS.rglob("*.eng") if "コピー" not in p.name]
    assert len(files) >= 25
    total = 0
    for path in files:
        raw = path.read_bytes()
        table = text.Table(raw)
        assert table.build(table.texts()) == raw, path
        total += len(table.texts())
    assert total > 100000
