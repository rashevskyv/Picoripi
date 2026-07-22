"""Tests for the zelda_bmg game-truth scene hook + stage_scene_data layer."""
from plugins.zelda_bmg.stage_data import (
    load_stage_scene_data, msg_group_for_stage, stages_for_actor,
)


def test_stage_scene_data_loads_and_maps_groups():
    doc = load_stage_scene_data()
    stages = doc.get("stages", {})
    assert len(stages) >= 70                       # full stage set extracted
    # every stage resolved a message group
    assert all("msg_group" in rec for rec in stages.values())
    # known mappings from the ENG dump
    assert msg_group_for_stage(doc, "F_SP103") == 1   # Ordon
    assert msg_group_for_stage(doc, "F_SP109") == 2   # Kakariko


def test_actor_reverse_index():
    doc = load_stage_scene_data()
    # Uri lives in Ordon village + her house interior
    stages = stages_for_actor(doc, "Uri")
    assert "F_SP103" in stages


def test_scene_hook_graceful_without_main_window():
    # GameRules with no main window must not raise and must return {}.
    from plugins.zelda_bmg.rules import GameRules
    rules = GameRules(None)
    assert rules.get_scene_context_for_string(0, 5) == {}
    # the cached stage data still loads
    assert len(rules._get_stage_scene_data().get("stages", {})) >= 70
