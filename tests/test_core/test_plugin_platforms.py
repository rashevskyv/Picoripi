"""A build target names only platforms its game declares, so the wizard can set the platform and Run finds a command."""
import pytest

from core.project_library import plugin_facts
from utils import constants


def _plugins_with_targets():
    names = []
    for folder in sorted(constants.plugins_root().iterdir()):
        if (folder / "rules.py").is_file() and (folder / "config.json").is_file():
            names.append(folder.name)
    return names


@pytest.mark.parametrize("plugin", ["pokemon_bdsp", "pokemon_nx", "pokemon_trinity"])
def test_switch_pokemon_games_declare_the_switch_platform(plugin):
    rules = plugin_facts.default_load_rules(plugin)

    assert "switch" in {platform["id"] for platform in rules.get_platforms()}


def test_every_plugin_target_names_only_declared_platforms():
    problems = []
    for name in _plugins_with_targets():
        rules = plugin_facts.default_load_rules(name)
        declared = {platform["id"] for platform in rules.get_platforms()}
        for target in rules.get_build_targets() or []:
            missing = set(target.get("platforms") or []) - declared
            if missing:
                problems.append(f"{name}:{target['id']} names {sorted(missing)}")
    assert problems == []
