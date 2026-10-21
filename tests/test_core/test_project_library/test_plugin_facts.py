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
        {"id": "base", "label": "Base game", "multiple": False}, {"id": "update", "label": "Update", "multiple": False},
        {"id": "ghost", "label": "ghost", "multiple": False}, {"id": "dlc", "label": "DLC", "multiple": True}]
    assert plugin_facts.platforms_of(rules) == [{"id": "3ds", "label": "Nintendo 3DS"}]
    assert plugin_facts.targets_of(rules) == [
        {"id": "patch", "label": "Patch", "platforms": ["3ds"], "kind": "patch"}]


def test_every_game_offers_base_update_and_many_dlc():
    roles = plugin_facts.roles_of(BaseGameRules())
    assert [(role["id"], role["multiple"]) for role in roles] == [("base", False), ("update", False), ("dlc", True)]


def test_repeated_role_keys_keep_their_order():
    sources = {"base": "b", "dlc_3": "d3", "dlc": "d1", "dlc_2": "d2", "dlcx": "no"}
    assert [plugin_facts.role_key("dlc", i) for i in (1, 2, 3)] == ["dlc", "dlc_2", "dlc_3"]
    assert plugin_facts.paths_of_role(sources, "dlc") == ["d1", "d2", "d3"]


@pytest.mark.parametrize("found, expected", [
    ({"kind": "switch", "title_id": "0100C0000CEEA000", "title_kind": "base"}, ("base", "switch")),
    ({"kind": "switch", "title_id": "0100C0000CEEA800", "title_kind": "update"}, ("update", "switch")),
    ({"kind": "switch", "title_id": "0100C0000CEEB001", "title_kind": "dlc"}, ("dlc", "switch")),
    ({"kind": "3ds", "title_id": "0004000E00167700"}, ("update", "3ds")),
    ({"kind": "3ds", "title_id": "0004008C00167701"}, ("dlc", "3ds")),
    ({"kind": "3ds", "title_id": "0004000000167700"}, ("base", "3ds")),
    ({"kind": "gc", "game_id": "GZ2E01"}, ("base", "gc")),
    (None, ("", "")),
])
def test_the_header_gives_role_and_platform(found, expected):
    identity = plugin_facts.generic_identity(found)
    assert (identity["role"], identity["platform"]) == expected


class NoUnpackRules(BaseGameRules):
    """A game that reads loose files only: no unpack of its own."""


def test_a_game_image_without_an_unpack_is_unreadable_and_a_folder_is_fine(tmp_path, monkeypatch):
    image = tmp_path / "game.nsz"
    image.write_bytes(b"x")
    folder = tmp_path / "unpacked"
    folder.mkdir()
    monkeypatch.setattr(plugin_facts.images, "identify", lambda path: (
        {"kind": "switch", "title_id": "0100C0000CEEA800", "title_kind": "update", "encrypted": True}
        if str(path).endswith(".nsz") else None))
    by_path = {item["path"]: item for item in plugin_facts.identify_sources(NoUnpackRules(), [str(image), str(folder)])}
    assert (by_path[str(image)]["role"], by_path[str(image)]["platform"]) == ("update", "switch")
    assert by_path[str(image)]["status"] == plugin_facts.STATUS_UNREADABLE
    assert by_path[str(image)]["key"] == ""        # no key is asked for: this game cannot read the file anyway
    assert by_path[str(folder)]["status"] == plugin_facts.STATUS_FOLDER


class UpdateLabelRules(BaseGameRules):
    def get_source_roles(self):
        return [{"id": "base", "label": "Основна гра"}, {"id": "update", "label": "Оновити"}]


def test_generic_role_names_stay_english_whatever_the_plugin_label():
    assert [role["label"] for role in plugin_facts.roles_of(UpdateLabelRules())] == ["Base game", "Update", "DLC"]


def _mark(folder, relative, data=b"x"):
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return folder


