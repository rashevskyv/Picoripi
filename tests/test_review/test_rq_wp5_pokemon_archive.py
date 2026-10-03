"""WP5 review queue (5.5):

- "Pokémon FireRed key handling moved into the plugin": a project save, a save after the keys were restored
  from a session snapshot (also one written by the pre-audit build) and a project revert write the right files.
  The pre-audit output (``tests/fixtures/review_queue/wp5/make_golden.py``) had three faults, now fixed: a
  one-block file saved under the file name, the second file saved with the first file's keys (each project
  block of a split file parsed the whole file again), a revert keeping only the last block of a file.
- "Files inside an archive are decoded by their extension": a .json / .txt member now arrives parsed, like a
  file on disk; a .bmg member is unchanged (bytes).
"""
import json

import pytest

from . import _rq_wp5_helpers as h

GOLDEN = json.loads((h.FIXTURES / "pokemon_archive" / "golden.json").read_text(encoding="utf-8"))


def _parsed(texts):
    return {name: json.loads(text) for name, text in texts.items()}


A, B = h.POKEMON_FILES["text_a.json"], h.POKEMON_FILES["text_b.json"]
A_EDITED = {**A, "A_lab": {**A["A_lab"], "l2": "Edited after the session restore"}}


def test_pokemon_save_session_restore_and_revert_write_the_right_files(qapp, tmp_path):
    result = h.pokemon_roundtrip(tmp_path)

    assert result["names"] == ["A_lab", "Z_town", "text_b"]   # a one-block file is shown under its file name
    assert _parsed(result["after_save"]) == {"text_b.json": {"M_mart": {**B["M_mart"], "m5": "Welcome, trainer!"}}}
    assert result["snapshot"] == {"plugin_original_keys": [["l9", "l2"], ["t3", "t1"], ["m5", "m0"]]}
    assert _parsed(result["after_session"])["text_a.json"] == A_EDITED
    assert _parsed(result["after_revert"]) == h.POKEMON_FILES


def test_a_single_block_project_saves_restores_and_reverts(qapp, tmp_path):
    result = h.pokemon_roundtrip(tmp_path, files=h.POKEMON_SINGLE)
    route = h.POKEMON_SINGLE["text_c.json"]["Q_route"]

    assert _parsed(result["after_save"]) == {"text_c.json": {"Q_route": {**route, "r7": "Welcome, trainer!"}}}
    assert _parsed(result["after_session"]) == {"text_c.json": {"Q_route": {
        "r7": "Welcome, trainer!", "r2": "Edited after the session restore"}}}
    assert _parsed(result["after_revert"]) == h.POKEMON_SINGLE


def test_a_session_written_by_the_old_build_restores_the_keys(qapp, tmp_path):
    old_snapshot = GOLDEN["two_files"]["snapshot"]
    assert "plugin_original_keys" in old_snapshot          # the slot old session files use

    result = h.pokemon_roundtrip(tmp_path, snapshot=old_snapshot)

    # The old build doubled the keys of a split file; the first file's blocks still come first.
    assert _parsed(result["after_session"])["text_a.json"] == A_EDITED


def _keys(text):
    return {block: list(strings) for block, strings in json.loads(text).items()}


def test_a_single_block_file_keeps_its_block_name(qapp, tmp_path):
    result = h.pokemon_roundtrip(tmp_path, files=h.POKEMON_SINGLE)
    assert _keys(result["after_save"]["text_c.json"]) == {"Q_route": ["r7", "r2"]}


def test_each_file_is_saved_with_its_own_keys(qapp, tmp_path):
    result = h.pokemon_roundtrip(tmp_path)
    saved = json.loads(result["after_save"]["text_b.json"])
    assert [list(strings) for strings in saved.values()] == [["m5", "m0"]]


def test_a_revert_keeps_every_block_of_a_file(qapp, tmp_path):
    result = h.pokemon_roundtrip(tmp_path)
    assert sorted(json.loads(result["after_revert"]["text_a.json"])) == ["A_lab", "Z_town"]


@pytest.mark.parametrize("plugin, member, payload", h.ARCHIVE_MEMBER_CASES)
def test_archive_members_arrive_decoded_by_their_extension(qapp, tmp_path, plugin, member, payload):
    old = GOLDEN["archive_members"][f"{plugin}:{member}"]
    data = h.archive_member_load(plugin, member, payload, tmp_path / "project")

    if member.endswith(".bmg"):
        assert data == old and len(data[0]) == 6                  # bytes, as before
        return
    # Changed on purpose: the plugin used to get raw bytes and read nothing from the member.
    assert old in ([], [[]])
    content = json.loads(payload) if member.endswith(".json") else payload.decode("utf-8")
    expected, _names = h.new_rules(plugin).load_data_from_json_obj(content)
    assert data == expected and data and data[0]


def test_a_doubled_old_session_does_not_replace_the_loaded_keys():
    from plugins.pokemon_fr.rules import GameRules

    rules = GameRules()
    for content in h.POKEMON_FILES.values():
        rules.load_data_from_json_obj(content)
    rules.restore_runtime_state(GOLDEN["two_files"]["snapshot"]["plugin_original_keys"])   # five lists, three blocks

    assert rules.export_runtime_state() == [["l9", "l2"], ["t3", "t1"], ["m5", "m0"]]
