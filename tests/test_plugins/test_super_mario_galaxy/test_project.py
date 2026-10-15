"""The project on a synthetic unpacked tree: documents by archive, references, the three builds, the mod import, rules."""
import hashlib
import json
import struct
import zipfile

import pytest

from core.containers.rarc_container import RarcContainer
from plugins.super_mario_galaxy import build, import_mod, messages, unpack
from plugins.super_mario_galaxy.rules import GameRules

from .fixture import message_arc

LABELS = ["Title_Press", "Npc_Hello", "Wii_Only", "File_Prompt"]
WII = [["Press ", (3, b"\x00\x00")], ["Hello"], ["Old line"], ["Point at a file"]]
SWITCH_LABELS = ["Title_Press", "Npc_Hello", "ZZZ_New", "File_Prompt"]
SWITCH = [["Press ", (3, b"\x49\x00")], ["Hello"], ["New line"], ["Touch a file"]]
FST_AT, ARC_AT, OTHER_AT = 0x3000, 0x40000, 0x48000


def _fst(arc_size: int) -> bytes:
    """root / UsEnglish / MessageData / Message.arc, and Other.bin after it on the disc."""
    names = b"UsEnglish\0MessageData\0Message.arc\0Other.bin\0"
    entries = [(1 << 24, 0, 5), (1 << 24 | 0, 0, 4), (1 << 24 | 10, 1, 4), (22, ARC_AT >> 2, arc_size),
               (34, OTHER_AT >> 2, 0x100)]
    return b"".join(struct.pack(">III", *entry) for entry in entries) + names


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "unpacked"
    wii = root / "versions" / "wii"
    wii_arc = message_arc(LABELS, WII)
    files = {"files/UsEnglish/MessageData/Message.arc": wii_arc, "files/UsFrench/MessageData/Message.arc":
             message_arc(LABELS, [["Appuyez"], ["Salut"], ["Vieux"], ["Pointez"]]), "sys/fst.bin": _fst(len(wii_arc)),
             "sys/apploader.img": bytes(0x40), "sys/main.dol": b"DOL" * 100}
    boot = bytearray(0x440)
    struct.pack_into(">II", boot, 0x420, 0x2800 >> 2, FST_AT >> 2)
    files["sys/boot.bin"] = bytes(boot)
    for rel, data in files.items():
        (wii / rel).parent.mkdir(parents=True, exist_ok=True)
        (wii / rel).write_bytes(data)
    (wii / "source.json").write_text(json.dumps({"image": "game.rvz", "game_id": "RMGE01"}), encoding="utf-8")
    switch = root / "versions" / "switch"
    for slot in ("EuEnglish", "UsEnglish"):
        (switch / "romfs" / slot / "MessageData").mkdir(parents=True)
        (switch / "romfs" / slot / "MessageData" / "Message.arc").write_bytes(message_arc(SWITCH_LABELS, SWITCH, True))
        (switch / "romfs" / slot / "MessageData" / "System.arc").write_bytes(
            message_arc([], [["Saving"]], True, with_table=False))
    (switch / "source.json").write_text(json.dumps({"game_id": "010099C022B96000"}), encoding="utf-8")
    unpack.write_documents(root)
    unpack.write_references(root, lambda: False)
    translation = tmp_path / "translation"
    translation.mkdir()
    return root, translation


def _rows(path):
    return messages.read_document(path.read_bytes())


def test_one_document_per_archive_over_both_versions(project):
    root, _translation = project
    rows = _rows(root / "MessageData" / "Message.smgmsg")
    assert [(r["label"], r["in"], r.get("split", False)) for r in rows] == [
        ("Title_Press", ["wii", "switch"], False), ("Npc_Hello", ["wii", "switch"], False), ("Wii_Only", ["wii"], False),
        ("File_Prompt", ["wii"], True), ("File_Prompt", ["switch"], True), ("ZZZ_New", ["switch"], False)]
    assert rows[0]["text"] == "Press {escape:3:0000}"   # the Wii text first
    assert _rows(root / "MessageData" / "System.smgmsg") == [{"label": "#0", "text": "Saving", "in": ["switch"]}]
    columns = json.loads((root / unpack.REFERENCES).read_text(encoding="utf-8"))
    assert columns["UsFrench (wii)"]["Message"]["Npc_Hello"] == "Salut"
    assert "UsEnglish (wii)" not in columns and columns["EuEnglish (switch)"]["System"] == {"#0": "Saving"}
    assert unpack.game_of(root) == "smg1"


