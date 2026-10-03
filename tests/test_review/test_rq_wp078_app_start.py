"""Review queue WP7: the application starts through tasks.py the way run.bat / run.sh start it.

The real ``python tasks.py run`` in a subprocess, offscreen, with the home directory (and with it
SETTINGS_DIR) pointed at a temporary folder so the owner's settings are never read or written.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
READY = "Starting Qt event loop"


def _kill_tree(process):
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                       stdin=subprocess.DEVNULL, timeout=30)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(10)


@pytest.fixture
def started_app(tmp_path):
    if (ROOT / "settings.json").exists():
        pytest.skip("a settings.json in the repository would be migrated (renamed) by main.py")
    home = tmp_path / "home"
    home.mkdir()
    log_path = tmp_path / "app.log"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", HOME=str(home), USERPROFILE=str(home),
               PYTHONIOENCODING="utf-8")
    env.pop("VIRTUAL_ENV", None)
    with open(log_path, "w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "tasks.py", "run"], cwd=ROOT, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, env=env,
                                   start_new_session=sys.platform != "win32")
    try:
        yield process, log_path, home
    finally:
        _kill_tree(process)


def test_the_application_starts_and_runs_its_event_loop_without_an_error(started_app):
    process, log_path, home = started_app
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and process.poll() is None \
            and READY not in log_path.read_text(encoding="utf-8", errors="replace"):
        time.sleep(0.2)
    ready_at = time.monotonic()
    while time.monotonic() - ready_at < 2 and process.poll() is None:   # the first turns of the event loop
        time.sleep(0.2)
    log = log_path.read_text(encoding="utf-8", errors="replace")

    assert READY in log, log[-3000:]
    assert process.poll() is None, log[-3000:]                            # still running
    assert (home / ".picoripi").is_dir()                                 # its settings went to the temporary home
    assert "Uncaught exception" not in log, [line for line in log.splitlines() if "Uncaught" in line]
