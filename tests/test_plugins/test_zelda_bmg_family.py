"""Twilight Princess family plan on the real message folders: member counts, links and the project's blocks.

Skipped on a machine without the unpacked game. The counts are the ones the plan printed for the GameCube, Wii and
both Wii U HD slots; a change here means the recognition or the linking changed.
"""
import os
from pathlib import Path

import pytest

from core.family_projects.store import links
from plugins.zelda_bmg.family import family_of, make_rules, plan_for_sources

WORKSPACE = Path(os.environ.get("PICORIPI_ROMHACKING", "RomHacking"), "Zelda/Twilight Princess")
SOURCES = [
    WORKSPACE / "GC + Wii/ISO/ENG/root/res/Msgus",
    Path(os.environ.get("PICORIPI_SCRATCH", "scratch"), "Zelda/TP_Wii_ENG/files/res/Msgus"),
    WORKSPACE / "HD - Wii U/source/content/res/Msguk",
    WORKSPACE / "HD - Wii U/source/content/res/Msgus",
]
needs_game = pytest.mark.skipif(not all(p.is_dir() for p in SOURCES),
                                reason="the unpacked Twilight Princess folders are not on this machine")


@needs_game
def test_plan_recognises_four_members_and_links_them_as_planned():
    plan, _units = plan_for_sources([str(p) for p in SOURCES], make_rules(WORKSPACE / "GC + Wii/picoripi"))
    assert [m.key for m in plan.members] == ["gc", "wii", "hd_msguk", "hd_msgus"]
    assert plan.base == "gc"
    assert plan.member("hd_msgus").parents == ("hd_msguk", "gc")
    family = family_of(plan)
    sizes = {key: len(units) for key, units in family.units.items()}
    assert sizes == {"gc": 15622, "wii": 15621, "hd_msguk": 15575, "hd_msgus": 15575}
    linked = links(family)
    own = {key: len(units) - len(linked[key]) for key, units in family.units.items()}
    assert own == {"gc": 15622, "wii": 183, "hd_msguk": 3321, "hd_msgus": 405}


@needs_game
def test_a_single_source_is_a_valid_family():
    plan, _units = plan_for_sources([str(SOURCES[0])], make_rules(None))
    assert plan.base == "gc" and len(plan.members) == 1


@needs_game
def test_project_folders_hold_every_message_once_with_the_planned_counts():
    from collections import Counter

    from plugins.zelda_bmg.family_project import _entries

    plan, units = plan_for_sources([str(p) for p in SOURCES], make_rules(WORKSPACE / "GC + Wii/picoripi"))
    folders = Counter(folder for folder, _member, _unit in _entries(plan, units))
    assert folders == {"Shared": 15486, "Shared HD Msguk": 2908, "GC only": 136, "Wii only": 183,
                       "HD Msguk only": 413, "HD Msgus only": 405}
    assert sum(folders.values()) == 19531
    assert plan.shared_files == {"Fontus/fontres.arc": ("wii",)}
