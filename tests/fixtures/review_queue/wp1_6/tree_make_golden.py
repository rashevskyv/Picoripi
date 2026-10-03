"""Record the block tree the pre-audit code builds for tree_scenario.py into tree_golden.json.

Rerun from the baseline worktree (commit 691699c0), outside pytest so both trees take the interactive path:

    cd /d/git/dev/Picoripi-baseline && PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
        ../Picoripi/venv/Scripts/python.exe ../Picoripi/tests/fixtures/review_queue/wp1_6/tree_make_golden.py < /dev/null

Each scenario runs in its own process with its own home directory: the application reopens the last
project at start-up, and the baseline has no other settings isolation.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORIES = ("legacy", "normalized")


def record(story: str, out: Path) -> None:
    scratch = Path(tempfile.mkdtemp(prefix=f"rq_tree_{story}_"))
    os.environ["USERPROFILE"] = os.environ["HOME"] = str(scratch / "home")
    sys.path.insert(0, str(HERE))

    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    import tree_scenario
    import handlers.project_action.lifecycle_mixin as lifecycle
    from main import MainWindow

    def wait_until(predicate, timeout=20.0):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() > deadline:
                raise TimeoutError("the tree did not settle")
            app.processEvents()
            time.sleep(0.005)

    tree_scenario.no_machine_script()
    project_file = tree_scenario.build_project(scratch / story, story)
    mw = MainWindow()

    def open_project(path):
        lifecycle.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(path), ""))
        mw.project_action_handler.open_project_action()

    result = tree_scenario.run(mw, project_file, open_project, wait_until, story)
    mw.is_testing = True
    mw.close()
    out.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        record(sys.argv[1], Path(sys.argv[2]))
        sys.exit(0)
    golden = {}
    for story in STORIES:
        out = Path(tempfile.mkdtemp()) / "tree.json"
        subprocess.run([sys.executable, __file__, story, str(out)], check=True, stdin=subprocess.DEVNULL)
        golden[story] = json.loads(out.read_text(encoding="utf-8"))
    target = HERE / "tree_golden.json"
    target.write_text(json.dumps(golden, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("written", target)
