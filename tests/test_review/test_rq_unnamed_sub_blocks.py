"""A project file split into blocks the plugin leaves unnamed (Minish Cap's list of lists) loads every block.

The sync names such blocks "Block {i}"; the loader looked only at the plugin's own names, found none and loaded
80 empty "(Missing)" blocks for the Minish Cap translation (2026-10-03).
"""
import json

from . import _rq_wp5_helpers as h


def test_a_list_of_lists_file_loads_every_block_with_its_strings(qapp, tmp_path):
    blocks = [["Hello there.", "How are you?"], ["Goodbye."], ["One", "Two", "Three"]]
    pm, _trans = h._open_project(tmp_path, "zelda_mc", {"text.json": json.dumps(blocks).encode("utf-8")})

    _rules, loaded = h._load(pm, "zelda_mc")

    assert loaded["data"] == blocks
    assert [loaded["block_names"][str(i)] for i in range(3)] == ["Block 0", "Block 1", "Block 2"]
