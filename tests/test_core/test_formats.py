"""A plugin declares the files it reads; the host loads and saves them without knowing the format (WP5 5.5)."""
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core import formats
from core.containers import ContainerManager
from core.containers.base_container import BaseArchiveContainer
from core.data_processor.session_manager import SessionManager
from core.data_state_processor import DataStateProcessor
from core.formats import DEFAULT_FORMATS, FileFormat, SaveContext
from core.project_manager import ProjectManager
from core.project_models import Project
from handlers.project_action.load_worker import ProjectLoadWorker
from plugins.base_game_rules import BaseGameRules
from plugins.pokemon_fr.rules import GameRules as PokemonRules
from plugins.zelda_bmg.rules import GameRules as ZeldaBmgRules


class TableRules(BaseGameRules):
    """A game whose text lives in a binary table: strings separated by a zero byte, blocks by 0xFF."""

    def get_file_formats(self):
        return [FileFormat((".tbl",), "bytes", "Text tables"), *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, content):
        if not isinstance(content, (bytes, bytearray)):
            return super().load_data_from_json_obj(content)
        blocks = [[s.decode("utf-8") for s in block.split(b"\x00") if s] for block in bytes(content).split(b"\xff")]
        return blocks, {str(i): f"Table {i}" for i in range(len(blocks))}

    def save_data_to_json_obj(self, data, block_names):
        return b"\xff".join(b"\x00".join(s.encode("utf-8") for s in block) for block in data)


TABLE = b"Hello\x00World\xffSecond table"


class TestFormats:
    def test_the_defaults_are_json_and_text(self):
        assert formats.file_formats(BaseGameRules()) == DEFAULT_FORMATS
        assert formats.file_formats(None) == DEFAULT_FORMATS
        assert formats.supported_extensions(BaseGameRules()) == {".json", ".txt"}

    def test_a_plugin_adds_its_own_and_the_extension_decides(self):
        rules = TableRules()

        assert formats.resolve(rules, "C:/game/TEXT.TBL").mode == "bytes"
        assert formats.resolve(rules, "a.json").mode == "json"
        assert formats.resolve(rules, "a.bin") is None
        assert formats.supported_extensions(rules) == {".tbl", ".json", ".txt"}

    def test_a_broken_or_useless_declaration_falls_back_to_the_defaults(self):
        broken = SimpleNamespace(get_file_formats=lambda: 1 / 0)
        useless = SimpleNamespace(get_file_formats=lambda: ["tbl", FileFormat((".x",), "pickle")])

        assert formats.file_formats(broken) == DEFAULT_FORMATS
        assert formats.file_formats(useless) == DEFAULT_FORMATS
        assert formats.file_formats(MagicMock()) == DEFAULT_FORMATS

    def test_each_mode_reads_and_writes_its_own_shape(self, tmp_path):
        rules = TableRules()

        assert formats.write_file(rules, tmp_path / "a.json", {"k": "значення"}) == (True, None)
        assert formats.write_file(rules, str(tmp_path / "a.txt"), "рядок") == (True, None)
        assert formats.write_file(rules, tmp_path / "sub" / "a.tbl", TABLE) == (True, None)

        assert formats.read_file(rules, tmp_path / "a.json") == ({"k": "значення"}, None)
        assert formats.read_file(rules, tmp_path / "a.txt") == ("рядок", None)
        assert formats.read_file(rules, tmp_path / "sub" / "a.tbl") == (TABLE, None)
        assert not list(tmp_path.rglob("*.tmp"))                  # the binary write left nothing behind

    def test_the_wrong_shape_is_refused_instead_of_written(self, tmp_path):
        rules = TableRules()

        ok, error = formats.write_file(rules, tmp_path / "a.tbl", "not bytes")
        assert (ok, error) == (False, "Plugin did not return bytes for .tbl file.")
        ok, error = formats.write_file(rules, tmp_path / "a.txt", {"not": "text"})
        assert (ok, error) == (False, "Plugin did not return a string for .txt file.")
        assert list(tmp_path.iterdir()) == []

    def test_an_extension_nobody_claims_is_an_error_or_text_as_the_caller_chooses(self, tmp_path):
        rules = BaseGameRules()
        (tmp_path / "a.bin").write_text("plain", encoding="utf-8")

        assert formats.read_file(rules, tmp_path / "a.bin") == (None, "Unsupported file type: .bin")
        assert formats.read_file(rules, tmp_path / "a.bin", unknown=formats.UNKNOWN_IS_TEXT) == ("plain", None)
        assert formats.write_file(rules, tmp_path / "b.bin", "x") == (False, "Unsupported file type: .bin")
        assert formats.write_file(rules, tmp_path / "b.bin", 12, unknown=formats.UNKNOWN_IS_TEXT) == (True, None)
        assert (tmp_path / "b.bin").read_text(encoding="utf-8") == "12"

    def test_a_failed_binary_write_leaves_the_old_file_whole(self, tmp_path, monkeypatch):
        rules = TableRules()
        target = tmp_path / "a.tbl"
        target.write_bytes(b"old")

        def refuse(source, destination):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", refuse)
        ok, error = formats.write_file(rules, target, b"new")

        assert ok is False and "disk full" in error and target.read_bytes() == b"old"

    def test_archive_members_are_decoded_by_the_format_of_their_name(self):
        rules = TableRules()

        assert formats.decode(rules, "dir/a.tbl", TABLE) == TABLE
        assert formats.decode(rules, "dir/a.json", b'\xef\xbb\xbf{"k": 1}') == {"k": 1}
        assert formats.decode(rules, "dir/a.txt", "текст".encode("utf-8")) == "текст"
        assert formats.decode(rules, "dir/a.unknown", b"raw") == b"raw"

    def test_the_file_dialog_lists_the_plugin_s_formats(self):
        assert formats.dialog_filter(TableRules()) == (
            "Supported Files (*.tbl *.json *.txt);;Text tables (*.tbl);;JSON (*.json);;Text files (*.txt);;All (*)"
        )


