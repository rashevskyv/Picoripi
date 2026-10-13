"""Jak and Daxter plugin: the game text as JSON blocks (load, save, ids kept), and the unpacked Jak II text
when the workspace is on this machine."""
import romhacking_root
import json

import pytest

from core.formats import SaveContext
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "jak_and_daxter"
WS = romhacking_root.under('Jak and Daxter\\Jak 2\\Switch')
real = pytest.mark.skipif(not (WS / "source" / "text" / "common.json").exists(), reason="Jak II not unpacked here")

SAMPLE = {"file": "text/common.json", "blocks": [
    {"name": "common", "ids": ["0100", "0101"], "strings": ["Quit", "Pause~"]}]}


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert ".json" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_saving_keeps_the_ids_and_the_other_keys():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    raw = json.dumps(SAMPLE).encode("utf-8")
    rules.prepare_save_context(SaveContext(relative_path="text/common.json", existing_versions=lambda: iter([raw])))
    blocks[0][1] = "Pausa"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved["blocks"][0]["strings"] == ["Quit", "Pausa"]
    assert saved["blocks"][0]["ids"] == ["0100", "0101"]


@real
def test_unpacked_text_has_every_id_with_english():
    doc = json.loads((WS / "source" / "text" / "common.json").read_text(encoding="utf-8"))
    block = doc["blocks"][0]
    assert len(block["ids"]) == len(block["strings"]) == 781
    assert block["strings"][block["ids"].index("0100")] == "Quit"
