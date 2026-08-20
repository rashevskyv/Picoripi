# utils/power_utils.py ---
import os
import ctypes
from utils.logging_utils import log_info, log_error

if os.name == "nt":

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
else:
    LASTINPUTINFO = None  # type: ignore


def get_system_idle_seconds() -> float:
    """Returns the elapsed time in seconds since the last system-wide user input (mouse/keyboard).

    On Windows, uses GetLastInputInfo. On other platforms or on error, returns 0.0.
    """
    if (
        os.name == "nt"
        and hasattr(ctypes, "windll")
        and hasattr(ctypes.windll, "user32")
        and LASTINPUTINFO is not None
    ):
        try:
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                millis = (
                    ctypes.windll.kernel32.GetTickCount() - lii.dwTime
                ) & 0xFFFFFFFF
                return max(0.0, float(millis) / 1000.0)
        except Exception as e:
            log_error(f"Failed to query system idle time: {e}")
    return 0.0


def prevent_sleep():
    """Prevent Windows from going to sleep while a background task is running."""
    if (
        os.name == "nt"
        and hasattr(ctypes, "windll")
        and hasattr(ctypes.windll, "kernel32")
    ):
        try:
            # ES_CONTINUOUS = 0x80000000, ES_SYSTEM_REQUIRED = 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
            log_info("System sleep prevention activated.")
        except Exception as e:
            log_error(f"Failed to set sleep prevention: {e}")


def restore_sleep():
    """Restore normal Windows sleep state."""
    if (
        os.name == "nt"
        and hasattr(ctypes, "windll")
        and hasattr(ctypes.windll, "kernel32")
    ):
        try:
            # ES_CONTINUOUS = 0x80000000
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            log_info("System sleep prevention deactivated.")
        except Exception as e:
            log_error(f"Failed to restore sleep state: {e}")


def put_to_sleep():
    """Put the system to sleep / hibernation."""
    if os.name == "nt":
        try:
            if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "powrprof"):
                ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
                log_info("System suspended successfully.")
                return
        except Exception as e:
            log_error(f"Failed to suspend system via powrprof: {e}")
        try:
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        except Exception as e:
            log_error(f"Failed to suspend system via rundll32: {e}")
