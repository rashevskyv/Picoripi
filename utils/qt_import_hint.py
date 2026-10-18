"""What to tell the user when Qt (PyQt6) cannot be imported at start: the commonest first-start failure on Windows.

No Qt import here: the text is made when Qt is the thing that failed. It is printed to stderr by ``main.py``.
"""
from __future__ import annotations

import sys

VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"


def hint_for(error: BaseException, platform: str | None = None) -> str:
    """The steps to try after ``error``; the Windows steps (Visual C++ runtime, PATH) only on Windows."""
    platform = sys.platform if platform is None else platform
    lines = [f"Picoripi could not load Qt (PyQt6): {error}", "", "Try, in this order:"]
    step = 1
    if platform == "win32":
        lines.append(f"{step}. Install the Microsoft Visual C++ Redistributable 2015-2022 (x64): {VC_REDIST_URL}")
        lines.append("   A missing or old msvcp140.dll is the usual cause of 'The specified procedure could not be found'.")
        step += 1
        lines.append(f"{step}. Run 'where Qt6Core.dll' in this window. A copy outside the Picoripi folder (Anaconda, another")
        lines.append("   Qt program) hides the right one: remove its folder from PATH for this window and start again.")
        step += 1
    lines.append(f"{step}. Reinstall the packages: run setup.bat again (Windows) or")
    lines.append("   python -m pip install --force-reinstall PyQt6 PyQt6-Qt6 PyQt6-sip")
    step += 1
    lines.append(f"{step}. Check that the 64-bit Python is the one in the environment (Python 3.14 is the tested version).")
    return "\n".join(lines) + "\n"
