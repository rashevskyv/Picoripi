"""Every thread class in product code can be let go of while it runs (WP6)."""
import re
from pathlib import Path

PRODUCT_PATHS = ("main.py", "components", "core", "dialogs", "handlers", "plugins", "tools", "ui", "utils")


def test_thread_classes_derive_from_worker_thread_not_from_qthread():
    """A plain QThread subclass is destroyed -- and the process aborted -- when its result slot drops it too early."""
    offenders = []
    for name in PRODUCT_PATHS:
        path = Path(name)
        for source in ([path] if path.is_file() else sorted(path.rglob("*.py"))):
            if source.as_posix() == "utils/thread_utils.py":
                continue
            for found in re.finditer(r"(?m)^class (\w+)\([^)]*\bQThread\b[^)]*\):", source.read_text(encoding="utf-8-sig")):
                offenders.append(f"{source.as_posix()}: {found.group(1)}")

    assert offenders == []