class TestThroughTheHost:
    """The custom format goes through project import, load and save without the host knowing it."""

    def _project(self, tmp_path):
        source = tmp_path / "src"
        source.mkdir()
        (source / "dialogue.tbl").write_bytes(TABLE)
        (source / "readme.md").write_text("not game text", encoding="utf-8")
        manager = ProjectManager()
        manager.project_dir = str(tmp_path)
        manager.project_file_path = str(tmp_path / "project.uiproj")
        manager.project = Project(name="Demo", plugin_name="demo")
        manager.project.metadata = {
            "source_path": str(source),
            "translation_path": str(tmp_path / "trans"),
            "is_directory_mode": True,
        }
        return manager

    def test_import_finds_the_plugin_s_files_and_only_those(self, tmp_path):
        manager = self._project(tmp_path)

        manager.sync_project_files(plugin=TableRules())

        assert [block.source_file for block in manager.project.blocks] == ["dialogue.tbl"]

    def test_a_plugin_without_the_format_does_not_import_them(self, tmp_path):
        manager = self._project(tmp_path)

        manager.sync_project_files(plugin=BaseGameRules())

        assert manager.project.blocks == []

    def test_load_and_save_round_trip(self, tmp_path):
        manager = self._project(tmp_path)
        rules = TableRules()
        manager.sync_project_files(plugin=rules)
        results = []
        worker = ProjectLoadWorker(manager, rules)
        worker.finished_with_result.connect(results.append)

        worker.run()

        loaded = results[0]
        assert loaded["data"] == [["Hello", "World"], ["Second table"]]
        assert loaded["block_names"] == {"0": "Table 0", "1": "Table 1"}

        mw = MagicMock()
        mw.state = None
        mw.project_manager = manager
        mw.current_game_rules = rules
        mw.block_to_project_file_map = loaded["block_to_project_file_map"]
        mw.data_store.block_names = loaded["block_names"]
        mw.data_store.edited_data = {(0, 1): "Світ"}
        saved, warnings, errors = DataStateProcessor(mw)._perform_save_impl([["Hello", "Світ"], ["Second table"]])

        assert (saved, warnings, errors) == (True, [], [])
        written = (tmp_path / "trans" / "dialogue.tbl").read_bytes()
        assert written == "Hello\x00Світ".encode("utf-8") + b"\xffSecond table"
        assert rules.load_data_from_json_obj(written)[0] == [["Hello", "Світ"], ["Second table"]]


