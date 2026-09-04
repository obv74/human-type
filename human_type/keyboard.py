"""OS keyboard backend. Windows uses SendInput (Unicode-safe)."""

from __future__ import annotations

import sys
import time

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MAPVK_VK_TO_VSC = 0
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
# Slow PCs / AV hooks often drop a Backspace that follows a Unicode char too quickly.
KEY_SETTLE = 0.008
EDIT_SETTLE = 0.028


class Keyboard:
    def type_char(self, char: str) -> None:
        raise NotImplementedError

    def backspace(self) -> None:
        raise NotImplementedError

    def enter(self) -> None:
        raise NotImplementedError

    def tab(self) -> None:
        raise NotImplementedError

    def write(self, char: str) -> None:
        if char in ("\n", "\r"):
            self.enter()
        elif char == "\t":
            self.tab()
        else:
            self.type_char(char)


class WindowsKeyboard(Keyboard):
    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        extra = ctypes.c_void_p(0)

        class KeyBdInput(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p),
            ]

        class HardwareInput(ctypes.Structure):
            _fields_ = [
                ("uMsg", wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]

        class MouseInput(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p),
            ]

        class InputI(ctypes.Union):
            _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]

        class Input(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong), ("ii", InputI)]

        self._KeyBdInput = KeyBdInput
        self._InputI = InputI
        self._Input = Input
        self._extra = extra
        self._send = ctypes.windll.user32.SendInput
        self._send.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self._send.restype = wintypes.UINT
        self._map_vk = ctypes.windll.user32.MapVirtualKeyW
        self._map_vk.argtypes = [wintypes.UINT, wintypes.UINT]
        self._map_vk.restype = wintypes.UINT

    def _send_pair(self, first: object, second: object) -> None:
        arr = (self._Input * 2)(first, second)
        self._send(2, arr, self._ctypes.sizeof(self._Input))

    def _vk_event(self, vk: int, flags: int) -> object:
        scan = self._map_vk(vk, MAPVK_VK_TO_VSC)
        ii = self._InputI()
        ii.ki = self._KeyBdInput(vk, scan, flags, 0, self._extra)
        return self._Input(INPUT_KEYBOARD, ii)

    def _unicode_event(self, char: str, flags: int) -> object:
        ii = self._InputI()
        ii.ki = self._KeyBdInput(0, ord(char), KEYEVENTF_UNICODE | flags, 0, self._extra)
        return self._Input(INPUT_KEYBOARD, ii)

    def _tap_vk(self, vk: int) -> None:
        self._send_pair(self._vk_event(vk, 0), self._vk_event(vk, KEYEVENTF_KEYUP))

    def _tap_unicode(self, char: str) -> None:
        self._send_pair(self._unicode_event(char, 0), self._unicode_event(char, KEYEVENTF_KEYUP))

    def type_char(self, char: str) -> None:
        if not char:
            return
        # Surrogate pair for characters outside the BMP
        code = ord(char)
        if code > 0xFFFF:
            encoded = char.encode("utf-16-le")
            lo = int.from_bytes(encoded[0:2], "little")
            hi = int.from_bytes(encoded[2:4], "little")
            for part in (chr(lo), chr(hi)):
                self._tap_unicode(part)
            return
        self._tap_unicode(char)

    def backspace(self) -> None:
        self._tap_vk(VK_BACK)
        time.sleep(EDIT_SETTLE)

    def enter(self) -> None:
        self._tap_vk(VK_RETURN)

    def tab(self) -> None:
        self._tap_vk(VK_TAB)


class PynputKeyboard(Keyboard):
    def __init__(self) -> None:
        from pynput.keyboard import Controller, Key

        self._kb = Controller()
        self._Key = Key

    def type_char(self, char: str) -> None:
        self._kb.type(char)

    def backspace(self) -> None:
        self._kb.press(self._Key.backspace)
        self._kb.release(self._Key.backspace)
        time.sleep(EDIT_SETTLE)

    def enter(self) -> None:
        self._kb.press(self._Key.enter)
        self._kb.release(self._Key.enter)

    def tab(self) -> None:
        self._kb.press(self._Key.tab)
        self._kb.release(self._Key.tab)


def create_keyboard() -> Keyboard:
    if sys.platform == "win32":
        return WindowsKeyboard()
    return PynputKeyboard()


def read_os_clipboard() -> str:
    """Read system clipboard text. Avoid Tk clipboard_get() — it can hang
    or miss Unicode text when the window is withdrawn."""
    if sys.platform != "win32":
        return ""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    cf_unicode = 13  # CF_UNICODETEXT

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    opened = False
    for _ in range(10):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        return ""
    try:
        handle = user32.GetClipboardData(cf_unicode)
        if not handle:
            return ""
        locked = kernel32.GlobalLock(handle)
        if not locked:
            return ""
        try:
            return ctypes.wstring_at(locked) or ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def tiny_settle() -> None:
    time.sleep(KEY_SETTLE)


def wait_keys_up(timeout: float = 2.0) -> None:
    """Wait until Ctrl/Shift/Alt/F8/F9/Q are released so injected keys are clean."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = wintypes.SHORT
    keys = (0x10, 0x11, 0x12, 0x77, 0x78, 0x51)  # Shift, Ctrl, Alt, F8, F9, Q
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in keys):
            return
        time.sleep(0.03)
