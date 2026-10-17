"""The owner's build for the Project Manager: the 3ds-ua repo's Makefile runs on a staged copy, never in the repo.

The Makefile is the engine (``build-ru`` writes ``dist/``, ``build-en`` writes ``dist_en/``). It writes beside itself,
so the build runs in a staging folder inside the build's output folder: the Makefile, ``tools/``, ``assets/`` and the
project's ``src/`` are copied there, and ``work/`` is a link to the owner's ``work/`` (the tools only read it). The
result moves out of the staging folder, and the staging folder and the link are removed in every case. The link is
removed before the staging folder, so no removal ever follows it into the owner's files.

Needs GNU make on PATH (``scoop install make``) and the Python of Picoripi, which has the Pillow the tools import.
"""
from __future__ import annotations

import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from core.i18n import tr
from utils.logging_utils import log_info, log_warning

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]

# Makefile target -> the folder it writes beside the Makefile.
TARGET_DIRS = {"build-ru": "dist", "build-en": "dist_en"}
LOG_NAME = "build.log"
STAGE_NAME = "stage"
TAIL_LINES = 15
_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")
_POLL_SECONDS = 0.2


def make_argv(make: str, target: str, python: str) -> List[str]:
    """The make command line. ``PY`` is quoted, because the Makefile puts it into a shell recipe as it is."""
    return [make, target, f'PY="{python.replace(chr(92), "/")}"']


def find_make() -> Optional[str]:
    return shutil.which("make")


def link_dir(target: Path, link: Path) -> None:
    """A junction on Windows, a symbolic link elsewhere. The link names ``target`` and does not copy it."""
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True,
                       capture_output=True, text=True)
    else:
        os.symlink(target, link, target_is_directory=True)


def unlink_dir(link: Path) -> None:
    """Remove a link made by ``link_dir`` without touching what it names. Refuses anything that is not a link."""
    if os.name == "nt":
        if not os.path.isjunction(link):
            raise ValueError(f"not a junction: {link}")
        os.rmdir(link)  # removes the junction only
    else:
        if not link.is_symlink():
            raise ValueError(f"not a symbolic link: {link}")
        os.unlink(link)


def stage(repo: Path, src: Path, staging: Path) -> None:
    """Copy what the Makefile needs into ``staging`` and link the owner's ``work`` folder into it."""
    staging.mkdir(parents=True)
    shutil.copy2(repo / "Makefile", staging / "Makefile")
    for name in ("tools", "assets"):
        shutil.copytree(repo / name, staging / name, ignore=_IGNORE)
    shutil.copytree(src, staging / "src", ignore=_IGNORE)
    link_dir(repo / "work", staging / "work")


def unstage(staging: Path) -> None:
    """Remove the staging folder. The work link goes first and alone; a folder that is still a link is not deleted."""
    link = staging / "work"
    if os.path.lexists(link):
        unlink_dir(link)
    if staging.exists():
        shutil.rmtree(staging)


def _kill_tree(process: subprocess.Popen) -> None:
    """Stop the make process and its children: only the process tree this call started."""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, text=True)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except OSError as error:
        log_warning(f"system_3ds: cannot stop the build process tree: {error}")
    if process.poll() is None:
        process.kill()


def run_process(argv: Sequence[str], cwd: Path, log_path: Path, progress: Progress,
                is_cancelled: Cancelled) -> Tuple[Optional[int], List[str]]:
    """Run ``argv`` in ``cwd``: every output line goes to ``log_path`` and to ``progress``.

    Returns (exit code, the last lines). The exit code is None when the run was cancelled, and the process tree is
    stopped first. The output is read on a thread so a cancel is seen even when the process prints nothing.
    """
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    process = subprocess.Popen(list(argv), cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", env=env,
                               start_new_session=os.name != "nt")
    lines: "queue.Queue[Optional[str]]" = queue.Queue()

    def read() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line.rstrip("\r\n"))
        lines.put(None)

    threading.Thread(target=read, daemon=True, name="system_3ds build output").start()
    tail: List[str] = []
    count = 0
    done = False
    with open(log_path, "w", encoding="utf-8") as log:
        while not done:
            if is_cancelled():
                _kill_tree(process)
                process.wait()
                return None, tail
            try:
                line = lines.get(timeout=_POLL_SECONDS)
            except queue.Empty:
                continue
            if line is None:
                done = True
                break
            count += 1
            log.write(line + "\n")
            tail = (tail + [line])[-TAIL_LINES:]
            # The build has no known length: the bar moves by a shrinking step per line and stops at 95.
            progress(min(95, int(100 * (1 - 0.98 ** count))), line)
    return process.wait(), tail


def build(source_dir: str, translation_dir: str, target_id: str, output_dir: str, progress: Progress,
          is_cancelled: Cancelled) -> Path:
    """Build ``target_id`` (a key of TARGET_DIRS) of the repo whose ``src`` is ``source_dir``; the result folder
    lands in ``output_dir``. Raises ValueError for a missing tool, a missing folder or a failed make.
    """
    if target_id not in TARGET_DIRS:
        raise ValueError(tr("Unknown build target: {0}", target_id))
    src = Path(translation_dir)  # the Ukrainian text: the files the project saves
    repo = Path(source_dir).parent  # the repo folder: the Makefile, tools/, assets/ and work/
    for needed in ("Makefile", "tools/build.py", "work"):
        if not (repo / needed).exists():
            raise ValueError(tr("The 3DS repo folder has no {0}: {1}", needed, str(repo)))
    make = find_make()
    if not make:
        raise ValueError(tr("GNU make is needed to build this mod. Install it (scoop install make) and put it on PATH."))
    out = Path(output_dir)
    staging = out / STAGE_NAME
    result_dir = out / TARGET_DIRS[target_id]
    log_path = out / LOG_NAME
    python = sys.executable
    started = time.monotonic()
    try:
        progress(0, tr("Copying the source for the build"))
        stage(repo, src, staging)
        if is_cancelled():
            return result_dir
        progress(0, tr("Running make {0}", target_id))
        code, tail = run_process(make_argv(make, target_id, python), staging, log_path, progress, is_cancelled)
        if code is None:
            return result_dir
        if code != 0:
            raise ValueError(tr("The build stopped with exit code {0}. Last lines:\n{1}", str(code), "\n".join(tail)))
        os.replace(staging / TARGET_DIRS[target_id], result_dir)
    finally:
        unstage(staging)
    log_info(f"system_3ds: {target_id} built in {time.monotonic() - started:.0f} s")
    return result_dir
