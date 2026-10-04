"""The Tears of the Kingdom plugin: loading and saving MSBT text, and a romfs project end to end."""
from types import SimpleNamespace

import pytest

import core.containers.container_manager as container_manager
from core.data_state_processor import DataStateProcessor
from core.project_manager import ProjectManager
from core.project_models import Project
from handlers.project_action.load_worker import ProjectLoadWorker
from plugins.testing import check_loads, check_round_trip, check_validator
from plugins.zelda_totk import sarc as sarc_module
from plugins.common.msbt import Msbt
from plugins.zelda_totk.rules import GameRules

from . import samples

PLUGIN = "zelda_totk"
SAMPLE = samples.msbt([
    ("Talk_00", samples.text("Hello, ", ("tag", 2, 29, b""), "!")),
    ("Talk_01", samples.text(("tag", 0, 3, b"\x02\x00"), "Red", ("end", 0, 3), "\nSecond line")),
])
SAMPLE_TEXT = ["Hello, {playerName}!", "{color:2}Red{/color}\nSecond line"]


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    """The plugin registers its archive type and dictionary folders; keep that out of other tests."""
    monkeypatch.setattr(container_manager, "_CONTAINER_TYPES", list(container_manager._CONTAINER_TYPES))
    monkeypatch.setattr(container_manager, "_ARCHIVE_EXTENSIONS", list(container_manager._ARCHIVE_EXTENSIONS))
    monkeypatch.setattr(sarc_module, "dictionary_dirs", sarc_module.dictionary_dirs)


def test_the_plugin_loads():
    check_loads(PLUGIN)


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_the_validator_passes():
    check_validator(PLUGIN)


def test_messages_load_with_readable_tags():
    assert GameRules().load_data_from_json_obj(SAMPLE)[0] == [SAMPLE_TEXT]


def test_unchanged_text_saves_the_same_bytes_and_edits_keep_their_tags():
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE

    saved = rules.save_data_to_json_obj([["Привіт, {playerName}!", SAMPLE_TEXT[1]]], names)

    assert Msbt(saved).labels == {0: "Talk_00", 1: "Talk_01"}
    assert GameRules().load_data_from_json_obj(saved)[0] == [["Привіт, {playerName}!", SAMPLE_TEXT[1]]]


def test_the_archive_type_is_registered_for_zs_files():
    GameRules()
    assert sarc_module.SarcContainer in container_manager._CONTAINER_TYPES
    assert ".zs" in container_manager.ContainerManager.extensions()


def test_tags_are_explained():
    assert "colour" in GameRules().get_tag_tooltip("{color:2}")


def test_a_romfs_project_imports_loads_and_saves_a_mod(tmp_path):
    """romfs/Mals/USen.Product.121.sarc.zs in, mod/romfs/Mals/USen.Product.121.sarc.zs out."""
    zstd = pytest.importorskip("compression.zstd")
    archive_path = "Mals/USen.Product.121.sarc.zs"
    source = tmp_path / "romfs"
    (source / "Mals").mkdir(parents=True)
    other = samples.msbt([("Name", samples.text("Untouched"))])
    archive = samples.sarc({"EventFlowMsg/Npc_Hestu.msbt": SAMPLE, "StaticMsg/Item.msbt": other})
    (source / archive_path).write_bytes(zstd.compress(archive))
    manager = ProjectManager()
    manager.project_dir = str(tmp_path)
    manager.project_file_path = str(tmp_path / "project.uiproj")
    manager.project = Project(name="TotK", plugin_name=PLUGIN)
    manager.project.metadata = {
        "source_path": str(source),
        "translation_path": str(tmp_path / "mod" / "romfs"),
        "is_directory_mode": True,
    }
    rules = GameRules()

    manager.sync_project_files(plugin=rules)
    assert sorted(block.name for block in manager.project.blocks) == ["Item", "Npc_Hestu"]

    results = []
    worker = ProjectLoadWorker(manager, rules)
    worker.finished_with_result.connect(results.append)
    worker.run()
    loaded = results[0]
    hestu = int(next(index for index, name in loaded["block_names"].items() if name == "Npc_Hestu"))
    assert loaded["data"][hestu] == SAMPLE_TEXT

    rules.mw = SimpleNamespace(project_manager=manager, block_to_project_file_map=loaded["block_to_project_file_map"])
    assert rules.get_scene_context_for_string(hestu, 1) == {"resource": "EventFlowMsg/Npc_Hestu.msbt", "label": "Talk_01"}
    assert rules.get_ai_flow_context_for_string(hestu, 0) == "Message file EventFlowMsg/Npc_Hestu.msbt, label Talk_00"

    output = [list(block) for block in loaded["data"]]
    output[hestu][0] = "Привіт, {playerName}!"
    mw = SimpleNamespace(
        state=None,
        project_manager=manager,
        current_game_rules=rules,
        block_to_project_file_map=loaded["block_to_project_file_map"],
        data_store=SimpleNamespace(block_names=loaded["block_names"], edited_data={(hestu, 0): output[hestu][0]}),
    )
    saved, _warnings, errors = DataStateProcessor(mw)._perform_save_impl(output)
    assert (saved, errors) == (True, [])

    mod = sarc_module.SarcContainer((tmp_path / "mod" / "romfs" / archive_path).read_bytes())
    assert mod.read_file("StaticMsg/Item.msbt") == other
    hestu_file = mod.read_file("EventFlowMsg/Npc_Hestu.msbt")
    assert GameRules().load_data_from_json_obj(hestu_file)[0] == [["Привіт, {playerName}!", SAMPLE_TEXT[1]]]
    assert Msbt(hestu_file).labels == {0: "Talk_00", 1: "Talk_01"}
