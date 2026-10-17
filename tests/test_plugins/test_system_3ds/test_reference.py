"""3DS system reference column on a worker: the parse reads the files the project held when it was started."""
from types import SimpleNamespace

from core.settings.plugin_settings import PluginSettings
from plugins.system_3ds.rules import GameRules
from test_plugins.test_system_3ds.test_rules import LAYOUT, STRINGS, _with_project


def _project_folder(tmp_path):
    folder = tmp_path / "strings" / "home_menu"
    folder.mkdir(parents=True)
    (folder / "message__menu.json").write_bytes(STRINGS)
    (tmp_path / "layouts").mkdir()
    (tmp_path / "layouts" / "system_settings.json").write_bytes(LAYOUT)
    return tmp_path


_FILES = ("layouts/system_settings.json", "strings/home_menu/message__menu.json")


def test_the_worker_copy_reads_the_files_the_project_held_when_it_was_made(tmp_path):
    root = _project_folder(tmp_path)
    rules = _with_project(GameRules(), *_FILES)
    copy, window = rules.reference_worker_rules()
    assert window is None and copy is not rules
    rules.mw = SimpleNamespace(project_manager=SimpleNamespace(project=SimpleNamespace(blocks=[])))

    assert copy.load_reference_patch(str(root)) == {(0, 0): "Выберите язык.", (1, 0): "Меню HOME"}
    assert rules.load_reference_patch(str(root)) == {}


def test_the_system_reference_is_parsed_on_a_worker_and_equals_the_synchronous_parse(qtbot, tmp_path):
    root = _project_folder(tmp_path)
    rules = _with_project(GameRules(), *_FILES)
    window = SimpleNamespace(current_game_rules=rules, reference_patch_path=str(root),
                             data_store=SimpleNamespace(block_names={}, reference_data={}, reference_languages_data={}))
    PluginSettings(window).load_reference()

    qtbot.waitUntil(lambda: bool(window.data_store.reference_data), timeout=10000)
    assert window.data_store.reference_data == rules.load_reference_patch(str(root))
    assert window.data_store.reference_languages_data == {"Russian (RU)": window.data_store.reference_data}
