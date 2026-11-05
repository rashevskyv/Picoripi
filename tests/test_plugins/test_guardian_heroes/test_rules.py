"""Guardian Heroes plugin: the script codec, the file round trip, the STFS reader, unpack and build.

Every game file here is synthetic (built in the test); no game data is in the repository. With the environment
variable GUARDIAN_HEROES_SCRIPT set to a real ``script_eng.mrg`` the last test also checks that file.
"""
import json
import os
import struct

import pytest

from plugins.guardian_heroes import script, stfs
from plugins.guardian_heroes.problems import long_lines
from plugins.guardian_heroes.rules import (
    FORMAT_ID, GameRules, ORIGINAL_DIR, ROLE_PACKAGE, SCRIPT_PATH, TARGET_FILES, TEXT_JSON_DIR, TEXT_JSON_NAME,
)
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "guardian_heroes"
NOVEL = "{E100:0039}{F006}{F900}We were crowned in\n{F900}laurels of white, and\n{F078}{F900} {F800}{F006}{F900}Done."
BUBBLE = "{E000:0001}{F203}The royal knights are coming!{F800}{F202}You have to go. Now!"


def _make_script(scenes):
    """A script file as the game ships it: header, 32-byte records, 4-byte aligned entries."""
    parsed = script.Script(b"\0" * 28, [b"\0" * 24] * len(scenes), [list(s) for s in scenes], b"")
    return script.build(parsed)


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_a_script_json_survives_load_and_save():
    check_round_trip(PLUGIN, {"format": FORMAT_ID, "file": SCRIPT_PATH, "scenes": [[NOVEL, BUBBLE], ["Hi."]]})


def test_a_foreign_json_is_refused():
    with pytest.raises(ValueError):
        GameRules().load_data_from_json_obj({"format": "other/1", "scenes": []})


def test_the_words_of_a_string_become_text_and_back():
    words = [0xE100, 0x0039, 0xF006, 0xF900, ord("A"), 0xFF0C, 0x20, ord("b"), 0xF700, 0xF900, ord("C"), 0xFFFF]
    text = script.decode(words)
    assert text == "{E100:0039}{F006}{F900}A, b\n{F900}C"
    assert script.encode(text) == words


def test_a_word_without_a_text_form_stays_a_tag_and_survives():
    words = [0x2C, 0x7B, 0x7D, 0x0A, 0xF123, 0xE200, 0xFFFF]   # plain comma, brackets, a control char, the last code has no parameter
    text = script.decode(words)
    assert text == "{002C}{007B}{007D}{000A}{F123}{E200}"
    assert script.encode(text) == words


def test_a_string_must_end_with_the_closing_word():
    with pytest.raises(script.ScriptError):
        script.decode([ord("A")])


def test_an_unknown_bracket_and_a_wide_character_are_refused():
    with pytest.raises(script.ScriptError):
        script.encode("a {NOPE} b")
    with pytest.raises(script.ScriptError):
        script.encode("\U0001F600")


def test_ukrainian_letters_are_written_as_their_code_units():
    assert script.encode("Привіт, світе!")[:3] == [0x041F, 0x0440, 0x0438]


def test_a_script_file_rebuilds_byte_for_byte_and_a_changed_line_moves_only_what_follows():
    data = _make_script([[NOVEL, BUBBLE], ["Hi."], [BUBBLE]])
    parsed = script.parse(data)
    assert script.build(parsed) == data
    assert parsed.strings[0] == [NOVEL, BUBBLE]
    edited = script.build(script.with_strings(parsed, [[NOVEL.replace("crowned", "CROWNED OVER"), BUBBLE], ["Hi."], [BUBBLE]]))
    reread = script.parse(edited)
    assert reread.strings[0][0].count("CROWNED OVER") == 1
    assert reread.strings[1:] == [["Hi."], [BUBBLE]]
    assert len(edited) > len(data)


def test_a_translation_with_other_string_counts_is_refused():
    parsed = script.parse(_make_script([["a", "b"], ["c"]]))
    with pytest.raises(script.ScriptError):
        script.with_strings(parsed, [["a"], ["c"]])
    with pytest.raises(script.ScriptError):
        script.with_strings(parsed, [["a", "b"]])


def test_a_damaged_script_is_refused():
    data = bytearray(_make_script([["a"], ["b"]]))
    struct.pack_into(">I", data, 0x20 + 32, 0x1234)   # entry 1 no longer starts after entry 0
    with pytest.raises(script.ScriptError):
        script.parse(bytes(data))
    with pytest.raises(script.ScriptError):
        script.parse(b"\0" * 8)


