"""Checks every plugin's own tests can start from.

``tools/new_plugin.py`` generates a test file that calls these three; the
shipped plugins are run through them too (``tests/test_plugins/test_plugin_smoke.py``).
They fail with plain ``AssertionError`` messages, so they work under pytest
and from a script alike.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Optional

from plugins.base_game_rules import BaseGameRules
from plugins.validate import PLUGINS_DIR, validate_plugin


def load_rules(name: str, main_window: Any = None) -> BaseGameRules:
    """The plugin's ``GameRules``, built the way the application builds it."""
    module = importlib.import_module(f"plugins.{name}.rules")
    return module.GameRules(main_window)


def check_loads(name: str) -> BaseGameRules:
    """The plugin imports, builds without a main window and names itself."""
    rules = load_rules(name)
    assert isinstance(rules, BaseGameRules), "GameRules must subclass BaseGameRules"
    display_name = rules.get_display_name()
    assert isinstance(display_name, str) and display_name.strip(), "get_display_name() must return a name"
    assert isinstance(rules.get_problem_definitions(), dict)
    return rules


def check_round_trip(name: str, sample: Any) -> None:
    """``sample`` loads into blocks of strings, and what is saved loads back the same."""
    rules = load_rules(name)
    blocks, block_names = rules.load_data_from_json_obj(sample)
    assert isinstance(blocks, list) and blocks, "the sample produced no blocks"
    assert all(isinstance(block, list) for block in blocks), "every block must be a list of strings"
    assert any(block for block in blocks), "the sample produced only empty blocks"
    assert isinstance(block_names, dict)

    saved = rules.save_data_to_json_obj(blocks, block_names)
    again, _names = load_rules(name).load_data_from_json_obj(saved)
    assert again == blocks, "saving and loading again changed the text"


def check_validator(name: str, root: Optional[Path] = None) -> None:
    """``python -m plugins.validate <name>`` reports no error."""
    report = validate_plugin(name, root or PLUGINS_DIR)
    assert report.ok, report.render()
