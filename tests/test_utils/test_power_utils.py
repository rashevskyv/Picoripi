# tests/test_utils/test_power_utils.py ---
import ctypes
from unittest.mock import patch, MagicMock
from utils.power_utils import (
    get_system_idle_seconds,
    prevent_sleep,
    restore_sleep,
    put_to_sleep,
)


def test_get_system_idle_seconds_mocked_windows():
    with (
        patch("os.name", "nt"),
        patch.object(ctypes, "windll", create=True) as mock_windll,
    ):
        mock_user32 = MagicMock()
        mock_kernel32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_windll.kernel32 = mock_kernel32

        def mock_get_last_input_info(byref_lii):
            # Simulate last input at 10,000 ms
            byref_lii._obj.dwTime = 10000
            return 1

        mock_user32.GetLastInputInfo.side_effect = mock_get_last_input_info
        mock_kernel32.GetTickCount.return_value = (
            25000  # 15,000 ms elapsed -> 15.0 seconds
        )

        idle = get_system_idle_seconds()
        assert idle == 15.0


def test_get_system_idle_seconds_error_handling():
    with (
        patch("os.name", "nt"),
        patch.object(ctypes, "windll", create=True) as mock_windll,
    ):
        mock_windll.user32.GetLastInputInfo.side_effect = RuntimeError("DLL failure")
        idle = get_system_idle_seconds()
        assert idle == 0.0


def test_prevent_and_restore_sleep():
    with (
        patch("os.name", "nt"),
        patch.object(ctypes, "windll", create=True) as mock_windll,
    ):
        prevent_sleep()
        mock_windll.kernel32.SetThreadExecutionState.assert_called_with(
            0x80000000 | 0x00000001
        )

        restore_sleep()
        mock_windll.kernel32.SetThreadExecutionState.assert_called_with(0x80000000)


def test_put_to_sleep():
    with (
        patch("os.name", "nt"),
        patch.object(ctypes, "windll", create=True) as mock_windll,
    ):
        put_to_sleep()
        mock_windll.powrprof.SetSuspendState.assert_called_once_with(0, 1, 0)
