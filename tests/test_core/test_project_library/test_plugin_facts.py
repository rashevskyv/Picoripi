"""What the Project Manager reads from a plugin: roles, platforms, targets, identification and string counts.

The plugin is replaced by an explicit fake passed as ``load_rules``; no plugin module is imported here.
"""
import json

import pytest

from core.project_library import plugin_facts
from plugins.base_game_rules import BaseGameRules


class FakeRules(BaseGameRules):
    """A small game: two roles, one platform, one build target; a JSON file is a list of blocks of lines."""

    def get_source_roles(self):
        return [{"id": "base", "label": "Base game"}, {"id": "update", "label": "Update"}, {"id": "ghost"}]

    def get_platforms(self):
        return [{"id": "3ds", "label": "Nintendo 3DS"}]

    def get_build_targets(self):
        return [{"id": "patch", "label": "Patch", "platforms": ["3ds"], "kind": "patch"}]

    def identify_source(self, path):
        if path.endswith("update.bin"):
            return {"role": "update", "platform": "3ds"}
        if path.endswith("broken.bin"):
            raise RuntimeError("bad header")
        if path.endswith("stranger.bin"):
            return {"role": "not_declared", "platform": "3ds"}
        return None

    def load_data_from_json_obj(self, json_obj):
        return json_obj, {}


def _loader(rules):
    return lambda plugin_name: rules


def _project(tmp_path, blocks, metadata=None):
    project_file = tmp_path / "picoripi" / "project.uiproj"
    project_file.parent.mkdir(parents=True)
    default_roots = {"source_path": str(tmp_path), "translation_path": str(tmp_path)}
    project_file.write_text(json.dumps({"plugin_name": "fake", "blocks": blocks,
                                        "metadata": metadata or default_roots}),
                            encoding="utf-8")
    return project_file


def test_roles_platforms_and_targets_are_normalised():
    rules = FakeRules()

    assert plugin_facts.roles_of(rules) == [
        {"id": "base", "label": "Base game"}, {"id": "update", "label": "Update"}, {"id": "ghost", "label": "ghost"}]
    assert plugin_facts.platforms_of(rules) == [{"id": "3ds", "label": "Nintendo 3DS"}]
    assert plugin_facts.targets_of(rules) == [
        {"id": "patch", "label": "Patch", "platforms": ["3ds"], "kind": "patch"}]


def test_a_plugin_without_roles_gets_one_base_role():
    assert plugin_facts.roles_of(BaseGameRules()) == [{"id": "base", "label": "Base game"}]


def test_identification_drops_undeclared_roles_and_survives_a_failing_plugin(tmp_path):
    paths = [str(tmp_path / n) for n in ("update.bin", "stranger.bin", "broken.bin", "unknown.bin")]

    result = plugin_facts.identify_sources(FakeRules(), paths)

    assert [(item["role"], item["platform"]) for item in result] == [
        ("update", "3ds"), ("", ""), ("", ""), ("", "")]


def test_identification_stops_when_cancelled(tmp_path):
    paths = [str(tmp_path / "update.bin"), str(tmp_path / "update.bin")]
    calls = iter([False, True])

    result = plugin_facts.identify_sources(FakeRules(), paths, is_cancelled=lambda: next(calls))

    assert len(result) == 1


def test_count_project_counts_translated_lines_per_block(tmp_path):
    (tmp_path / "source").mkdir()
    (tmp_path / "translation").mkdir()
    (tmp_path / "source" / "a.json").write_text(json.dumps([["Hi", "Bye"]]), encoding="utf-8")
    (tmp_path / "translation" / "a.json").write_text(json.dumps([["Salut", "Bye"]]), encoding="utf-8")
    project = _project(tmp_path, [{"source_file": "a.json", "translation_file": "a.json"}],
                       metadata={"source_path": str(tmp_path / "source"),
                                 "translation_path": str(tmp_path / "translation")})

    result = plugin_facts.count_project(project, load_rules=_loader(FakeRules()))

    assert result["counts"] == {"lines": 2, "needs_translation": 2, "translated": 1}
    assert result["skipped"] == 0
    assert result["targets"][0]["id"] == "patch"
    assert result["groups"] == {"(top level)": {"blocks": 1, "lines": 2}}


def test_count_project_uses_the_internal_key_of_a_split_file(tmp_path):
    class NamedRules(FakeRules):
        def load_data_from_json_obj(self, json_obj):
            return json_obj["blocks"], json_obj["names"]

    (tmp_path / "source.json").write_text(json.dumps({
        "blocks": [["one", "uno"], ["two"]], "names": {"0": "Menu", "1": "Dialogue"}}), encoding="utf-8")
    project = _project(tmp_path, [{"source_file": "source.json", "translation_file": "missing.json",
                                   "internal_key": "Dialogue"}])

    result = plugin_facts.count_project(project, load_rules=_loader(NamedRules()))

    assert result["counts"]["lines"] == 1
    assert result["skipped"] == 0


def test_count_project_skips_archive_members_and_missing_files(tmp_path):
    (tmp_path / "source.json").write_text(json.dumps([["Hi"]]), encoding="utf-8")
    project = _project(tmp_path, [
        {"source_file": "source.json", "translation_file": "none.json"},
        {"source_file": "inside.arc", "translation_file": "x", "metadata": {"is_archive_member": True}},
        {"source_file": "gone.json", "translation_file": "gone.json"},
    ])

    result = plugin_facts.count_project(project, load_rules=_loader(FakeRules()))

    assert result["counts"] == {"lines": 1, "needs_translation": 1, "translated": 0}
    assert result["skipped"] == 2


def test_count_project_returns_none_when_cancelled(tmp_path):
    (tmp_path / "source.json").write_text(json.dumps([["Hi"]]), encoding="utf-8")
    project = _project(tmp_path, [{"source_file": "source.json", "translation_file": "source.json"}])

    assert plugin_facts.count_project(project, load_rules=_loader(FakeRules()), is_cancelled=lambda: True) is None


def test_count_project_skips_binary_files_without_reading_them_as_text(tmp_path, monkeypatch):
    """A font of a game is no text: the counter must not hand it to the text loader (Metal Gear fonts did)."""
    (tmp_path / "font.res").write_bytes(b"\x00\xff\xfe\x80" * 64)
    (tmp_path / "source.json").write_text(json.dumps([["Hi"]]), encoding="utf-8")
    project = _project(tmp_path, [
        {"source_file": "font.res", "translation_file": "font.res"},
        {"source_file": "source.json", "translation_file": "source.json"},
    ])
    text_loads = []
    real_load_text = plugin_facts.formats.load_text_file

    def spy(path, newline=None):
        text_loads.append(str(path))
        return real_load_text(path, newline=newline)

    monkeypatch.setattr(plugin_facts.formats, "load_text_file", spy)

    result = plugin_facts.count_project(project, load_rules=_loader(FakeRules()))

    assert text_loads == []  # the .res font is unclaimed: no text load; the JSON block loads as JSON
    assert result["counts"]["lines"] == 1
    assert result["skipped"] == 1


def test_count_project_names_a_missing_plugin_instead_of_failing(tmp_path):
    (tmp_path / "source.json").write_text(json.dumps([["Hi"]]), encoding="utf-8")
    project = _project(tmp_path, [{"source_file": "source.json", "translation_file": "source.json"}])

    def loader(plugin_name):
        raise ModuleNotFoundError(f"No module named 'plugins.{plugin_name}'", name=f"plugins.{plugin_name}")

    with pytest.raises(plugin_facts.PluginMissing) as caught:
        plugin_facts.count_project(project, load_rules=loader)
    assert str(caught.value) == "fake"