def _stfs_package(path, title_id, files):
    """A tiny STFS package: a file table of one block, then one data block per file (all consecutive).

    A name like ``media/script_eng.mrg`` gets a folder entry ``media`` as its parent.
    """
    base = 0xB000
    folders, entries = {}, []
    for name in files:
        folder, _, leaf = name.rpartition("/")
        if folder and folder not in folders:
            folders[folder] = len(entries)
            entries.append((folder, True, -1, b""))
        entries.append((leaf, False, folders.get(folder, -1), files[name]))
    blocks, table, next_block = {}, b"", 1
    for leaf, is_folder, parent, data in entries:
        count = 0 if is_folder else max(1, -(-len(data) // 0x1000))
        entry = bytearray(64)
        entry[:len(leaf)] = leaf.encode("latin-1")
        entry[0x28] = len(leaf) | (0x80 if is_folder else 0x40)
        entry[0x29:0x2C] = count.to_bytes(3, "little")
        entry[0x2F:0x32] = (0 if is_folder else next_block).to_bytes(3, "little")
        struct.pack_into(">hI", entry, 0x32, parent, len(data))
        table += bytes(entry)
        for i in range(count):
            blocks[next_block + i] = data[i * 0x1000:(i + 1) * 0x1000]
        next_block += count
    blocks[0] = table
    header = bytearray(base)
    header[:4] = b"LIVE"
    struct.pack_into(">I", header, 0x340, 0xAD0E)             # header size: the data starts at 0xB000
    struct.pack_into(">I", header, 0x360, title_id)
    header[0x379:0x379 + 8] = bytes([0x24, 0, 1]) + (1).to_bytes(2, "little") + (0).to_bytes(3, "little")
    body = bytearray()
    for n in range(next_block):
        # data block n sits at raw block n + 1: one hash table block stands in front of the first 0xAA blocks
        while len(body) < (n + 1) * 0x1000:
            body += b"\0" * 0x1000
        body += blocks[n].ljust(0x1000, b"\0")
    path.write_bytes(bytes(header) + bytes(body))


def test_the_stfs_reader_lists_and_reads_files_and_names_the_title(tmp_path):
    package = tmp_path / "pkg"
    payload = bytes(range(256)) * 20
    _stfs_package(package, 0x58410B2B, {"a.bin": b"abc", "media/script.mrg": payload})
    assert stfs.title_id(str(package)) == 0x58410B2B
    with stfs.Package(str(package)) as opened:
        assert dict(opened.files()) == {"a.bin": 3, "media/script.mrg": len(payload)}
        assert opened.read("MEDIA/script.mrg") == payload
        with pytest.raises(stfs.StfsError):
            opened.read("missing")
    assert stfs.title_id(str(tmp_path / "nothing")) is None


def _unpack(tmp_path, source):
    rules = GameRules()
    root = tmp_path / "unpacked"
    root.mkdir(parents=True)
    rules.unpack_sources({ROLE_PACKAGE: str(source)}, str(root), lambda p, t: None, lambda: False)
    return rules, root


def test_a_package_is_identified_and_unpacked_to_json_and_the_original(tmp_path):
    data = _make_script([[NOVEL, BUBBLE], ["Hi."]])
    package = tmp_path / "pkg"
    _stfs_package(package, 0x58410B2B, {"media/script_eng.mrg": data})
    assert GameRules().identify_source(str(package)) == {"role": ROLE_PACKAGE, "platform": "x360"}
    other = tmp_path / "other"
    _stfs_package(other, 0x12345678, {"x": b"1"})
    assert GameRules().identify_source(str(other)) is None
    folder = tmp_path / "game"
    (folder / "media").mkdir(parents=True)
    (folder / "media" / "script_eng.mrg").write_bytes(data)
    assert GameRules().identify_source(str(folder)) == {"role": ROLE_PACKAGE, "platform": "x360"}
    for source in (folder, package):
        rules, root = _unpack(tmp_path / ("from_" + source.name), source)
        assert (root / ORIGINAL_DIR / "media" / "script_eng.mrg").read_bytes() == data
    obj = json.loads((root / TEXT_JSON_DIR / TEXT_JSON_NAME).read_text(encoding="utf-8"))
    assert obj["format"] == FORMAT_ID and obj["scenes"] == [[NOVEL, BUBBLE], ["Hi."]]
    assert rules.includes_source_file(f"{TEXT_JSON_DIR}/{TEXT_JSON_NAME}")
    assert not rules.includes_source_file("original/media/script_eng.mrg")


def test_the_build_without_edits_is_identical_and_one_edited_line_changes_the_file(tmp_path):
    data = _make_script([[NOVEL, BUBBLE], ["Hi."], [BUBBLE]])
    folder = tmp_path / "game"
    (folder / "media").mkdir(parents=True)
    (folder / "media" / "script_eng.mrg").write_bytes(data)
    rules, root = _unpack(tmp_path, folder)

    out = tmp_path / "out"
    rules.build_target(TARGET_FILES, str(root), str(root), str(out), lambda p, t: None, lambda: False)
    assert (out / "media" / "script_eng.mrg").read_bytes() == data

    text_path = root / TEXT_JSON_DIR / TEXT_JSON_NAME
    obj = json.loads(text_path.read_text(encoding="utf-8"))
    obj["scenes"][1][0] = "Привіт."
    text_path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    out2 = tmp_path / "out2"
    rules.build_target(TARGET_FILES, str(root), str(root), str(out2), lambda p, t: None, lambda: False)
    built = script.parse((out2 / "media" / "script_eng.mrg").read_bytes())
    assert built.strings == [[NOVEL, BUBBLE], ["Привіт."], [BUBBLE]]

    obj["scenes"][1].append("one string too many")
    text_path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        rules.build_target(TARGET_FILES, str(root), str(root), str(tmp_path / "out3"), lambda p, t: None, lambda: False)


def test_a_line_over_the_limit_is_reported():
    assert long_lines("{E000:0001}" + "x" * 34) == []
    assert long_lines("{E000:0001}short\n" + "x" * 35) == [1]
    assert long_lines("{E200:0001}" + "x" * 50) == []


@pytest.mark.skipif(not os.environ.get("GUARDIAN_HEROES_SCRIPT"), reason="needs a real script_eng.mrg")
def test_the_real_script_rebuilds_byte_for_byte():
    data = open(os.environ["GUARDIAN_HEROES_SCRIPT"], "rb").read()
    parsed = script.parse(data)
    assert script.build(parsed) == data
    assert sum(len(s) for s in parsed.strings) > 1000
