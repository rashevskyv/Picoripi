"""A project file with an empty alias table (saved before the plugin shipped its aliases) keeps the plugin's aliases."""
import json
from types import SimpleNamespace

from core.settings.plugin_settings import PluginSettings


def _mw(project_dir):
    return SimpleNamespace(
        active_game_plugin="test_plugin",
        project_manager=SimpleNamespace(project_dir=str(project_dir)),
        data_store=SimpleNamespace(block_names={}, data=[]),
        block_color_markers={},
        string_metadata={},
        default_tag_mappings={},
        context_menu_tags={"single_tags": [], "wrap_tags": []},
        search_history_to_save=[],
    )


def test_an_empty_project_alias_table_keeps_the_plugin_aliases(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"default_tag_mappings": {"{Nash left#06}": "{FA:06}"}}), encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "project_settings.json").write_text(json.dumps({"default_tag_mappings": {}}), encoding="utf-8")
    mw = _mw(project)
    settings = PluginSettings(mw)
    monkeypatch.setattr(settings, "_get_plugin_config_path", lambda: config)
    settings.load({})
    assert mw.default_tag_mappings == {"{Nash left#06}": "{FA:06}"}


def test_a_project_alias_wins_over_the_plugin_alias_with_the_same_name(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"default_tag_mappings": {"{Nash left#06}": "{FA:06}"}}), encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "project_settings.json").write_text(
        json.dumps({"default_tag_mappings": {"{Nash left#06}": "{FA:07}", "{Mia#10}": "{FA:10}"}}), encoding="utf-8")
    mw = _mw(project)
    settings = PluginSettings(mw)
    monkeypatch.setattr(settings, "_get_plugin_config_path", lambda: config)
    settings.load({})
    assert mw.default_tag_mappings == {"{Nash left#06}": "{FA:07}", "{Mia#10}": "{FA:10}"}