def _translate(root, translation):
    rows = _rows(root / "MessageData" / "Message.smgmsg")
    for row in rows:
        row["text"] = {"Title_Press": "Тисни {escape:3:0000}", "ZZZ_New": "Нове"}.get(row["label"], row["text"])
    (translation / "MessageData").mkdir(exist_ok=True)
    (translation / "MessageData" / "Message.smgmsg").write_bytes(messages.make_document(rows))


def test_switch_build_writes_every_english_slot_with_switch_pictures(project, tmp_path):
    root, translation = project
    _translate(root, translation)
    out = tmp_path / "switch"
    result = build.build_switch(str(root), str(translation), str(out), lambda *a: None, lambda: False)
    base = out / "atmosphere" / "contents" / "010099C022B96000" / "romfs"
    assert result == str(out / "atmosphere")
    for slot in ("EuEnglish", "UsEnglish"):
        texts = messages.texts_by_label((base / slot / "MessageData" / "Message.arc").read_bytes())
        assert texts["Title_Press"] == "Тисни {escape:3:0049}" and texts["ZZZ_New"] == "Нове"
        assert not (base / slot / "MessageData" / "System.arc").exists()   # nothing translated: the game's file stays


def test_wii_riivolution_build(project, tmp_path):
    root, translation = project
    _translate(root, translation)
    out = tmp_path / "wii"
    build.build_wii_riivolution(str(root), str(translation), str(out), lambda *a: None, lambda: False)
    arc = out / "SuperMarioGalaxyUA" / "UsEnglish" / "MessageData" / "Message.arc"
    assert messages.texts_by_label(arc.read_bytes())["Title_Press"] == "Тисни {escape:3:0000}"
    xml = (out / "riivolution" / "SuperMarioGalaxyUA.xml").read_text(encoding="utf-8")
    assert '<file disc="/UsEnglish/MessageData/Message.arc" external="UsEnglish/MessageData/Message.arc" />' in xml
    assert '<id game="RMG">' in xml
    descriptor = json.loads((out / "SuperMarioGalaxyUA.json").read_text(encoding="utf-8"))
    assert descriptor["base-file"] == "game.rvz" and descriptor["riivolution"]["patches"][0]["root"] == "."


def test_nebula_manifest_moves_a_grown_archive_and_patches_the_fst(project, tmp_path, monkeypatch):
    root, translation = project
    rows = _rows(root / "MessageData" / "Message.smgmsg")
    for row in rows:
        row["text"] = "Довгий український текст " * 20
    (translation / "MessageData").mkdir()
    (translation / "MessageData" / "Message.smgmsg").write_bytes(messages.make_document(rows))
    dol = (root / "versions" / "wii" / "sys" / "main.dol").read_bytes()
    monkeypatch.setattr(build, "NEBULA_MAIN_DOL_SHA1", hashlib.sha1(dol).hexdigest())
    out = tmp_path / "nebula"
    manifest = build.build_nebula(str(root), str(translation), str(out), lambda *a: None, lambda: False)
    lines = (out / "manifest.txt").read_text().splitlines()
    assert manifest == str(out / "manifest.txt") and lines[:2] == ["version 1", "game RMGE01"]
    offset, size, rel = lines[4].split()
    assert rel == "files/UsEnglish/MessageData/Message.arc" and int(size) == (out / rel).stat().st_size
    new_offset = int(offset, 16)
    assert new_offset % build.PLACE_ALIGN == 0 and new_offset + int(size) <= ARC_AT   # a free gap before the files
    assert new_offset >= FST_AT + len(_fst(0))
    files = build.fst_files((out / "sys" / "fst.bin").read_bytes())
    assert files["UsEnglish/MessageData/Message.arc"][1:] == (new_offset, int(size))
    assert files["Other.bin"][1:] == (OTHER_AT, 0x100)


def test_nebula_refuses_another_main_dol(project, tmp_path):
    root, translation = project
    with pytest.raises(ValueError, match="revision 0"):
        build.build_nebula(str(root), str(translation), str(tmp_path / "n"), lambda *a: None, lambda: False)


def test_place_keeps_a_file_that_still_fits():
    fst = _fst(0x2000)
    new, placed = build.place(fst, [(0, 0x100)], {"UsEnglish/MessageData/Message.arc": 0x1000})
    assert placed == {"UsEnglish/MessageData/Message.arc": ARC_AT}
    assert build.fst_files(new)["UsEnglish/MessageData/Message.arc"][1:] == (ARC_AT, 0x1000)
    with pytest.raises(ValueError, match="no file"):
        build.place(fst, [], {"Missing.arc": 1})


