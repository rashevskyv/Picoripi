"""Every plugin declares how its source reaches the wizard, or is on the explicit baseline below.

A plugin with a wizard hook (identify_source, unpack_sources, get_platforms, get_source_roles,
unpack_key_consoles, get_source_subfolder) is not on the list. A plugin without one is on BASELINE with the
reason its source is not unpacked by Picoripi yet. The baseline only shrinks: a baseline plugin that gains a hook
must leave the list, and a new plugin without a hook must be added with a reason.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from plugins.base_game_rules import BaseGameRules

PLUGINS = Path("plugins")
HOOKS = (
    "identify_source", "get_source_roles", "get_platforms", "unpack_sources", "unpack_key_consoles",
    "get_source_subfolder",
)

BASELINE = {
    "ace_attorney_trilogy": "owner source is not a disc image (folders); the user prepares the folder or files",
    "animal_crossing_3ds": "owner source is not a disc image (folders); the user prepares the folder or files",
    "animal_crossing_nh": "owner source is not a disc image (folders); the user prepares the folder or files",
    "attack_on_titan_3ds": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "bravely_default": "owner source is not a disc image (folders); the user prepares the folder or files",
    "castlevania_cotm": "owner source is not a disc image (folders); the user prepares the folder or files",
    "castlevania_dxc": "owner source is not a disc image (folders); the user prepares the folder or files",
    "castlevania_gba": "owner source is not a disc image (folders); the user prepares the folder or files",
    "castlevania_mof": "owner source is not a disc image (folders); the user prepares the folder or files",
    "castlevania_sotn": "owner source is not a disc image (folders); the user prepares the folder or files",
    "castlevania_sotn_saturn": "owner source is not a disc image (folders); the user prepares the folder or files",
    "code_name_steam": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "code_of_princess": "owner source is not a disc image (folders); the user prepares the folder or files",
    "corpse_party": "owner source is not a disc image (folders); the user prepares the folder or files",
    "default_plugin": "template plugin for new games, not a game",
    "digimon_redigitize": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "donkey_kong_country": "owner source is not a disc image (folders); the user prepares the folder or files",
    "donkey_kong_gba": "owner source is not a disc image (folders); the user prepares the folder or files",
    "donkey_kong_tropical_freeze": "owner source is not a disc image (folders); the user prepares the folder or files",
    "dq_monsters_joker3": "owner source is not a disc image (folders); the user prepares the folder or files",
    "dragon_ball_fusions": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "dragon_quest_builders": "owner source is not a disc image (folders); the user prepares the folder or files",
    "dragon_quest_vii": "owner source is not a disc image (folders); the user prepares the folder or files",
    "dragon_quest_viii": "owner source is not a disc image (folders); the user prepares the folder or files",
    "ever_oasis": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "fantasy_life": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "final_fantasy_explorers": "owner source is not a disc image (folders); the user prepares the folder or files",
    "fire_emblem_awakening": "owner source is not a disc image (folders); the user prepares the folder or files",
    "fragile_dreams": "owner has a .iso,.rvz image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "gravity_falls_gemulets": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "hard_corps_uprising": "owner source is not a disc image (folders); the user prepares the folder or files",
    "ikenie_no_yoru": "owner has a .iso,.rvz image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "jak_and_daxter": "owner source is not a disc image (folders); the user prepares the folder or files",
    "kid_icarus": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "kingdom_hearts_ddd": "owner source is not a disc image (folders); the user prepares the folder or files",
    "layton_3ds": "owner source is not a disc image (folders); the user prepares the folder or files",
    "layton_mr": "owner source is not a disc image (folders); the user prepares the folder or files",
    "luigis_mansion_2": "owner source is not a disc image (folders); the user prepares the folder or files",
    "lunar_ebc": "owner source is not a disc image (folders); the user prepares the folder or files",
    "lunar_ssh": "owner source is not a disc image (folders); the user prepares the folder or files",
    "lunar_sssc": "owner source is not a disc image (folders); the user prepares the folder or files",
    "madworld": "owner has a .iso,.rvz image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "manual_3ds": "owner source is not a disc image (folders); the user prepares the folder or files",
    "mario_vs_donkey_kong_gba": "owner source is not a disc image (folders); the user prepares the folder or files",
    "mario_vs_donkey_kong_switch": "owner source is not a disc image (folders); the user prepares the folder or files",
    "metal_gear_mc_bonus": "owner source is not a disc image (folders); the user prepares the folder or files",
    "metal_gear_pw": "owner source is not a disc image (folders); the user prepares the folder or files",
    "metal_gear_solid_23_mc": "owner source is not a disc image (folders); the user prepares the folder or files",
    "metal_gear_solid_3d": "owner source is not a disc image (folders); the user prepares the folder or files",
    "metal_gear_solid_4": "owner source is not a disc image (folders); the user prepares the folder or files",
    "metal_gear_solid_mc": "owner source is not a disc image (folders); the user prepares the folder or files",
    "metal_gear_solid_ps1": "owner source is not a disc image (folders); the user prepares the folder or files",
    "metroid_other_m": "owner source is not a disc image (folders); the user prepares the folder or files",
    "metroid_prime4": "owner source is not a disc image (folders); the user prepares the folder or files",
    "metroid_prime_remastered": "owner source is not a disc image (folders); the user prepares the folder or files",
    "mhp3rd": "no owner workspace on disk to check; no image is known",
    "mii_3ds": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "miitopia_nx": "owner source is not a disc image (folders); the user prepares the folder or files",
    "monster_hunter_3ds": "owner source is not a disc image (folders); the user prepares the folder or files",
    "monster_hunter_stories_nx": "owner source is not a disc image (folders); the user prepares the folder or files",
    "no_more_heroes": "owner has a .iso,.rvz image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "one_piece_uwr": "owner source is not a disc image (folders); the user prepares the folder or files",
    "paper_mario_64": "owner source is not a disc image (folders); the user prepares the folder or files",
    "paper_mario_cs": "owner source is not a disc image (folders); the user prepares the folder or files",
    "paper_mario_nx": "owner source is not a disc image (folders); the user prepares the folder or files",
    "paper_mario_ok": "owner source is not a disc image (folders); the user prepares the folder or files",
    "paper_mario_ss": "owner source is not a disc image (folders); the user prepares the folder or files",
    "plain_text": "no owner workspace on disk to check; no image is known",
    "policenauts": "owner source is not a disc image (folders); the user prepares the folder or files",
    "rabbids_party": "owner has a .iso,.rvz image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "rhythm_paradise_megamix": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "rune_factory_4": "owner source is not a disc image (folders); the user prepares the folder or files",
    "senran_kagura_burst": "owner source is not a disc image (folders); the user prepares the folder or files",
    "silent_hill1_switch": "no owner workspace on disk to check; no image is known",
    "silent_hill2_pc": "owner source is not a disc image (folders); the user prepares the folder or files",
    "silent_hill2_switch": "no owner workspace on disk to check; no image is known",
    "silent_hill_3_pc": "owner source is not a disc image (folders); the user prepares the folder or files",
    "silent_hill_ps1": "owner source is not a disc image (folders); the user prepares the folder or files",
    "sly_cooper": "owner source is not a disc image (folders); the user prepares the folder or files",
    "smt_iv": "owner source is not a disc image (folders); the user prepares the folder or files",
    "spore_hero": "owner has a .iso,.rvz image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "stella_glow": "owner has a .cia image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "story_of_seasons_3ds": "owner source is not a disc image (folders); the user prepares the folder or files",
    "super_metroid": "owner source is not a disc image (folders); the user prepares the folder or files",
    "vagrant_story": "owner has a .cue image; no unpack hook yet, the wizard refuses it (unpacking needs a port of the workspace's zt script)",
    "wii_sysfont": "owner source is not a disc image (folders); the user prepares the folder or files",
    "xenoblade_2": "owner source is not a disc image (folders); the user prepares the folder or files",
    "xenoblade_3": "owner source is not a disc image (folders); the user prepares the folder or files",
    "xenoblade_de": "owner source is not a disc image (folders); the user prepares the folder or files",
    "xenoblade_wii": "owner source is not a disc image (folders); the user prepares the folder or files",
    "xenoblade_x_de": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_albw": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_aoc": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_coh": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_hwde": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_ladx": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_ladx_hd": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_lttp": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_mc": "no owner workspace on disk to check; no image is known",
    "zelda_mm3d": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_mm64": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_oot3d": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_oot64": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_oracles": "no owner workspace on disk to check; no image is known",
    "zelda_tfh": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_tingle": "owner source is not a disc image (folders); the user prepares the folder or files",
    "zelda_totk": "owner source is not a disc image (folders); the user prepares the folder or files",
}


def _plugin_names():
    return sorted(p.name for p in PLUGINS.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))
                  and p.name != "common" and (p / "rules.py").is_file())


def _declares_a_hook(name: str) -> bool:
    module = importlib.import_module(f"plugins.{name}.rules")
    cls = getattr(module, "GameRules", None)
    if cls is None:
        cls = next(obj for obj in vars(module).values()
                   if isinstance(obj, type) and issubclass(obj, BaseGameRules) and obj is not BaseGameRules
                   and obj.__module__ == module.__name__)
    return any(getattr(cls, hook) is not getattr(BaseGameRules, hook) for hook in HOOKS)


def test_every_plugin_declares_a_hook_or_is_on_the_baseline():
    missing = [name for name in _plugin_names() if name not in BASELINE and not _declares_a_hook(name)]
    assert missing == [], f"add a wizard hook or a reason to BASELINE: {missing}"


def test_the_baseline_only_shrinks():
    for name in BASELINE:
        assert name in _plugin_names(), f"{name} is not a plugin: remove it from BASELINE"
        assert not _declares_a_hook(name), f"{name} now has a hook: remove it from BASELINE"


def test_each_baseline_reason_is_one_line():
    for name, reason in BASELINE.items():
        assert reason and "\n" not in reason, name


@pytest.mark.parametrize("name", sorted(BASELINE))
def test_baseline_plugin_still_imports(name):
    importlib.import_module(f"plugins.{name}.rules")
