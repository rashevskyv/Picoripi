"""The byte-budget check of a Gen 1 string reads memory on the UI thread; the files are read on a worker."""
import json
import threading
from types import SimpleNamespace

from plugins.pokemon_gen1 import rom_project
from plugins.pokemon_gen1 import rules as gen1
from utils import app_mode

NAMES_ASM = 'Names:\n\tdname "Aa"\n\tdname "a"\n'


class _Manager:
    """The open project: one block, its source file under ``folder``."""

    def __init__(self, folder):
        self.project = SimpleNamespace(blocks=[SimpleNamespace(source_file="names.asm")])
        self.project_dir = ""
        self._folder = folder

    def get_absolute_path(self, rel):
        return str(self._folder / rel)


def test_the_budget_check_reads_no_file_on_the_ui_thread(tmp_path, qtbot, monkeypatch):
    monkeypatch.setattr(app_mode, "headless", False)
    (tmp_path / "names.asm").write_text(NAMES_ASM, encoding="utf-8")
    facts = json.loads((rom_project.FACTS_DIR / "pokered.json").read_text(encoding="utf-8"))
    names = rom_project._names(facts)
    threads = []
    real_units = gen1._asm_units

    def units_spy(rel, path):
        threads.append(threading.current_thread())
        return real_units(rel, path)

    def budgets_spy(source):
        threads.append(threading.current_thread())
        return {"Names#0": 2, "Names#1": 1}, names

    monkeypatch.setattr(gen1, "_asm_units", units_spy)
    monkeypatch.setattr(gen1, "_budgets_near", budgets_spy)
    rules = gen1.GameRules(None)
    rules.mw = SimpleNamespace(project_manager=_Manager(tmp_path), block_to_project_file_map={})

    assert rules.exceeds_byte_budget(0, 0, "Aaa") is False      # nothing read yet: the check answers False
    assert threads == []                                        # no file was touched on the UI thread
    qtbot.waitUntil(lambda: rules.exceeds_byte_budget(0, 0, "Aaa") is True, timeout=5000)
    assert threads and all(thread is not threading.main_thread() for thread in threads)
    assert rules.exceeds_byte_budget(0, 0, "Aa") is False
