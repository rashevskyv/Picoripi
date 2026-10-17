"""3DS manual reference column: the English is read from the manuals the project holds, also after a state-only read.

A session without plugin state restores no manual; the host reads the project files once for that state on a worker.
The reference was parsed before that read, so its fingerprints named no manual and the English stayed empty.
"""
import json
import types
from types import SimpleNamespace

from core.data_processor.session_manager import SessionManager
from core.settings.plugin_settings import PluginSettings
from handlers.project_action.session_mixin import SessionMixin
from plugins.manual_3ds import rules as m3d

PAGE_KEY = "small/Page_003_small_0#1"
KEYS = {"one": ["index/Index#0", PAGE_KEY], "two": [PAGE_KEY, "index/Index#0"]}


def _document(keys, en):
    entries = {key: {"lines": 1, "width": 300.0, "en": en, "ru": "Text", "ua": "Text"} for key in keys}
    return json.dumps(entries, ensure_ascii=False)


def _manual_english(tmp_path):
    """A project of two manual files and a reference folder with their English (one file per manual)."""
    project, reference = tmp_path / "project", tmp_path / "reference"
    project.mkdir()
    reference.mkdir()
    for name, keys in KEYS.items():
        (project / f"{name}.json").write_text(_document(keys, "Text"), encoding="utf-8")
        (reference / f"{name}_en.json").write_text(_document(keys, "English"), encoding="utf-8")
    return project, reference


def test_the_reference_is_read_again_when_a_state_only_read_adds_the_manuals(qtbot, tmp_path):
    project, reference = _manual_english(tmp_path)
    blocks = [SimpleNamespace(name=name, source_file=f"{name}.json", translation_file=f"{name}.json",
                              internal_key=None, metadata={}) for name in KEYS]
    project_manager = SimpleNamespace(project=SimpleNamespace(blocks=blocks, virtual_folders=[]),
                                      project_dir=str(project), clear_archive_cache=lambda: None,
                                      get_absolute_path=lambda relative, is_translation=False: str(project / relative))
    rules = m3d.GameRules()
    scans, redraws = [], []
    window = SimpleNamespace(
        current_game_rules=rules, project_manager=project_manager,
        reference_patch_path=str(reference), active_game_plugin="manual_3ds",
        data_store=SimpleNamespace(edited_data={}, block_names={}, data=[], reference_data={},
                                   reference_languages_data={}),
        issue_scan_handler=SimpleNamespace(_perform_initial_silent_scan_all_issues=lambda force=False: scans.append(force)),
        custom_preview_widget=SimpleNamespace(refresh=lambda: redraws.append(True)))
    window.settings_manager = SimpleNamespace(plugin_settings=PluginSettings(window))
    sessions = SessionManager(SimpleNamespace(mw=window))
    sessions._restore_runtime_session_state({"data": []})  # a session of the old plugin: no plugin state
    owner = SimpleNamespace(mw=window, data_processor=SimpleNamespace(
        session_had_plugin_state=lambda: sessions.restored_plugin_state), _active_load_worker=None)
    owner._load_reference = types.MethodType(SessionMixin._load_reference, owner)

    # The session fast path reads the reference first: no manual is known yet, so no English.
    owner._load_reference()
    assert not window.data_store.reference_data

    SessionMixin._read_missing_plugin_state(owner)

    qtbot.waitUntil(lambda: bool(window.data_store.reference_data), timeout=10000)
    assert window.data_store.reference_data == {
        (0, 0): "English", (0, 1): "English", (1, 0): "English", (1, 1): "English"}
    assert scans == [True]


def _rules_with_manuals(tmp_path):
    project, reference = _manual_english(tmp_path)
    rules = m3d.GameRules()
    for name in KEYS:
        rules.load_data_from_json_obj((project / f"{name}.json").read_text(encoding="utf-8"))
    return rules, reference


def test_the_english_is_parsed_on_a_worker_and_equals_the_synchronous_parse(qtbot, tmp_path, monkeypatch):
    from core.reference_manager import ReferenceManager

    rules, reference = _rules_with_manuals(tmp_path)
    started = []
    original = ReferenceManager.load_in_background.__func__

    def spy(cls, *args, **kwargs):
        started.append(True)
        return original(cls, *args, **kwargs)

    monkeypatch.setattr(ReferenceManager, "load_in_background", classmethod(spy))
    window = SimpleNamespace(current_game_rules=rules, reference_patch_path=str(reference),
                             data_store=SimpleNamespace(block_names={}, reference_data={}, reference_languages_data={}))
    PluginSettings(window).load_reference()

    qtbot.waitUntil(lambda: bool(window.data_store.reference_data), timeout=10000)
    expected = ReferenceManager.load_multi_reference(str(reference), {}, game_rules=rules)
    assert started == [True], "the manual reference is parsed on a worker"
    assert window.data_store.reference_languages_data == expected
    assert window.data_store.reference_data == next(iter(expected.values()))


def test_the_worker_copy_keeps_the_manuals_it_was_made_with(tmp_path):
    rules, _reference = _rules_with_manuals(tmp_path)
    copy, window = rules.reference_worker_rules()
    assert window is None and copy is not rules
    rules.load_data_from_json_obj('{"x/Other#0": {"lines": 1, "width": 1.0, "en": "E", "ru": "R", "ua": "U"}}')
    assert len(copy._manuals) == 2
    assert len(rules._manuals) == 3
