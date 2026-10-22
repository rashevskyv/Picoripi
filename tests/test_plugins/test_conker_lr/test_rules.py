"""Conker: Live & Reloaded (Xbox) plugin: loads, JSON texts round-trip, the English text build, and the validator.

Every game file here is synthetic (built in the test); no disc data is in the repository.
"""
import json
import struct

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
    assert not _wanted("default.xbe")


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
