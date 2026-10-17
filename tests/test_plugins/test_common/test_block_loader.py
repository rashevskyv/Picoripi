"""ReadThrough: a plugin's file reads run on a worker; the UI thread gets them from memory (plugins/common/block_loader.py)."""
import threading

from plugins.common.block_loader import ReadThrough, rescan_block
from utils import app_mode


def test_a_miss_on_the_ui_thread_returns_the_default_and_the_read_runs_on_a_worker(qtbot, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    ready, threads = [], []
    reads = ReadThrough("test", on_ready=ready.append)

    def read():
        threads.append(threading.current_thread())
        return 42

    assert reads.get("k", read, default=-1) == -1
    qtbot.waitUntil(lambda: reads.get("k", read, default=-1) == 42, timeout=5000)
    assert ready == ["k"]                       # the owner is told once, on the UI thread
    assert len(threads) == 1 and threads[0] is not threading.main_thread()


def test_a_key_that_is_pending_starts_one_read(qtbot, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    gate, calls = threading.Event(), []
    reads = ReadThrough("test")

    def read():
        calls.append(1)
        gate.wait(5)
        return "value"

    for _ in range(3):
        reads.get("k", read)
    gate.set()
    qtbot.waitUntil(lambda: reads.get("k", read) == "value", timeout=5000)
    assert len(calls) == 1


def test_clear_stops_the_running_read_and_its_result_never_reaches_memory(qtbot, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    gate = threading.Event()
    reads = ReadThrough("test")
    reads.get("k", lambda: (gate.wait(5), "old")[1])
    (reader,) = reads._readers.values()
    assert reader.isRunning()
    gate.set()
    reads.clear()                               # bounded wait: the read ends, the thread is not left running
    assert not reader.isRunning()
    assert reads.get("k", lambda: "new", default="pending") == "pending"
    qtbot.waitUntil(lambda: reads.get("k", lambda: "new", default="pending") == "new", timeout=5000)
    assert reads.get("k", lambda: "never", default="pending") == "new"


def test_a_read_that_raises_stores_none_and_is_not_read_again(qtbot, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    calls = []
    reads = ReadThrough("test")

    def broken():
        calls.append(1)
        raise ValueError("broken file")

    reads.get("k", broken)
    qtbot.waitUntil(lambda: "k" in reads._values, timeout=5000)
    assert reads.get("k", broken, default="pending") is None
    assert len(calls) == 1


def test_headless_runs_the_read_inline(monkeypatch):
    monkeypatch.setattr(app_mode, "headless", True)
    assert ReadThrough("test").get("k", lambda: 7, default=-1) == 7


def test_a_read_off_the_ui_thread_runs_inline_even_when_not_headless(monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    reads = ReadThrough("test")
    seen = []
    worker = threading.Thread(target=lambda: seen.append(reads.get("k", lambda: 9, default=-1)))
    worker.start()
    worker.join(5)
    assert seen == [9]


def test_rescan_without_a_scan_handler_does_nothing():
    rescan_block(object(), 0)
