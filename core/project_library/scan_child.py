"""Entry point of the Project Manager's scan process: ``python -m core.project_library.scan_child``.

Reads one JSON job line from stdin (``{"data_dir": ..., "projects": [[key, project_file], ...]}``) and writes one JSON
line per event to stdout (see ``core.project_library.scan``). ``print()`` calls of plugins go to stderr, so they cannot
break the protocol. The process runs at below-normal priority, so the window keeps its share of the processor.

The window may write a line ``cancel`` to stdin: the scan then stops between projects and ends with a ``done`` event
(``cancelled: true``). The end of stdin (the window is gone) stops it the same way.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from typing import Any, Dict, Tuple


def _lower_priority() -> None:
    try:
        if os.name == "nt":
            import ctypes
            below_normal = 0x00004000
            kernel32 = ctypes.windll.kernel32
            kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), below_normal)
        else:
            os.nice(10)
    except (OSError, AttributeError):
        pass  # the priority is a courtesy; the scan runs without it


def _read_job(fd: int) -> Tuple[Dict[str, Any], bytes]:
    """The first line of stdin as the job, and the bytes that came after it. Raw reads: no buffered stream is kept,
    so a daemon thread that waits on the pipe cannot hold a lock at interpreter shutdown."""
    pending = b""
    while b"\n" not in pending:
        chunk = os.read(fd, 65536)
        if not chunk:
            raise EOFError("no job on stdin")
        pending += chunk
    line, rest = pending.split(b"\n", 1)
    return json.loads(line.decode("utf-8")), rest


def _watch_stdin(fd: int, rest: bytes, cancelled: threading.Event) -> None:
    """Set ``cancelled`` when the window writes ``cancel`` or closes the pipe. Runs on a daemon thread."""
    pending = rest
    while True:
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            if line.strip() == b"cancel":
                cancelled.set()
        chunk = os.read(fd, 4096)
        if not chunk:
            break
        pending += chunk
    cancelled.set()


def main() -> int:
    fd = sys.stdin.fileno()
    job, rest = _read_job(fd)
    cancelled = threading.Event()
    threading.Thread(target=_watch_stdin, args=(fd, rest, cancelled), name="scan-cancel", daemon=True).start()
    _lower_priority()
    from core.project_library import scan

    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", newline="\n")
    sys.stdout = sys.stderr  # plugin prints go to the log channel, not to the protocol

    def emit(event):
        protocol.write(scan.encode(event))
        protocol.flush()

    try:
        scan.run(job["data_dir"], [(str(key), str(path)) for key, path in job["projects"]], emit, cancelled.is_set)
    finally:
        protocol.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
