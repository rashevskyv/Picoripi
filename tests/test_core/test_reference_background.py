"""The reference parse on a worker thread: the result is handed to the window's thread, the aliases a parse registers
reach the editor's tag mapping (existing entries win), a plugin without worker rules keeps the synchronous path, only
the latest request is applied, and a Twilight Princess worker parse equals the synchronous one on the owner's files
(skipped without them)."""
import threading
from types import SimpleNamespace

import romhacking_root
from core.reference_manager import ReferenceManager
from core.reference_manager import ReferenceLoadWorker
from core.settings.plugin_settings import PluginSettings
from plugins.base_game_rules import BaseGameRules
from plugins.zelda_bmg.rules import GameRules as TwilightPrincessRules

PAL_RU = ("Zelda", "Twilight Princess", "GC + Wii", "ISO", "PAL_RU")


class _Window:
    """The main window as far as the reference code reads it."""

    def __init__(self, mapping=None):
        self.default_tag_mappings = dict(mapping or {})
        self.data_store = SimpleNamespace(block_names={}, reference_languages_data={}, reference_data={})
        self.refreshed = 0
        self.ui_updater = SimpleNamespace(update_text_views=self._refresh)
        self.current_game_rules = None

    def _refresh(self):
        self.refreshed += 1


class _WorkerRules:
    """A plugin whose parse registers one alias into the tag mapping it sees, as the Twilight Princess parse does."""

    def __init__(self, window):
        self.mw = window

    def supports_reference_patch(self):
        return True

    def load_multi_reference(self, patch_path, block_names=None):
        self.mw.default_tag_mappings["{X}"] = "{escape:9:0001}"
        return {"Russian (RU)": {(0, 0): "Текст"}}

    def reference_worker_rules(self):
        copy = _Window(self.mw.default_tag_mappings)
        return _WorkerRules(copy), copy


class _SyncRules:
    """A plugin without worker rules: the parse runs on the window's thread."""

    def supports_reference_patch(self):
        return True

    def load_multi_reference(self, patch_path, block_names=None):
        return {"German (DE)": {(0, 0): "Hallo"}}


def test_a_plugin_without_worker_rules_is_loaded_synchronously():
    seen = []
    assert ReferenceManager.load_in_background("ignored", None, _SyncRules(), _Window(), seen.append) is False
    assert seen == []


def test_the_background_result_reaches_the_window_thread_with_its_aliases(qtbot, tmp_path):
    window = _Window()
    seen = {}

    def done(languages):
        seen["thread"] = threading.get_ident()
        seen["languages"] = languages

    window.current_game_rules = _WorkerRules(window)
    assert ReferenceManager.load_in_background(tmp_path, None, window.current_game_rules, window, done) is True
    qtbot.waitUntil(lambda: "languages" in seen, timeout=5000)

    assert seen["thread"] == threading.main_thread().ident
    assert seen["languages"] == {"Russian (RU)": {(0, 0): "Текст"}}
    assert window.default_tag_mappings == {"{X}": "{escape:9:0001}"}


def test_adopting_aliases_keeps_the_editors_own_entries():
    window = _Window({"{X}": "{keep}"})
    _rules, worker_window = _WorkerRules(window).reference_worker_rules()
    worker_window.default_tag_mappings["{Y}"] = "{escape:9:0002}"
    worker_window.default_tag_mappings["{X}"] = "{escape:9:0001}"

    ReferenceManager.adopt_aliases(window, worker_window)

    assert window.default_tag_mappings == {"{X}": "{keep}", "{Y}": "{escape:9:0002}"}


def test_the_settings_apply_the_parse_when_it_arrives(qtbot, tmp_path):
    window = _Window()
    window.reference_patch_path = str(tmp_path)
    window.current_game_rules = _WorkerRules(window)
    settings = PluginSettings(window)

    settings.load_reference()
    qtbot.waitUntil(lambda: bool(window.data_store.reference_languages_data), timeout=5000)

    assert window.data_store.reference_data == {(0, 0): "Текст"}
    assert window.refreshed == 1
    assert window.default_tag_mappings == {"{X}": "{escape:9:0001}"}


def test_a_twilight_princess_worker_copies_the_mapping_and_never_writes_the_editors():
    window = SimpleNamespace(default_tag_mappings={"{GC:A}": "{escape:0:000a}"})
    rules = TwilightPrincessRules(main_window_ref=window)

    _worker_rules, worker_window = rules.reference_worker_rules()
    worker_window.default_tag_mappings["{x}"] = "{y}"

    assert worker_window is not window
    assert "{x}" not in window.default_tag_mappings
    assert worker_window.default_tag_mappings["{GC:A}"] == "{escape:0:000a}"


class _KeyedRules(_WorkerRules):
    """A plugin whose parse answers with the block names it was given, so each request has its own result."""

    def load_multi_reference(self, patch_path, block_names=None):
        return {"Russian (RU)": {(0, 0): repr(sorted(block_names or {}))}}

    def reference_worker_rules(self):
        copy = _Window(self.mw.default_tag_mappings)
        return _KeyedRules(copy), copy


