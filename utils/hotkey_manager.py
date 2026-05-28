"""
Windows-level global hotkey manager.

Used to intercept key combinations that are grabbed by the OS before Qt can
see them (e.g. Alt+Shift+Up/Down on some Windows configurations).

Usage:
    manager = HotkeyManager(main_window)
    manager.register()
    # ... later on close:
    manager.unregister()

MainWindow must override nativeEvent() and delegate to manager.handle_native_event().
"""

import sys
import ctypes
from ctypes import wintypes
from PyQt5.QtCore import QTimer
from utils.logging_utils import log_debug, log_error

# Windows message and modifier constants
WM_HOTKEY = 0x0312

MOD_ALT = 0x0001
MOD_SHIFT = 0x0004

# Virtual key codes
VK_UP    = 0x26
VK_DOWN  = 0x28
VK_LEFT  = 0x25
VK_RIGHT = 0x27

VK_SHIFT = 0x10
VK_ALT   = 0x12

# Hotkey IDs (must be unique for the window)
HOTKEY_PREV_BLOCK  = 0xBF01  # Alt+Shift+Up
HOTKEY_NEXT_BLOCK  = 0xBF02  # Alt+Shift+Down
HOTKEY_PREV_FOLDER = 0xBF03  # Alt+Shift+Left
HOTKEY_NEXT_FOLDER = 0xBF04  # Alt+Shift+Right

ID_TO_VK = {
    HOTKEY_PREV_BLOCK: VK_UP,
    HOTKEY_NEXT_BLOCK: VK_DOWN,
    HOTKEY_PREV_FOLDER: VK_LEFT,
    HOTKEY_NEXT_FOLDER: VK_RIGHT
}

class MSG(ctypes.Structure):
    """Windows MSG structure for parsing native events."""
    _fields_ = [
        ("hwnd",    wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam",  wintypes.WPARAM),
        ("lParam",  wintypes.LPARAM),
        ("time",    wintypes.DWORD),
        ("pt",      wintypes.POINT),
    ]


class HotkeyManager:
    """Registers global hotkeys on Windows that bypass OS-level interception."""

    def __init__(self, main_window):
        self.mw = main_window
        self._hwnd = None
        self._registered = False
        self._repeat_timer = QTimer()
        self._repeat_timer.timeout.connect(self._handle_repeat)
        self._last_hid = None
        self._is_repeating = False

    def register(self):
        """Register all Alt+Shift hotkeys with Windows."""
        if sys.platform != 'win32':
            return
        try:
            self._hwnd = int(self.mw.winId())
            user32 = ctypes.windll.user32
            mods = MOD_ALT | MOD_SHIFT

            results = []
            for hid, vk in ID_TO_VK.items():
                ctypes.set_last_error(0)
                res = user32.RegisterHotKey(self._hwnd, hid, mods, vk)
                results.append(bool(res))

            if all(results):
                self._registered = True
                log_debug("HotkeyManager: All Alt+Shift hotkeys registered")
            else:
                log_error("HotkeyManager: Some RegisterHotKey calls failed.")
        except Exception as e:
            log_error(f"HotkeyManager: Exception during register: {e}", exc_info=True)

    def unregister(self):
        """Unregister all hotkeys."""
        self._repeat_timer.stop()
        if sys.platform != 'win32' or not self._registered or self._hwnd is None:
            return
        try:
            user32 = ctypes.windll.user32
            for hid in ID_TO_VK.keys():
                user32.UnregisterHotKey(self._hwnd, hid)
            self._registered = False
            log_debug("HotkeyManager: All hotkeys unregistered")
        except Exception as e:
            log_error(f"HotkeyManager: Exception during unregister: {e}", exc_info=True)

    def handle_native_event(self, event_type, message):
        """
        Call this from MainWindow.nativeEvent().
        Returns (handled: bool, result: int).
        """
        try:
            msg = MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                hid = msg.wParam
                
                # If we are already repeating this hotkey, ignore the WM_HOTKEY
                if self._is_repeating and self._last_hid == hid:
                    return True, 0

                self._dispatch_hotkey(hid)
                
                # Start repeat timer
                self._last_hid = hid
                self._is_repeating = False
                self._repeat_timer.start(400) # Initial delay before repeat
                
                return True, 0

        except Exception as e:
            log_error(f"HotkeyManager: Exception in handle_native_event: {e}", exc_info=True)
        return False, 0

    def _handle_repeat(self):
        """Poll keyboard state to emulate auto-repeat."""
        if self._last_hid is None:
            self._repeat_timer.stop()
            return

        vk = ID_TO_VK.get(self._last_hid)
        if not vk:
            self._repeat_timer.stop()
            return

        user32 = ctypes.windll.user32
        def is_down(key):
            return bool(user32.GetAsyncKeyState(key) & 0x8000)

        if is_down(VK_ALT) and is_down(VK_SHIFT) and is_down(vk):
            self._is_repeating = True
            self._dispatch_hotkey(self._last_hid)
            # Switch to faster repeat interval
            if self._repeat_timer.interval() != 80:
                self._repeat_timer.setInterval(80)
        else:
            self._repeat_timer.stop()
            self._last_hid = None
            self._is_repeating = False

    def _dispatch_hotkey(self, hid):
        """Dispatch the hotkey action to ListSelectionHandler."""
        lsh = None
        if hasattr(self.mw, 'ui_handler') and hasattr(self.mw.ui_handler, 'list_selection_handler'):
            lsh = self.mw.ui_handler.list_selection_handler
        elif hasattr(self.mw, 'list_selection_handler'):
            lsh = self.mw.list_selection_handler

        if lsh is None:
            return

        if hid == HOTKEY_PREV_BLOCK:
            lsh.navigate_between_blocks(False)
        elif hid == HOTKEY_NEXT_BLOCK:
            lsh.navigate_between_blocks(True)
        elif hid == HOTKEY_PREV_FOLDER:
            lsh.navigate_between_folders(False)
        elif hid == HOTKEY_NEXT_FOLDER:
            lsh.navigate_between_folders(True)

