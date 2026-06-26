import os
import ctypes
from utils.logging_utils import log_info, log_error

def prevent_sleep():
    """Prevent sleep."""
    if os.name == 'nt':
        try:
            # ES_CONTINUOUS = 0x80000000, ES_SYSTEM_REQUIRED = 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
            log_info("System sleep prevention activated.")
        except Exception as e:
            log_error(f"Failed to set sleep prevention: {e}")

def restore_sleep():
    """Restore sleep."""
    if os.name == 'nt':
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            log_info("System sleep prevention deactivated.")
        except Exception as e:
            log_error(f"Failed to restore sleep state: {e}")

def put_to_sleep():
    """Put to sleep."""
    if os.name == 'nt':
        try:
            # SetSuspendState(False, True, False) -> sleep
            ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
            log_info("System suspended successfully.")
        except Exception as e:
            log_error(f"Failed to suspend system: {e}")
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