def test_an_unpacked_folder_tells_its_platform(tmp_path):
    assert plugin_facts.folder_platform(str(_mark(tmp_path / "wiiu", "meta/meta.xml"))) == "wiiu"
    assert plugin_facts.folder_platform(str(_mark(tmp_path / "ctr", "exefs/code.bin"))) == "3ds"
    assert plugin_facts.folder_platform(str(_mark(tmp_path / "nx", "game/exefs/main.npdm"))) == "switch"
    gc = _mark(_mark(tmp_path / "gc", "sys/main.dol"), "sys/boot.bin", b"GZ2E01")
    wii = _mark(_mark(tmp_path / "wii", "sys/main.dol"), "sys/boot.bin", b"RZDE01")
    assert (plugin_facts.folder_platform(str(gc)), plugin_facts.folder_platform(str(wii))) == ("gc", "wii")
    (tmp_path / "plain").mkdir()
    assert plugin_facts.folder_platform(str(tmp_path / "plain")) == ""


class OnePlatformRules(BaseGameRules):
    def get_platforms(self):
        return [{"id": "3ds", "label": "Nintendo 3DS"}]


def test_a_folder_of_a_one_platform_game_gets_that_platform(tmp_path):
    [item] = plugin_facts.identify_sources(OnePlatformRules(), [str(tmp_path)])
    assert (item["platform"], item["status"]) == ("3ds", plugin_facts.STATUS_FOLDER)
    [unknown] = plugin_facts.identify_sources(NoUnpackRules(), [str(tmp_path)])
    assert unknown["platform"] == ""


def test_a_game_without_platforms_offers_every_known_platform():
    assert plugin_facts.offered_platforms(OnePlatformRules()) == [{"id": "3ds", "label": "Nintendo 3DS"}]
    offered = [platform["id"] for platform in plugin_facts.offered_platforms(NoUnpackRules())]
    assert offered == list(plugin_facts.KNOWN_PLATFORMS) and "wiiu" in offered


def test_a_wii_u_disc_image_is_named_but_not_read(tmp_path):
    wux = tmp_path / "game.wux"
    wux.write_bytes(plugin_facts.WUX_MAGIC + b"\0" * 60)
    [item] = plugin_facts.identify_sources(NoUnpackRules(), [str(wux)])
    assert (item["platform"], item["status"]) == ("wiiu", plugin_facts.STATUS_UNREADABLE)
    assert plugin_facts.platform_label("wiiu") == "Wii U"


def test_identification_drops_undeclared_roles_and_survives_a_failing_plugin(tmp_path):
    paths = [str(tmp_path / n) for n in ("update.bin", "stranger.bin", "broken.bin", "unknown.bin")]

    result = plugin_facts.identify_sources(FakeRules(), paths)

    # The fake game ships on one platform, so a file it does not recognise is still on that platform.
    assert [(item["role"], item["platform"]) for item in result] == [
        ("update", "3ds"), ("", "3ds"), ("", "3ds"), ("", "3ds")]


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


def test_count_project_parses_a_file_read_in_place_once_per_role(tmp_path):
    """One file is both source and translation (several languages in it): the translation side is parsed in the
    translation role, not taken from the source parse."""
    class RoleRules(FakeRules):
        role = "source"

        def set_load_role(self, role):
            self.role = role

        def load_data_from_json_obj(self, json_obj):
            return [[entry[self.role] for entry in json_obj]], {}

    (tmp_path / "a.json").write_text(json.dumps([{"source": "Hi", "translation": "Привіт"},
                                                 {"source": "Bye", "translation": "Bye"}]), encoding="utf-8")
    project = _project(tmp_path, [{"source_file": "a.json", "translation_file": "a.json"}])

    result = plugin_facts.count_project(project, load_rules=_loader(RoleRules()))

    assert result["counts"] == {"lines": 2, "needs_translation": 2, "translated": 1}


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


def test_count_project_counts_the_blocks_whose_translation_file_is_missing(tmp_path):
    (tmp_path / "source.json").write_text(json.dumps([["Hi"]]), encoding="utf-8")
    (tmp_path / "translation.json").write_text(json.dumps([["Salut"]]), encoding="utf-8")
    project = _project(tmp_path, [
        {"source_file": "source.json", "translation_file": "none.json"},
        {"source_file": "source.json", "translation_file": "translation.json"},
        {"source_file": "source.json", "translation_file": ""},
    ])

    result = plugin_facts.count_project(project, load_rules=_loader(FakeRules()))

    # an empty translation name is not a missing file: only a named file that is absent counts
    assert result["missing_translations"] == 1
