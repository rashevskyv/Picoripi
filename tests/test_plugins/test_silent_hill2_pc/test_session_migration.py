"""Sessions saved before the message table fix: the plugin maps their rows, and the session manager decides.

The snapshots are built here from synthetic message files; no game data is read.
"""
from types import SimpleNamespace

from core.data_processor.session_manager import SESSION_DATA_LAYOUT, SessionManager
from plugins.silent_hill2_pc import mes, mes_legacy
from plugins.silent_hill2_pc.rules import GameRules as PcRules
from plugins.silent_hill2_switch.rules import GameRules as SwitchRules

MESSAGES = [
    b"\x00\x80\x39\x45\x53\x0e\xff\xff\x00\x80",
    b"\x00\x80\x2e\x4f\x0e\xff\xff\x00\x00\x00",
    b"\x00\x80\x29\x54\x07\x53\xff\xff\x00\x90",
]


def _old_snapshot(edits, **extra):
    """A snapshot as the old reading saved it: one block, its rows decoded with the old codec."""
    data = mes.build(MESSAGES)
    old_rows = [mes_legacy.legacy_decode(r) for r in mes_legacy.legacy_split(data)]
    snapshot = {"data": [old_rows], "edited_data": dict(edits), "undo_stack": [{"a": 1}], "redo_stack": [],
                "problems_per_subline": {"0,1,0": "p", "0,0,0": "q"}, "current_block_idx": 0,
                "current_string_idx": 2, "selected_string_indices": [2], "last_selected_string_index": 2}
    snapshot.update(extra)
    return snapshot, old_rows


def test_pc_hook_moves_rows_and_edits_to_the_current_messages():
    snapshot, old_rows = _old_snapshot({})
    snapshot["edited_data"] = {(0, 1): old_rows[1] + "!", (0, 2): old_rows[2]}
    out = PcRules().migrate_session_snapshot(snapshot)
    assert out["data_layout"] == SESSION_DATA_LAYOUT
    assert out["data"][0] == [mes.decode(m) for m in MESSAGES]
    assert out["edited_data"][(0, 0)] == old_rows[1] + "!"
    assert out["edited_data"][(0, 1)] == mes.decode(MESSAGES[1])
    assert out["edited_data"][(0, 2)] == mes.decode(MESSAGES[2])
    assert out["undo_stack"] == [] and out["redo_stack"] == []
    assert out["problems_per_subline"] == {}
    assert out["current_string_idx"] == -1 and out["selected_string_indices"] == []


def test_pc_hook_drops_an_edit_on_the_offset_row():
    snapshot, _ = _old_snapshot({(0, 0): "junk"})
    out = PcRules().migrate_session_snapshot(snapshot)
    assert (0, 0) not in out["edited_data"]


def test_pc_hook_drops_a_merged_row_edit_whose_length_changed():
    snapshot, old_rows = _old_snapshot({})
    snapshot["edited_data"] = {(0, 2): old_rows[2] + "xyz"}
    out = PcRules().migrate_session_snapshot(snapshot)
    assert out["data_layout"] == SESSION_DATA_LAYOUT
    assert (0, 1) not in out["edited_data"] and (0, 2) not in out["edited_data"]


def test_switch_hook_does_not_migrate_and_keeps_the_marker_away():
    snapshot, _ = _old_snapshot({(0, 1): "x"})
    out = SwitchRules().migrate_session_snapshot(snapshot)
    assert "data_layout" not in out


def test_session_manager_migrates_an_old_session_and_refuses_an_unmigratable_one():
    manager = SessionManager(SimpleNamespace(mw=SimpleNamespace(current_game_rules=PcRules())))
    snapshot, _ = _old_snapshot({})
    migrated = manager._upgrade_session_layout(snapshot)
    assert migrated is not None and migrated["data_layout"] == SESSION_DATA_LAYOUT
    manager_sw = SessionManager(SimpleNamespace(mw=SimpleNamespace(current_game_rules=SwitchRules())))
    assert manager_sw._upgrade_session_layout(_old_snapshot({})[0]) is None


def test_session_manager_leaves_a_current_session_alone_and_other_games_too():
    manager = SessionManager(SimpleNamespace(mw=SimpleNamespace(current_game_rules=PcRules())))
    current = {"data_layout": SESSION_DATA_LAYOUT, "data": []}
    assert manager._upgrade_session_layout(current) is current
    other = SessionManager(SimpleNamespace(mw=SimpleNamespace(current_game_rules=object())))
    old = {"data": [["a"]]}
    assert other._upgrade_session_layout(old) is old