def test_only_the_latest_request_is_applied_and_one_parse_runs_at_a_time(qtbot, tmp_path):
    applied = []

    class _Store(SimpleNamespace):
        def __setattr__(self, name, value):
            if name == "reference_languages_data":
                applied.append(value)
            super().__setattr__(name, value)

    window = _Window()
    window.data_store = _Store(block_names={}, reference_languages_data={}, reference_data={})
    window.reference_patch_path = str(tmp_path)
    window.current_game_rules = _KeyedRules(window)
    settings = PluginSettings(window)

    settings.load_reference()                       # no block names yet
    window.data_store.block_names = {"0": "zel_01"}
    settings.load_reference()                       # the project load asks again, now with names

    qtbot.waitUntil(lambda: window.data_store.reference_languages_data == {
        "Russian (RU)": {(0, 0): repr(["0"])}}, timeout=5000)
    assert all(value != {"Russian (RU)": {(0, 0): repr([])}} for value in applied)
    assert applied[-1] == {"Russian (RU)": {(0, 0): repr(["0"])}}


@romhacking_root.needs(PAL_RU)
def test_a_twilight_princess_background_parse_equals_the_synchronous_one(qtbot):
    folder = str(romhacking_root.path(*PAL_RU))
    sync_window = SimpleNamespace(default_tag_mappings={})
    expected = ReferenceManager.load_multi_reference(folder, None, game_rules=TwilightPrincessRules(
        main_window_ref=sync_window))

    background_window = SimpleNamespace(default_tag_mappings={})
    rules = TwilightPrincessRules(main_window_ref=background_window)
    seen = {}
    assert ReferenceManager.load_in_background(folder, None, rules, background_window,
                                               lambda langs: seen.update(languages=langs))
    qtbot.waitUntil(lambda: "languages" in seen, timeout=120000)   # the aliases are adopted before this callback

    assert seen["languages"] == expected
    assert background_window.default_tag_mappings == sync_window.default_tag_mappings


def test_the_base_rules_default_keeps_the_parse_on_the_window_thread():
    rules = BaseGameRules()
    assert rules.reference_worker_rules() is None
    assert ReferenceManager.has_worker_rules(rules) is False
    seen = []
    assert ReferenceManager.load_in_background("ignored", None, rules, _Window(), seen.append) is False
    assert seen == []


def test_a_base_rules_subclass_that_overrides_the_hook_has_worker_rules():
    class _OverridingRules(BaseGameRules):
        def reference_worker_rules(self):
            return self, None

    assert ReferenceManager.has_worker_rules(_OverridingRules()) is True


def test_switching_to_no_reference_discards_an_inflight_result(qtbot, tmp_path):
    entered, release = threading.Event(), threading.Event()

    class WaitingRules(_WorkerRules):
        def load_multi_reference(self, patch_path, block_names=None):
            entered.set()
            assert release.wait(5)
            return {"German (DE)": {(0, 0): "Old project"}}

        def reference_worker_rules(self):
            return WaitingRules(_Window()), None

    window = _Window()
    window.reference_patch_path = str(tmp_path)
    window.current_game_rules = WaitingRules(window)
    settings = PluginSettings(window)
    try:
        settings.load_reference()
        qtbot.waitUntil(entered.is_set)
        window.reference_patch_path = None
        window.current_game_rules = BaseGameRules()
        settings.load_reference()
        release.set()
        qtbot.waitUntil(lambda: not settings._reference_busy)
        assert window.data_store.reference_languages_data == {}
        assert window.data_store.reference_data == {}
        assert window.refreshed == 0
    finally:
        release.set()


def test_cancelled_reference_worker_does_not_emit_a_result(qtbot, tmp_path):
    entered, release = threading.Event(), threading.Event()

    class WaitingRules(_SyncRules):
        def load_multi_reference(self, patch_path, block_names=None):
            entered.set()
            assert release.wait(5)
            return {"German (DE)": {(0, 0): "Cancelled"}}

    worker = ReferenceLoadWorker(str(tmp_path), None, WaitingRules())
    results = []
    worker.loaded.connect(results.append)
    worker.start()
    try:
        qtbot.waitUntil(entered.is_set)
        worker.requestInterruption()
        with qtbot.waitSignal(worker.finished):
            release.set()
        assert results == []
    finally:
        release.set()
        assert worker.wait(5000)


def test_destroyed_owner_cancels_reference_without_callback(qtbot, tmp_path, monkeypatch):
    from PyQt6 import sip
    from PyQt6.QtCore import QObject
    import core.reference_manager as reference_module

    entered, release = threading.Event(), threading.Event()
    workers = []

    class WaitingRules(_SyncRules):
        def load_multi_reference(self, patch_path, block_names=None):
            entered.set()
            assert release.wait(5)
            return {"German (DE)": {(0, 0): "Closed"}}

        def reference_worker_rules(self):
            return WaitingRules(), None

    def make_worker(*args):
        worker = ReferenceLoadWorker(*args)
        workers.append(worker)
        return worker

    monkeypatch.setattr(reference_module, "ReferenceLoadWorker", make_worker)
    owner = QObject()
    results = []
    assert ReferenceManager.load_in_background(tmp_path, None, WaitingRules(), owner, results.append)
    try:
        qtbot.waitUntil(entered.is_set)
        owner.deleteLater()
        qtbot.waitUntil(lambda: sip.isdeleted(owner))
        with qtbot.waitSignal(workers[0].finished):
            release.set()
        assert results == []
    finally:
        release.set()
        if not sip.isdeleted(workers[0]):
            assert workers[0].wait(5000)
