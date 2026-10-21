"""MadWorld plugin: message tables exported as JSON blocks (load, save, other keys kept), tags; the real fonts of the
owner's unpacked workspace; and the wizard's unpack of the owner's disc compared with the workspace source tree
(both skipped when the workspace is not on this machine)."""
import filecmp
import json
import os

import romhacking_root
import pytest

from core.formats import SaveContext
from core.project_library import build as lb
from core.project_library import console_keys
from core import font_formats
from plugins.madworld.rules import TAG_RE, GameRules
from plugins.madworld.unpack import GAME_ID
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "madworld"
WS = romhacking_root.under('MadWorld')
ORIGINAL = WS / "image" / "original (Wii PAL).iso"
real = pytest.mark.skipif(not (ORIGINAL.is_file() and (WS / "source" / "text").is_dir()),
                          reason="MadWorld disc and source not on this machine")

SAMPLE = {"file": "subscr/MessSubscr002_us.msd", "kind": "msd", "atlas": "subscr/subscr002_us.mtd", "blocks": [
    {"name": "MessSubscr002_us", "ids": [0, 1], "ends": [True, False],
     "strings": ["<8010:0064>No SD Card found.", "<8073:0000><8010:0050><8093:0023>"]}]}


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


def test_the_rules_declare_the_wii_platform_and_the_build_target():
    rules = GameRules(None)
    assert rules.get_platforms() == [{"id": "wii", "label": "Wii"}]
    assert [t["id"] for t in rules.get_build_targets()] == ["wii_iso"]
    assert rules.unpack_key_consoles() == ["wii"]
    assert GAME_ID == "RZZP8P"


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
def test_the_wizard_unpack_of_the_disc_matches_the_workspace_source(tmp_path):
    pytest.importorskip("Crypto", reason="reading the disc needs pycryptodome")
    project = tmp_path / "project"
    folder = lb.run_unpack(GameRules(None), {"base": str(ORIGINAL)}, str(project), lambda p, t: None,
                           lambda: False, key_provider=console_keys.path_for)
    mine = {}
    for dp, _dn, fn in os.walk(folder):
        for name in fn:
            full = os.path.join(dp, name)
            mine[os.path.relpath(full, folder).replace("\\", "/")] = full
    source = WS / "source"
    theirs = {}
    for dp, _dn, fn in os.walk(source):
        for name in fn:
            full = os.path.join(dp, name)
            theirs[os.path.relpath(full, source).replace("\\", "/")] = full
    mine.pop(".picoripi_disc.json", None)
    assert set(mine) == set(theirs)
    assert [k for k in mine if not filecmp.cmp(mine[k], theirs[k], shallow=False)] == []
