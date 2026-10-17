"""The speaker of a Pokémon FR string reads memory on the UI thread; the pret source files are read on a worker."""
import threading
from types import SimpleNamespace

from plugins.pokemon_fr import rules as fr
from utils import app_mode


def test_the_speaker_lookup_reads_no_source_file_on_the_ui_thread(tmp_path, qtbot, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    (tmp_path / "text.inc").write_text("", encoding="utf-8")
    threads = []

    def pret_file_spy(rel, path):
        threads.append(threading.current_thread())
        return [SimpleNamespace(label="Hello")], {"Hello": ["Script"]}, {"Script": ["Mom"]}

    monkeypatch.setattr(fr, "_pret_file", pret_file_spy)
    manager = SimpleNamespace(project=SimpleNamespace(blocks=[SimpleNamespace(source_file="text/text.inc")]),
                              get_absolute_path=lambda rel: str(tmp_path / "text.inc"))
    rules = fr.GameRules(None)
    rules.mw = SimpleNamespace(project_manager=manager, block_to_project_file_map={})

    assert rules.get_speaker_for_string(0, 0) is None      # nothing read yet
    assert threads == []                                   # no source file was touched on the UI thread
    qtbot.waitUntil(lambda: rules.get_speaker_for_string(0, 0) == "Mom", timeout=5000)
    assert threads and all(thread is not threading.main_thread() for thread in threads)
