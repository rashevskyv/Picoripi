"""A project file that opens into no text block (Luigi's Mansion's .picoripi_disc) must not shift the translation
of the files after it: the loader and an older session both keep the translation next to its own text block."""
from types import SimpleNamespace

from core.formats import DEFAULT_FORMATS, FileFormat
from core.project_manager import ProjectManager
from core.project_models import Project
from handlers.project_action.load_worker import ProjectLoadWorker
from handlers.project_action.session_mixin import SessionMixin
from plugins.base_game_rules import BaseGameRules


class TableRules(BaseGameRules):
    """One block per file; a file that holds only b"MARK" has no text block."""

    def get_file_formats(self):
        return [FileFormat((".tbl",), "bytes", "Text tables"), *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, content):
        if not isinstance(content, (bytes, bytearray)):
            return super().load_data_from_json_obj(content)
        if bytes(content) == b"MARK":
            return [], {}
        return [bytes(content).decode("utf-8").split("|")], {}


def _project(tmp_path):
    source, translation = tmp_path / "src", tmp_path / "trans"
    source.mkdir()
    translation.mkdir()
    for name, original, translated in (("a_mark.tbl", "MARK", "MARK"), ("b.tbl", "Hello|World", "Привіт|Світ"),
                                       ("c.tbl", "Bye", "Бувай")):
        (source / name).write_bytes(original.encode("utf-8"))
        (translation / name).write_bytes(translated.encode("utf-8"))
    manager = ProjectManager()
    manager.project_dir = str(tmp_path)
    manager.project_file_path = str(tmp_path / "project.uiproj")
    manager.project = Project(name="Demo", plugin_name="demo")
    manager.project.metadata = {"source_path": str(source), "translation_path": str(translation),
                                "is_directory_mode": True}
    return manager


def test_a_file_with_no_text_block_adds_no_translation_block(tmp_path):
    manager = _project(tmp_path)
    rules = TableRules()
    manager.sync_project_files(plugin=rules)
    assert [block.source_file for block in manager.project.blocks] == ["a_mark.tbl", "b.tbl", "c.tbl"]
    results = []
    worker = ProjectLoadWorker(manager, rules)
    worker.finished_with_result.connect(results.append)

    worker.run()

    assert results[0]["data"] == [["Hello", "World"], ["Bye"]]
    assert results[0]["edited_file_data"] == [["Привіт", "Світ"], ["Бувай"]]


def test_a_session_saved_with_the_shift_gets_its_translation_back_in_place():
    store = SimpleNamespace(data=[["Hello", "World"], ["Bye"]], edited_file_data=[[], ["Привіт", "Світ"], ["Бувай"]],
                            block_to_project_file_map={"0": 1, "1": 2}, edited_data={(1, 0): "Па"})
    mixin = SessionMixin()
    mixin.mw = SimpleNamespace(data_store=store,
                               project_manager=SimpleNamespace(project=SimpleNamespace(blocks=[object()] * 3)))

    mixin._realign_session_translation()

    assert store.edited_file_data == [["Привіт", "Світ"], ["Бувай"]]
    assert store.edited_data == {(1, 0): "Па"}
    mixin._realign_session_translation()   # an aligned session stays as it is
    assert store.edited_file_data == [["Привіт", "Світ"], ["Бувай"]]