class TestRuntimeState:
    def test_the_base_class_has_no_state(self):
        rules = BaseGameRules()

        assert rules.export_runtime_state() is None
        rules.restore_runtime_state(None)
        rules.reset_runtime_state()
        rules.prepare_save_context(SaveContext())

    def test_the_helpers_tolerate_an_object_without_the_hooks(self):
        bare = SimpleNamespace()

        assert formats.export_state(bare) is None
        formats.restore_state(bare, ["x"])
        formats.reset_state(bare)
        formats.prepare_save(bare, SaveContext())

    def test_pokemon_keys_travel_as_runtime_state(self):
        rules = PokemonRules()
        source = {"block_a": {"k1": "one", "k2": "two"}, "block_b": {"k3": "three"}}
        rules.load_data_from_json_obj(source)
        state = rules.export_runtime_state()

        rules.load_data_from_json_obj(source)                    # re-parsing appends keys again
        assert len(rules.original_keys) == 4
        rules.restore_runtime_state(state)
        assert rules.original_keys == [["k1", "k2"], ["k3"]]

        assert json.loads(json.dumps(state)) == state            # plain data, fit for the session file
        rules.reset_runtime_state()
        assert rules.original_keys == []

    def test_pokemon_narrows_its_keys_to_the_file_being_saved(self):
        rules = PokemonRules()
        rules.load_data_from_json_obj({"block_a": {"k1": "one"}, "block_b": {"k2": "two"}})
        state = rules.export_runtime_state()

        rules.prepare_save_context(SaveContext(block_indices=[1], runtime_state=state))
        saved = rules.save_data_to_json_obj([["два"]], {"0": "block_b"})
        assert saved == {"block_b": {"k2": "два"}}

        rules.prepare_save_context(SaveContext(block_indices=[5], runtime_state=state))   # incomplete snapshot
        assert rules.original_keys == [["k2"]]                                                  # left as it was
        rules.restore_runtime_state(state)
        assert rules.original_keys == [["k1"], ["k2"]]

    def test_the_session_stores_and_restores_what_the_plugin_exports(self):
        rules = MagicMock()
        processor = SimpleNamespace(mw=SimpleNamespace(current_game_rules=rules, ui_updater=None))
        manager = SessionManager(processor)

        rules.export_runtime_state.return_value = [["k1"], ["k2"]]
        assert manager._attach_runtime_session_state({})["plugin_original_keys"] == [["k1"], ["k2"]]
        rules.export_runtime_state.return_value = {"cursor": 3}
        assert manager._attach_runtime_session_state({}) == {"plugin_runtime_state": {"cursor": 3}}
        rules.export_runtime_state.return_value = None
        assert manager._attach_runtime_session_state({}) == {}

        manager._restore_runtime_session_state({"plugin_original_keys": [["k1"]]})
        rules.restore_runtime_state.assert_called_with([["k1"]])
        manager._restore_runtime_session_state({"plugin_runtime_state": {"cursor": 3}})
        rules.restore_runtime_state.assert_called_with({"cursor": 3})
        rules.restore_runtime_state.reset_mock()
        manager._restore_runtime_session_state({})
        rules.restore_runtime_state.assert_not_called()


class TestZeldaBmg:
    def test_it_declares_its_binary_files(self):
        rules = ZeldaBmgRules()

        assert formats.resolve(rules, "zel_00.bmg").mode == "bytes"
        assert formats.resolve(rules, "font.bfn").mode == "bytes"
        assert {".json", ".txt"} <= formats.supported_extensions(rules)

    def test_before_a_save_it_loads_the_newest_version_that_parses(self, monkeypatch):
        import plugins.zelda_bmg.bmg_tool as bmg_tool

        class FakeBmg:
            def load(self, raw):
                if raw == b"corrupt":
                    raise ValueError("bad header")
                self.raw = raw

        monkeypatch.setattr(bmg_tool, "BMGFile", FakeBmg)
        rules = ZeldaBmgRules()
        read = []

        def versions():
            for raw in (b"corrupt", b"source bytes", b"never read"):
                read.append(raw)
                yield raw

        rules.prepare_save_context(SaveContext(relative_path="zel_00.bmg", existing_versions=versions))

        assert rules.last_loaded_bmg.raw == b"source bytes"
        assert read == [b"corrupt", b"source bytes"]             # stopped at the first that parsed

    def test_nothing_readable_leaves_the_loaded_file_as_it_was(self):
        rules = ZeldaBmgRules()
        rules.last_loaded_bmg = "kept"

        rules.prepare_save_context(SaveContext())

        assert rules.last_loaded_bmg == "kept"

    def test_the_old_import_path_of_the_parser_still_works(self):
        import bmg_tool
        from plugins.zelda_bmg.bmg_tool import BMGFile

        assert bmg_tool.BMGFile is BMGFile


