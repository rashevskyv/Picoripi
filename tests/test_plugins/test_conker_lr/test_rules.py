"""Conker: Live & Reloaded (Xbox) plugin: loads, JSON texts round-trip, the English text build, and the validator.

Every game file here is synthetic (built in the test); no disc data is in the repository.
"""
import json
import struct

import pytest

from plugins.testing import check_loads, check_validator

from plugins.conker_lr import caff_text
from plugins.conker_lr.rules import FORMAT_ID, GameRules, ORIGINAL_DIR, TARGET_FILES

PLUGIN = "conker_lr"
FOLDER_REL = "dvddata/aid/text/English/Frontend/default.bin"


def _caff(texts, extra=b""):
    """A minimal CAFF text file: an LSBL block with its table (one entry per text, then a key to skip), the strings."""
    head = bytearray(b"CAFF".ljust(0x180, b"\x00"))
    entries = list(texts) + ["cutscene_TEST_1"]
    raws = [t.encode("utf-16le") + b"\x00\x00" for t in entries]
    records, pos = [], 0
    for index, raw in enumerate(raws):
        records.append(struct.pack("<HI", index, pos // 2))
        pos += len(raw)
    records.append(struct.pack("<HI", 0xFFFF, pos // 2))
    lsbl = bytearray(b"LSBL" + b"\x00" * 32)
    struct.pack_into("<I", lsbl, 32, len(entries))
    data = bytearray(head) + bytearray(lsbl) + b"".join(records) + b"".join(raws) + extra
    # the header sizes and the checksum as the game checks them
    struct.pack_into("<I", data, 0x34, len(data) - 0x180)
    struct.pack_into("<I", data, 0x50, len(data) - 0x180)
    struct.pack_into("<I", data, 0x64, len(data) - 0x180)
    struct.pack_into("<I", data, 0x14, caff_text.caff_hash(bytes(data)))
    return bytes(data)


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_a_json_text_round_trips_unchanged():
    rules = GameRules()
    obj = {"format": FORMAT_ID, "file": FOLDER_REL, "strings": ["Hi, Berri!", "Bye."]}
    blocks, names = rules.load_data_from_json_obj(obj)
    assert blocks == [["Hi, Berri!", "Bye."]]
    assert names == {"0": FOLDER_REL}
    assert rules.save_data_to_json_obj(blocks, names) == obj


def test_a_foreign_json_is_refused():
    rules = GameRules()
    try:
        rules.load_data_from_json_obj({"strings": []})
    except ValueError:
        return
    raise AssertionError("a JSON without the format id must be refused")


def test_only_the_english_text_files_are_wanted():
    from plugins.conker_lr.rules import _wanted

    assert _wanted("dvddata/aid/text/English/Frontend/default.bin")
    assert not _wanted("dvddata/aid/text/French/Frontend/default.bin")
    assert not _wanted("dvddata/aid/text/English/UIFrontend/default.bin")
    assert _wanted("default.xbe")
    assert not _wanted("dashupdate.xbe")


def test_build_writes_the_changed_file_and_grows_a_longer_line(tmp_path):
    source = tmp_path / "source"
    translation = tmp_path / "translation"
    output = tmp_path / "output"
    original = source / ORIGINAL_DIR / FOLDER_REL
    original.parent.mkdir(parents=True)
    original.write_bytes(_caff(["Hello there", "Bye"]))
    (translation / "text").mkdir(parents=True)
    obj = {"format": FORMAT_ID, "file": FOLDER_REL, "strings": ["Hi there", "Bai"]}
    (translation / "text" / "Frontend.json").write_text(json.dumps(obj), encoding="utf-8")

    rules = GameRules()
    rules.build_target(TARGET_FILES, str(source), str(translation), str(output), lambda *a: None, lambda: False)
    built = (output / FOLDER_REL).read_bytes()
    assert [s.text for s in caff_text.read_slots(built)] == ["Hi there", "Bai"]

    obj["strings"] = ["This text is far longer than its original slot was", "Bai"]
    (translation / "text" / "Frontend.json").write_text(json.dumps(obj), encoding="utf-8")
    rules.build_target(TARGET_FILES, str(source), str(translation), str(tmp_path / "o2"),
                       lambda *a: None, lambda: False)
    grown = (tmp_path / "o2" / FOLDER_REL).read_bytes()
    assert [s.text for s in caff_text.read_slots(grown)] == ["This text is far longer than its original slot was", "Bai"]


def _xbe_with_title(title_id):
    """A synthetic XBE with the certificate and the subtitle box sites holding their original bytes."""
    from plugins.conker_lr import xbe_box

    base = 0x10000
    xbe = bytearray(0x40000)
    xbe[0:4] = b"XBEH"
    struct.pack_into("<I", xbe, 0x104, base)
    struct.pack_into("<I", xbe, 0x118, base + 0x800)
    struct.pack_into("<I", xbe, 0x800 + 8, title_id)
    sections = [(0xD0000, 0x20000, 0x1000, 0x20000), (0x640000, 0x10000, 0x21000, 0x10000)]
    struct.pack_into("<I", xbe, 0x11C, len(sections))
    struct.pack_into("<I", xbe, 0x120, base + 0x200)
    for index, (va, vsize, raw, rsize) in enumerate(sections):
        struct.pack_into("<IIIII", xbe, 0x200 + 0x38 * index, 0, va, vsize, raw, rsize)
    for va in xbe_box.WRAP_VAS:
        struct.pack_into("<I", xbe, xbe_box.va_to_offset(bytes(xbe), va, 4), xbe_box.ORIGINAL_WRAP)
    for va in xbe_box.LINE_VAS:
        xbe[xbe_box.va_to_offset(bytes(xbe), va, 1)] = xbe_box.ORIGINAL_LINES
    for va in xbe_box.HEIGHT_LOAD_VAS:
        struct.pack_into("<I", xbe, xbe_box.va_to_offset(bytes(xbe), va, 4), xbe_box.HEIGHT_CONST_VA)
    struct.pack_into("<f", xbe, xbe_box.va_to_offset(bytes(xbe), xbe_box.HEIGHT_CONST_VA, 4), 160.0)
    struct.pack_into("<f", xbe, xbe_box.va_to_offset(bytes(xbe), 0x640100, 4), 240.0)
    return bytes(xbe)


def test_the_box_build_writes_a_patched_copy_and_refuses_another_xbe(tmp_path):
    from plugins.conker_lr import xbe_box
    from plugins.conker_lr.config import BOX_HEIGHT, BOX_LINE_LIMIT, BOX_WRAP_CHARS
    from plugins.conker_lr.rules import TARGET_BOX, TITLE_ID, XBE_NAME

    source = tmp_path / "source"
    (source / ORIGINAL_DIR).mkdir(parents=True)
    (source / ORIGINAL_DIR / XBE_NAME).write_bytes(_xbe_with_title(TITLE_ID))
    output = tmp_path / "output"
    output.mkdir()
    rules = GameRules()
    built = rules.build_target(TARGET_BOX, str(source), str(tmp_path), str(output), lambda *a: None, lambda: False)
    patched = (output / XBE_NAME).read_bytes()
    assert built == str(output / XBE_NAME)
    assert patched[xbe_box.va_to_offset(patched, xbe_box.LINE_VAS[0], 1)] == BOX_LINE_LIMIT
    assert struct.unpack_from("<I", patched, xbe_box.va_to_offset(patched, xbe_box.WRAP_VAS[0], 4))[0] == BOX_WRAP_CHARS
    load = struct.unpack_from("<I", patched, xbe_box.va_to_offset(patched, xbe_box.HEIGHT_LOAD_VAS[0], 4))[0]
    height = struct.unpack_from("<f", patched, xbe_box.va_to_offset(patched, load, 4))[0]
    assert height == (xbe_box.scaled_height(BOX_LINE_LIMIT) if BOX_HEIGHT else 160.0)

    (source / ORIGINAL_DIR / XBE_NAME).write_bytes(_xbe_with_title(0x12345678))
    with pytest.raises(ValueError):
        rules.build_target(TARGET_BOX, str(source), str(tmp_path), str(tmp_path / "o2"), lambda *a: None, lambda: False)
