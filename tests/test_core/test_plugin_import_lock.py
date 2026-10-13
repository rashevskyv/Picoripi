"""The Project Manager's plugin import and the main window's plugin load take one lock, so they never overlap."""
import importlib
import threading

from core.project_library.plugin_facts import default_load_rules
from ui.main_window.main_window_plugin_handler import forget_plugin_modules
from utils.plugin_import import PLUGIN_IMPORT_LOCK


def test_a_count_worker_waits_while_the_main_window_holds_the_plugin_lock():
    results = []
    worker = threading.Thread(target=lambda: results.append(default_load_rules("plain_text")))
    with PLUGIN_IMPORT_LOCK:
        worker.start()
        worker.join(0.3)
        blocked_while_held = worker.is_alive() and results == []
    worker.join(10)

    assert blocked_while_held
    assert not worker.is_alive()
    assert type(results[0]).__name__ == "GameRules"


def test_forgetting_and_importing_one_plugin_on_two_threads_never_fails():
    errors = []

    def main_window_side():
        for _ in range(10):
            try:
                with PLUGIN_IMPORT_LOCK:
                    forget_plugin_modules("plain_text")
                    importlib.import_module("plugins.plain_text.rules")
            except Exception as exc:  # reported below; a thread must not die silently
                errors.append(exc)

    def count_side():
        for _ in range(10):
            try:
                assert default_load_rules("plain_text").get_display_name()
            except Exception as exc:
                errors.append(exc)

    threads = [threading.Thread(target=main_window_side), threading.Thread(target=count_side)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)

    assert errors == []
