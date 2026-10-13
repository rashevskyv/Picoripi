"""Entry point of the Project Manager's scan process: ``python -m core.project_library.scan_child``.

Reads one JSON job from stdin (``{"data_dir": ..., "projects": [[key, project_file], ...]}``) and writes one JSON line
per event to stdout (see ``core.project_library.scan``). ``print()`` calls of plugins go to stderr, so they cannot break
the protocol. The process runs at below-normal priority, so the window keeps its share of the processor.
"""
from __future__ import annotations

import json
import os
import sys


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


def main() -> int:
    job = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    _lower_priority()
    from core.project_library import scan

    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", newline="\n")
    sys.stdout = sys.stderr  # plugin prints go to the log channel, not to the protocol

    def emit(event):
        protocol.write(scan.encode(event))
        protocol.flush()

    try:
        scan.run(job["data_dir"], [(str(key), str(path)) for key, path in job["projects"]], emit, lambda: False)
    finally:
        protocol.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
