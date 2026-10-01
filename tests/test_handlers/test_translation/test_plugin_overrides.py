"""User edits (prompts, aliases) must land outside plugins/ (audit WP0 0.3)."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import utils.constants as constants
from handlers.translation.glossary_prompt_manager import GlossaryPromptManager


def _manager(tmp_path, project_dir=None):
    mw = SimpleNamespace(
        active_game_plugin="plain_text",
        project_manager=SimpleNamespace(project_dir=str(project_dir) if project_dir else None),
    )
    return GlossaryPromptManager(mw, MagicMock(), MagicMock())


def test_prompt_edit_without_project_goes_to_settings_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path / "settings")
    pm = _manager(tmp_path)
    assert pm.save_prompt_section("translation", "system_prompt", "X")
    target = tmp_path / "settings" / "plugins" / "plain_text" / "prompts.json"
    assert json.loads(target.read_text("utf-8"))["translation"]["system_prompt"] == "X"
    assert pm._resolve_file("prompts.json", "plain_text") == target


def test_prompt_edit_with_project_goes_to_project_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path / "settings")
    pm = _manager(tmp_path, project_dir=tmp_path / "proj")
    assert pm.save_prompt_section("glossary", "prompt_template", "T")
    target = tmp_path / "proj" / "plugin_overrides" / "plain_text" / "prompts.json"
    assert target.exists()
    assert not (tmp_path / "settings").exists()


def test_aliases_saved_to_settings_dir_and_mock_plugin_skipped(tmp_path, monkeypatch):
    from core.settings.plugin_settings import PluginSettings
    monkeypatch.setattr(constants, "SETTINGS_DIR", tmp_path)
    mw = MagicMock()
    mw.active_game_plugin = "plain_text"
    mw.default_tag_mappings = {"[a]": "{b}"}
    ps = PluginSettings(mw)
    ps._get_project_settings_path = lambda: None
    ps.save()
    assert json.loads((tmp_path / "plugins" / "plain_text" / "aliases.json").read_text("utf-8")) == {"[a]": "{b}"}

    mw.active_game_plugin = MagicMock()  # must not create a "MagicMock" directory anywhere
    ps.save()
    assert sorted(p.name for p in (tmp_path / "plugins").iterdir()) == ["plain_text"]
