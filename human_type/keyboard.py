"""OS keyboard backend. Windows uses SendInput (Unicode-safe)."""

from __future__ import annotations

import sys
import time

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D


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

    def _tap_vk(self, vk: int) -> None:
        self._send_vk(vk, 0)
        self._send_vk(vk, KEYEVENTF_KEYUP)

    def _send_vk(self, vk: int, flags: int) -> None:
        ii = self._InputI()
        ii.ki = self._KeyBdInput(vk, 0, flags, 0, self._extra)
        inp = self._Input(INPUT_KEYBOARD, ii)
        self._send(1, self._ctypes.byref(inp), self._ctypes.sizeof(inp))

    def _send_unicode(self, char: str, flags: int) -> None:
        code = ord(char)
        ii = self._InputI()
        ii.ki = self._KeyBdInput(0, code, KEYEVENTF_UNICODE | flags, 0, self._extra)
        inp = self._Input(INPUT_KEYBOARD, ii)
        self._send(1, self._ctypes.byref(inp), self._ctypes.sizeof(inp))

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
                self._send_unicode(part, 0)
                self._send_unicode(part, KEYEVENTF_KEYUP)
            return
        self._send_unicode(char, 0)
        self._send_unicode(char, KEYEVENTF_KEYUP)

    def backspace(self) -> None:
        self._tap_vk(VK_BACK)

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


def tiny_settle() -> None:
    time.sleep(0.004)
