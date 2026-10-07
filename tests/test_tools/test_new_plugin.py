"""tools/new_plugin.py creates a plugin that loads, round-trips and validates (WP5 5.4)."""
import json
import shutil
import sys
from pathlib import Path

import pytest

import plugins
from plugins.testing import check_loads, check_round_trip, check_validator
from plugins.validate import plugin_names
from tools.new_plugin import NewPluginError, create_plugin, main, used_prefixes

REPO_PLUGINS = Path("plugins")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A scratch plugins/ folder with the template in it, importable as part of the ``plugins`` package."""
    plugins_dir = tmp_path / "plugins"
    tests_dir = tmp_path / "tests" / "test_plugins"
    plugins_dir.mkdir()
    tests_dir.mkdir(parents=True)
    shutil.copytree(REPO_PLUGINS / "default_plugin", plugins_dir / "default_plugin",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (plugins_dir / "default_plugin" / "fonts").mkdir(exist_ok=True)   # git keeps no empty folder: a fresh clone lacks it
    monkeypatch.setattr(plugins, "__path__", [*plugins.__path__, str(plugins_dir)])
    yield plugins_dir, tests_dir
    for name in [name for name in sys.modules if name.startswith("plugins.demo_game")]:
        del sys.modules[name]


def test_the_generated_plugin_loads_round_trips_and_validates(workspace):
    plugins_dir, tests_dir = workspace

    written = create_plugin("demo_game", 'Demo "Quest"', "DMG", plugins_dir, tests_dir)

    rules = check_loads("demo_game")
    assert rules.get_display_name() == 'Demo "Quest"'
    assert rules.problem_prefix == "DMG" and "DMG_WIDTH_EXCEEDED" in rules.get_problem_definitions()
    assert rules.get_default_script_name() == "demo_game_script.md"
    check_round_trip("demo_game", "First line\nSecond line\n\nNext block")
    check_validator("demo_game", root=plugins_dir)
    assert "demo_game" in plugin_names(plugins_dir)                   # the application would list it
    assert {path.name for path in written} >= {"config.json", "rules.py", "config.py", "tag_manager.py", "test_rules.py"}


def test_the_config_is_renamed_and_the_template_s_own_files_are_left_behind(workspace):
    plugins_dir, tests_dir = workspace

    create_plugin("demo_game", "Demo Game", "DMG", plugins_dir, tests_dir)

    config = json.loads((plugins_dir / "demo_game" / "config.json").read_text(encoding="utf-8"))
    assert config["display_name"] == "Demo Game"
    assert all(key.startswith("DMG_") for key in config["autofix_enabled"])
    assert all(key.startswith("DMG_") for key in config["detection_enabled"])
    present = {path.name for path in (plugins_dir / "demo_game").iterdir()}
    assert not present & {"README.md", "AI_PLUGIN_ASSISTANT_PROMPT.md", "aliases.json", "__pycache__"}
    assert {"fonts", "translation_prompts", "font_map.json"} <= present


def test_the_generated_test_file_uses_the_shared_checks_and_passes(workspace):
    plugins_dir, tests_dir = workspace
    create_plugin("demo_game", "Demo Game", "DMG", plugins_dir, tests_dir)

    source = (tests_dir / "test_demo_game" / "test_rules.py").read_text(encoding="utf-8")
    namespace = {}
    exec(compile(source, "test_rules.py", "exec"), namespace)

    assert 'PLUGIN = "demo_game"' in source and (tests_dir / "test_demo_game" / "__init__.py").is_file()
    namespace["test_the_plugin_loads"]()
    namespace["test_the_sample_survives_load_and_save"]()


@pytest.mark.parametrize("plugin_id, name, prefix, reason", [
    ("Demo", "Demo", "DM", "lowercase"),
    ("1demo", "Demo", "DM", "lowercase"),
    ("demo", "Demo", "dm", "uppercase"),
    ("demo", "  ", "DM", "display name"),
    ("demo", "Demo", "DEFAULT", "already used"),
    ("default_plugin", "Demo", "DM", "already exists"),
])
def test_a_bad_request_is_refused_before_anything_is_written(workspace, plugin_id, name, prefix, reason):
    plugins_dir, tests_dir = workspace
    before = sorted(p.as_posix() for p in plugins_dir.rglob("*"))

    with pytest.raises(NewPluginError, match=reason):
        create_plugin(plugin_id, name, prefix, plugins_dir, tests_dir)

    assert sorted(p.as_posix() for p in plugins_dir.rglob("*")) == before and list(tests_dir.iterdir()) == []


def test_prefixes_of_the_shipped_plugins_are_known():
    assert {"DEFAULT", "ZMC", "ZWW", "ZBMG"} <= used_prefixes(REPO_PLUGINS)


def test_the_command_line_reports_an_error_and_writes_nothing(capsys):
    assert main(["zelda_mc", "Again", "--prefix", "ZX"]) == 1
    assert "already exists" in capsys.readouterr().err