def test_import_by_label_from_a_switch_mod_zip(project, tmp_path):
    root, translation = project
    mod = tmp_path / "mod.zip"
    ua = message_arc(SWITCH_LABELS + ["ZZZ_Update"], [["Тисни ", (3, b"\x49\x00")], ["Привiт"], ["Нове"],
                                                      ["Торкнiться файлу"], ["Онов"]], True)
    with zipfile.ZipFile(mod, "w") as archive:
        archive.writestr("010099c022b96000/romfs/EuEnglish/MessageData/Message.arc", ua)
        archive.writestr("010099c022b96000/romfs/EuEnglish/LayoutData/Font.arc", b"FONT")
    report = import_mod.import_translation(str(root), str(translation), str(mod))
    part = report["archives"]["Message"]
    assert (part["matched"], part["missing_with_text"], part["extra"]) == (4, 1, ["ZZZ_Update"])
    assert part["other_version_wording"] == 1
    rows = {(row["label"], tuple(row["in"])): row["text"] for row in _rows(translation / "MessageData" / "Message.smgmsg")}
    assert rows[("Title_Press", ("wii", "switch"))] == "Тисни {escape:3:0000}"   # back to the Wii picture number
    assert rows[("Npc_Hello", ("wii", "switch"))] == "Привіт"                     # proper Ukrainian і
    assert rows[("Wii_Only", ("wii",))] == "Old line" and rows[("ZZZ_New", ("switch",))] == "Нове"
    # the Switch wording reaches only the Switch row; the Wii row keeps the Wii English until it is translated
    assert rows[("File_Prompt", ("switch",))] == "Торкніться файлу"
    assert rows[("File_Prompt", ("wii",))] == "Point at a file"
    wii = tmp_path / "wii"
    build.build_wii_riivolution(str(root), str(translation), str(wii), lambda *a: None, lambda: False)
    wii_texts = messages.texts_by_label(
        (wii / "SuperMarioGalaxyUA" / "UsEnglish" / "MessageData" / "Message.arc").read_bytes())
    assert wii_texts["File_Prompt"] == "Point at a file" and wii_texts["Npc_Hello"] == "Привіт"
    assert report["fonts"] == ["versions/switch/romfs/EuEnglish/LayoutData/Font.arc",
                               "versions/switch/romfs/UsEnglish/LayoutData/Font.arc"]
    # the Switch build starts from the mod's archive (its update's labels) and takes its font
    out = tmp_path / "switch"
    build.build_switch(str(root), str(translation), str(out), lambda *a: None, lambda: False)
    base = out / "atmosphere" / "contents" / "010099C022B96000" / "romfs" / "EuEnglish"
    assert messages.texts_by_label((base / "MessageData" / "Message.arc").read_bytes())["ZZZ_Update"] == "Онов"
    assert (base / "LayoutData" / "Font.arc").read_bytes() == b"FONT"
    switch_texts = messages.texts_by_label((base / "MessageData" / "Message.arc").read_bytes())
    assert switch_texts["File_Prompt"] == "Торкніться файлу"


def test_rules_load_save_and_reference_columns(project):
    root, _translation = project
    rules = GameRules()
    data = (root / "MessageData" / "Message.smgmsg").read_bytes()
    blocks, names = rules.load_data_from_json_obj(data)
    assert blocks[0][0] == "Press {escape:3:0000}" and names == {}
    assert rules.get_scene_context_for_string(0, 1) == {"label": "Npc_Hello", "versions": ["wii", "switch"]}
    saved = messages.read_document(rules.save_data_to_json_obj([["A", "B", "C", "D", "E", "F"]], {}))
    assert [row["text"] for row in saved] == ["A", "B", "C", "D", "E", "F"] and saved[5]["label"] == "ZZZ_New"
    assert [rules.is_split(0, index) for index in range(6)] == [False, False, False, True, True, False]
    assert "translate it" in rules.get_problem_detail(0, 3, "SMG_VERSION_WORDING")
    columns = rules.load_multi_reference(str(root), {"0": "Message"})
    assert columns["UsFrench (wii)"][(0, 1)] == "Salut"
    assert "Picture" in rules.get_tag_tooltip("{escape:3:0000}")


def test_identify_takes_only_the_game_files(tmp_path):
    other = tmp_path / "x.bin"
    other.write_bytes(b"\0" * 0x500)
    assert unpack.identify(str(other)) is None
    assert GameRules().identify_source(str(other)) is None


def test_archive_member_round_trip_keeps_the_label_table(project):
    root, _translation = project
    data = (root / "versions" / "wii" / "files" / "UsEnglish" / "MessageData" / "Message.arc").read_bytes()
    out = messages.apply_texts(data, {"Npc_Hello": "Привіт"})
    assert RarcContainer(out).read_file("messageid.tbl") == RarcContainer(data).read_file("messageid.tbl")
