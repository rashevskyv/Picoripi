"""A message block's line labels come from the ``.tbl`` beside its ``.dat`` (Scarlet / Violet, Legends: Z-A and Sword / Shield)."""
import struct
import threading
from pathlib import Path
from types import SimpleNamespace

from plugins.common import gfmsg, message_block
from plugins.common.block_loader import ReadThrough
from utils import app_mode


def _tbl(labels):
    """An ``AHTB`` label table: u32 count, then per line a u64 hash, a u16 length and the zero-terminated label."""
    out = struct.pack("<I", len(labels))
    for index, label in enumerate(labels):
        raw = label.encode("utf-8") + b"\0"
        out += struct.pack("<Q", index) + struct.pack("<H", len(raw)) + raw
    return b"AHTB" + out


def _project(tmp_path):
    (tmp_path / "language_select.dat").write_bytes(
        gfmsg.write([(gfmsg.from_editor("Which language?"), 0), (gfmsg.from_editor("Second line"), 0)]))
    (tmp_path / "language_select.tbl").write_bytes(_tbl(["guide_01", "guide_02"]))
    project = SimpleNamespace(blocks=[SimpleNamespace(source_file="message/language_select.dat")])
    manager = SimpleNamespace(project=project, get_absolute_path=lambda rel: str(tmp_path / Path(rel).name))
    return SimpleNamespace(project_manager=manager, block_to_project_file_map={})


def test_labels_and_flags_of_a_block_come_from_its_dat_and_tbl(tmp_path):
    mw = _project(tmp_path)
    assert message_block.cached(ReadThrough("test"), mw, 0) == (
        "message/language_select.dat", [0, 0], ["guide_01", "guide_02"])


def test_a_block_without_a_message_file_gives_none():
    mw = SimpleNamespace(project_manager=SimpleNamespace(project=SimpleNamespace(blocks=[]),
                                                         get_absolute_path=str), block_to_project_file_map={})
    assert message_block.cached(ReadThrough("test"), mw, 5) is None


def test_on_the_ui_thread_the_labels_come_from_memory_once_the_read_ends(tmp_path, qtbot, monkeypatch):
    """The first call on the UI thread starts the read and gives nothing; the read itself runs on a worker."""
    monkeypatch.setattr(app_mode, "headless", False)
    reads = ReadThrough("test")
    mw = _project(tmp_path)
    threads = []
    real_load = message_block.load

    def spy(rel, path):
        threads.append(threading.current_thread())
        return real_load(rel, path)

    monkeypatch.setattr(message_block, "load", spy)
    assert message_block.cached(reads, mw, 0) is None
    qtbot.waitUntil(lambda: message_block.cached(reads, mw, 0) is not None, timeout=5000)
    assert threads and all(thread is not threading.main_thread() for thread in threads)
    assert len(threads) == 1
