"""Global hotkeys. Windows avoids a keyboard hook so SendInput cannot deadlock it."""

from __future__ import annotations

import sys
import threading
from typing import Callable, Optional

HotkeyCallback = Callable[[], None]


class Hotkeys:
    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


def create_hotkeys(
    schedule: Callable[[HotkeyCallback], None],
    on_f8: HotkeyCallback,
    on_f9: HotkeyCallback,
    on_stealth: HotkeyCallback,
) -> Hotkeys:
    if sys.platform == "win32":
        return WinHotkeys(schedule, on_f8, on_f9, on_stealth)
    return PynputHotkeys(schedule, on_f8, on_f9, on_stealth)


class PynputHotkeys(Hotkeys):
    def __init__(
        self,
        schedule: Callable[[HotkeyCallback], None],
        on_f8: HotkeyCallback,
        on_f9: HotkeyCallback,
        on_stealth: HotkeyCallback,
    ) -> None:
        from pynput import keyboard as pynput_keyboard

        self._listener = pynput_keyboard.GlobalHotKeys(
            {
                "<f8>": lambda: schedule(on_f8),
                "<f9>": lambda: schedule(on_f9),
                "<ctrl>+<shift>+q": lambda: schedule(on_stealth),
            }
        )

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()


class WinHotkeys(Hotkeys):
    """RegisterHotKey on a private thread — no WH_KEYBOARD_LL hook."""

    _F8 = 1
    _F9 = 2
    _STEALTH = 3

    def __init__(
        self,
        schedule: Callable[[HotkeyCallback], None],
        on_f8: HotkeyCallback,
        on_f9: HotkeyCallback,
        on_stealth: HotkeyCallback,
    ) -> None:
        self._schedule = schedule
        self._handlers = {self._F8: on_f8, self._F9: on_f9, self._STEALTH: on_stealth}
        self._thread: Optional[threading.Thread] = None
        self._thread_id = 0
        self._ready = threading.Event()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="hotkeys", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def stop(self) -> None:
        import ctypes

        thread = self._thread
        thread_id = self._thread_id
        self._thread = None
        if thread is None or not thread_id:
            return
        ctypes.windll.user32.PostThreadMessageW(thread_id, 0x0012, 0, 0)  # WM_QUIT
        thread.join(timeout=2.0)

    def _run(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        user32.RegisterHotKey.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.UnregisterHotKey.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetMessageW.restype = ctypes.c_int

        mod_norepeat = 0x4000
        mod_ctrl_shift = 0x0002 | 0x0004 | mod_norepeat
        vk_f8, vk_f9, vk_q = 0x77, 0x78, 0x51

        self._thread_id = kernel32.GetCurrentThreadId()
        registered = []
        for hid, mods, vk in (
            (self._F8, mod_norepeat, vk_f8),
            (self._F9, mod_norepeat, vk_f9),
            (self._STEALTH, mod_ctrl_shift, vk_q),
        ):
            if user32.RegisterHotKey(None, hid, mods, vk):
                registered.append(hid)
        self._ready.set()

        msg = wintypes.MSG()
        try:
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break
                if msg.message == 0x0312:  # WM_HOTKEY
                    handler = self._handlers.get(int(msg.wParam))
                    if handler is not None:
                        self._schedule(handler)
        finally:
            for hid in registered:
                user32.UnregisterHotKey(None, hid)