class TestExistingVersions:
    def _processor(self, tmp_path, container=None):
        mw = MagicMock()
        mw.state = None
        mw.project_manager.get_absolute_path.side_effect = (
            lambda rel, is_translation=False: str(tmp_path / ("trans" if is_translation else "src") / rel)
        )
        mw.project_manager.get_archive_container.side_effect = container
        return DataStateProcessor(mw), mw

    def test_a_plain_file_is_read_from_the_translation_then_the_source(self, tmp_path):
        (tmp_path / "trans").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "trans" / "a.tbl").write_bytes(b"translated")
        (tmp_path / "src" / "a.tbl").write_bytes(b"original")
        processor, _mw = self._processor(tmp_path)

        assert list(processor._existing_versions("a.tbl")) == [b"translated", b"original"]

    def test_a_missing_version_is_skipped(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.tbl").write_bytes(b"original")
        processor, _mw = self._processor(tmp_path)

        assert list(processor._existing_versions("a.tbl")) == [b"original"]

    def test_an_archive_member_is_read_from_the_archives(self, tmp_path):
        def container(archive, is_translation=False):
            if is_translation:
                raise OSError("no translated archive yet")
            return SimpleNamespace(read_file=lambda inner: f"{archive}:{inner}".encode())

        processor, mw = self._processor(tmp_path, container)

        versions = list(processor._existing_versions(".extracted/translation/res/bmgres.arc/dir/zel_00.bmg"))

        assert versions == [b"res/bmgres.arc:dir/zel_00.bmg"]
        assert [call.kwargs for call in mw.project_manager.get_archive_container.call_args_list] == [
            {"is_translation": True}, {"is_translation": False},
        ]


class TestContainerRegistration:
    def test_a_plugin_can_add_an_archive_format(self, monkeypatch):
        import core.containers.container_manager as module

        monkeypatch.setattr(module, "_CONTAINER_TYPES", list(module._CONTAINER_TYPES))
        monkeypatch.setattr(module, "_ARCHIVE_EXTENSIONS", list(module._ARCHIVE_EXTENSIONS))

        class PackContainer(BaseArchiveContainer):
            def __init__(self, data):
                self.data = data

            @classmethod
            def can_handle(cls, data):
                return data.startswith(b"PACK")

            def list_files(self):
                return []

            def read_file(self, path):
                return b""

            def write_file(self, path, data):
                pass

            def pack(self):
                return self.data

        assert ContainerManager.open(b"PACK....") is None
        ContainerManager.register(PackContainer, extensions=(".PAK",))
        ContainerManager.register(PackContainer, extensions=(".pak",))        # twice changes nothing

        assert isinstance(ContainerManager.open(b"PACK...."), PackContainer)
        assert ContainerManager.extensions().count(".pak") == 1
        assert module._CONTAINER_TYPES.count(PackContainer) == 1

    def test_the_built_in_archive_extensions_are_listed(self):
        assert {".arc", ".rarc", ".ark"} <= set(ContainerManager.extensions())


@pytest.mark.parametrize("name", ["original_keys", "last_loaded_bmg"])
def test_host_code_no_longer_reaches_into_plugin_attributes(name):
    from pathlib import Path

    offenders = [
        path.as_posix()
        for root in ("core", "handlers", "ui", "components", "utils")
        for path in Path(root).rglob("*.py")
        if name in path.read_text(encoding="utf-8")
    ]
    # the session file keeps its historic key name; nothing else may mention them
    assert [p for p in offenders if p != "core/data_processor/session_manager.py"] == []
