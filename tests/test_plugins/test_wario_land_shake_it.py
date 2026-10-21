"""Wario Land: Shake It! plugin on synthetic BMG and GFAC files: the text form, documents, the build and the identify."""
import json
import struct
from pathlib import Path

import pytest

from core.containers import gfac
from plugins.wario_land_shake_it import bmgtext, build, unpack
from plugins.zelda_bmg.bmg_tool import BMGFile
from plugins.wario_land_shake_it.rules import GameRules


def make_bmg(messages):
    """A big-endian BMG with an INF1 (8-byte entries) and a DAT1 holding UTF-16 strings, like the game's."""
    strings = bytearray(b"\0\0")  # the game's DAT1 starts with a UTF-16 NUL
    offsets = []
    for text in messages:
        offsets.append(len(strings))
        strings += text.encode("utf-16-be") + b"\0\0"
        strings += b"\0" * (-len(strings) % 4)  # the game's strings start on 4-byte boundaries
    dat = b"DAT1" + struct.pack(">I", 8 + len(strings)) + bytes(strings)
    inf = bytearray()
    for index, offset in enumerate(offsets):
        inf += struct.pack(">I", offset) + bytes([0, 0, 0, index])
    inf_size = 16 + len(inf)
    inf_size += (-inf_size) % 32
    inf_block = b"INF1" + struct.pack(">IHHI", inf_size, len(messages), 8, 0) + bytes(inf)
    inf_block += b"\0" * (inf_size - len(inf_block))
    body = inf_block + dat
    total = 0x20 + len(body)
    header = b"MESGbmg1" + struct.pack(">I", total) + struct.pack(">I", 2) + bytes([2]) + b"\0\0\0"
    header += struct.pack(">III", 0, 0, 0)
    return header + body


def make_pack(entries):
    archive = gfac.GfacArchive(entries=[gfac.GfacEntry(name=name, data=data) for name, data in entries])
    return gfac.write_gfac(archive)


def test_text_form_round_trips_escape_codes_and_newlines():
    parts = ["Hello", "\n", {"type": "escape", "escape_type": 255, "data": bytes.fromhex("00000100")}, "!"]
    text = bmgtext.parts_to_text(parts)
    assert text == "Hello\n{esc:FF:00000100}!"
    assert bmgtext.text_to_parts(text) == [
        "Hello\n", {"type": "escape", "escape_type": 255, "data": "00000100"}, "!"]


def test_unclosed_escape_is_refused():
    with pytest.raises(ValueError):
        bmgtext.text_to_parts("Hi {esc:FF:00")


def canonical_bmg(messages):
    """The synthetic file as the tool itself writes it, so a re-save of it must give the same bytes."""
    bmg = BMGFile()
    bmg.load(make_bmg(messages))
    return bmg.save()


def test_bmg_read_and_rebuild_keeps_untouched_messages_identical():
    original = canonical_bmg(["Invented first line", "Invented second line"])
    messages = bmgtext.read_messages(original)
    assert [m["text"] for m in messages] == ["Invented first line", "Invented second line"]
    assert bmgtext.rebuild(original, [None, None]) == original
    edited = bmgtext.rebuild(original, ["Edited first line", "Invented {esc:FF:00000100} line"])
    back = bmgtext.read_messages(edited)
    assert [m["text"] for m in back] == ["Edited first line", "Invented {esc:FF:00000100} line"]
    assert back[1]["info"] == messages[1]["info"]


def test_rebuild_refuses_a_message_count_mismatch():
    original = make_bmg(["one", "two"])
    with pytest.raises(ValueError):
        bmgtext.rebuild(original, ["only one"])


def test_documents_build_a_translated_pack(tmp_path: Path):
    bmg_a = make_bmg(["Area one", "Area two"])
    bmg_b = make_bmg(["Demo"])
    pack_file = tmp_path / "versions" / "wii" / unpack.PACK_REL
    pack_file.parent.mkdir(parents=True)
    pack_file.write_bytes(make_pack([("message_english_USA_area.bmg", bmg_a),
                                     ("message_english_USA_demo.bmg", bmg_b)]))
    (tmp_path / "versions" / "wii" / "source.json").write_text(
        json.dumps({"image": "disc.rvz", "game_id": unpack.GAME_ID, "role": unpack.WII}), encoding="utf-8")
    unpack.write_documents(tmp_path, pack_file)
    docs = sorted((tmp_path / unpack.DOC_DIR).glob("*.json"))
    assert [d.name for d in docs] == ["message_english_USA_area.json", "message_english_USA_demo.json"]

    translation = tmp_path / "translation"
    (translation / unpack.DOC_DIR).mkdir(parents=True)
    doc = json.loads((tmp_path / unpack.DOC_DIR / "message_english_USA_area.json").read_text(encoding="utf-8"))
    doc["messages"][1]["text"] = "Zone two"
    (translation / unpack.DOC_DIR / "message_english_USA_area.json").write_text(
        json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    out = tmp_path / "out"
    build.build_wii_riivolution(str(tmp_path), str(translation), str(out),
                                lambda *_: None, lambda: False)
    xml = (out / "riivolution" / f"{build.MOD_NAME}.xml").read_text(encoding="utf-8")
    assert f'disc="/{unpack.PACK_REL}"' in xml
    archive = gfac.read_gfac((out / build.MOD_NAME / unpack.PACK_REL).read_bytes())
    texts = {e.name: [m["text"] for m in bmgtext.read_messages(e.data)] for e in archive.entries}
    assert texts == {"message_english_USA_area.bmg": ["Area one", "Zone two"],
                     "message_english_USA_demo.bmg": ["Demo"]}


def test_load_and_save_keep_the_message_count_and_info(tmp_path: Path):
    rules = GameRules()
    doc = {"format": unpack.FORMAT_ID, "pack": unpack.PACK_REL, "entry": "message_english_USA_stage.bmg",
           "messages": [{"info": "00000001", "text": "Stage"}, {"info": "00000002", "text": "Name"}]}
    blocks, names = rules.load_data_from_json_obj(doc)
    assert blocks == [["Stage", "Name"]] and names == {"0": "message_english_USA_stage.bmg"}
    saved = rules.save_data_to_json_obj([["Etap", None]], {})
    assert [m["text"] for m in saved["messages"]] == ["Etap", "Name"]
    assert [m["info"] for m in saved["messages"]] == ["00000001", "00000002"]


def test_identify_accepts_only_the_usa_disc_revision_zero(monkeypatch):
    from core.project_library import images

    def fake(found):
        return lambda path: dict(found)
    monkeypatch.setattr(images, "identify", fake({"kind": images.KIND_WII, "game_id": "RWLE01", "revision": 0}))
    assert unpack.identify("disc.rvz") == {"role": unpack.WII, "platform": unpack.WII}
    monkeypatch.setattr(images, "identify", fake({"kind": images.KIND_WII, "game_id": "RWLE01", "revision": 1}))
    assert unpack.identify("disc.rvz") is None
    monkeypatch.setattr(images, "identify", fake({"kind": images.KIND_GC, "game_id": "RWLE01", "revision": 0}))
    assert unpack.identify("disc.rvz") is None
