"""MadWorld plugin: message tables exported as JSON blocks (load, save, other keys kept), tags; the workspace
script's message words, tables and rebuilt atlases when it is on this machine; the real fonts, text and a
changed table of a stage package and of a cut-scene when the workspace is unpacked here."""
import importlib
import json
import re
import sys
from pathlib import Path

import pytest

from core import font_formats
from core.formats import SaveContext
from plugins.madworld.rules import TAG_RE
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "madworld"
WS = Path(r"E:\Emulators\RomHacking\MadWorld")
SCRIPTS = Path(r"E:\Emulators\RomHacking\_shared\scripts")
real = pytest.mark.skipif(not (WS / "image" / "mw_index.json").exists(), reason="MadWorld not unpacked here")

SAMPLE = {"file": "subscr/MessSubscr002_us.msd", "kind": "msd", "atlas": "subscr/subscr002_us.mtd", "blocks": [
    {"name": "MessSubscr002_us", "ids": [0, 1], "ends": [True, False],
     "strings": ["<8010:0064>No SD Card found.", "<8073:0000><8010:0050><8093:0023>"]}]}


def mw():
    if not (SCRIPTS / "zt" / "madworld.py").is_file():
        pytest.skip("workspace scripts not on this machine")
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("zt.madworld")


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".mwt", ".csv"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_saving_keeps_the_other_keys():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    raw = json.dumps(SAMPLE).encode("utf-8")
    rules.prepare_save_context(SaveContext(relative_path="text/x.mwt", existing_versions=lambda: iter([raw])))
    blocks[0][0] = "<8010:0064>SD-карту не знайдено. Ґанок, їжак."
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved["blocks"][0]["strings"][0].endswith("Ґанок, їжак.")
    assert saved["blocks"][0]["ends"] == [True, False] and saved["atlas"] == "subscr/subscr002_us.mtd"


def test_tags():
    for tag in ("<8010:0064>", "<8002>", "<#0003>", "<G:1012>"):
        assert TAG_RE.fullmatch(tag), tag


def test_words_text_and_tables():
    zt = mw()
    chars = {0: ("H", "subtitle"), 1: ("i", "subtitle")}
    words = [0x8010, 0x64, 0x1000, 0x1001, 0x8001, 0x8094, 0x0003, 0x8000, 0x1001, 0x8002]
    text, end = zt.words_to_text(words, 0x1000, chars)
    assert text == "<8010:0064>Hi <8094><#0003>\ni" and end
    by = {"H": 0x1000, "i": 0x1001}
    assert zt.text_to_words(text, end, by.__getitem__) == words
    table = zt.msd_build(0xFFFFFFFF, [(0, words), (7, [0x8002])])
    assert zt.msd_parse(table) == (0xFFFFFFFF, [(0, words), (7, [0x8002])])
    assert zt.msd_build(0xFFFFFFFF, [(0, words)], 0x80)[-1:] == b"\0" and len(zt.msd_build(0xFFFFFFFF, [(0, words)], 0x80)) == 0x80


@real
def test_every_font_opens_and_packs_back_unchanged():
    for src in load_rules(PLUGIN).get_font_sources():
        if src["format"] != "texture_grid":
            continue
        data = (WS / "source" / src["path"]).read_bytes()
        backend = font_formats._backends()["texture_grid"]
        meta, sheets = backend.extract(data, src["params"])
        assert backend.pack(meta, sheets, data, src["params"]) == data, src["path"]
        if "chars" in src["params"]:
            assert "Ґ" in src["params"]["chars"] and len(set(src["params"]["chars"])) == len(src["params"]["chars"])


@real
def test_a_changed_table_is_rebuilt_and_reads_back():
    pytest.importorskip("Crypto", reason="reading the disc needs pycryptodome")
    zt = mw()
    from zt import common
    from zt.nmh import Disc
    index = json.loads((WS / "image" / zt.INDEX).read_text(encoding="utf-8"))
    table = zt.labels()
    disc = Disc(WS, common.load_env())
    try:
        for rel in ("case1/idpac_c103_us.dat", "event/ev71_us.dat"):
            info = index["texts"][rel]
            raw, msd, mtd = zt.load_unit(disc, rel, info["kind"], info["atlas"])
            doc = json.loads((WS / "source" / "text" / f"{rel}.mwt").read_text(encoding="utf-8"))["blocks"][0]
            k = next(i for i, s in enumerate(doc["strings"]) if re.search("[A-Za-z]{4}", s))
            word = re.search("[A-Za-z]{4,}", doc["strings"][k])
            new = list(doc["strings"])
            new[k] = new[k][:word.end()] + " Quiz" + new[k][word.end():]
            missing = set()
            msd2, mtd2 = zt.rebuild_unit(WS, index, raw, msd, mtd, (doc, new), {}, table, {}, missing)
            out = dict(zt.save_unit(info["kind"], raw, msd2, mtd2))[0]
            if info["kind"] == "evnt":
                assert out[:4] == b"EVNT" and len(out) % 0x20 == len(raw[0]) % 0x20
                msd3, mtd3 = zt.evnt_bodies(out)
            else:
                secs = dict((t, b) for t, b in zt.idpac_sections(out))
                msd3, mtd3 = secs[b"MSD\0"], secs[b"MTD\0"]
            atlas = zt.mtd_parse(mtd3)
            chars = zt.atlas_chars(atlas, table)
            _flag, msgs = zt.msd_parse(msd3)
            texts = [zt.words_to_text(w, atlas["first"], chars)[0] for _i, w in msgs]
            assert texts[k] == new[k] and texts[:k] == doc["strings"][:k] and not missing
    finally:
        disc.close()
