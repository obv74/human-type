"""Desktop UI for HumanType."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from typing import Optional

import customtkinter as ctk
from pynput import keyboard as pynput_keyboard

from .engine import HumanTyper, TypeProgress, TypeSettings, estimate_seconds
from .keyboard import create_keyboard

ACCENT = "#e8a54b"
ACCENT_HOVER = "#d4943a"
BG = "#101216"
CARD = "#181b21"
MUTED = "#8b919c"
TEXT = "#e8eaed"
DANGER = "#e06c75"


class HumanTypeApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("HumanType")
        self.geometry("720x700")
        self.minsize(660, 640)
        self.configure(fg_color=BG)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._typer = HumanTyper(create_keyboard())
        self._busy = False
        self._hotkey_listener: Optional[pynput_keyboard.GlobalHotKeys] = None
        self._latest_progress: Optional[TypeProgress] = None
        self._last_ui = 0.0

        self._build()
        self._bind_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(200, self._refresh_meta)

    def _build(self) -> None:
        pad = 22

        footer = ctk.CTkFrame(self, fg_color="transparent", height=52)
        footer.pack(side="bottom", fill="x", padx=pad, pady=(0, 18))
        footer.pack_propagate(False)

        self.progress = ctk.CTkProgressBar(
            footer, progress_color=ACCENT, fg_color="#2a2f3a", height=6
        )
        self.progress.pack(fill="x", pady=(6, 8))
        self.progress.set(0)

        self.status = ctk.CTkLabel(
            footer,
            text="Ready  ·  click a field after Start, or press F8 while that field is focused",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
            anchor="w",
            height=22,
        )
        self.status.pack(fill="x")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(side="bottom", fill="x", padx=pad, pady=(0, 8))

        self.start_btn = ctk.CTkButton(
            actions,
            text="Start typing  ·  F8",
            height=42,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#1a140c",
            command=self._start_with_countdown,
        )
        self.start_btn.pack(side="left", fill="x", expand=True)

        self.stop_btn = ctk.CTkButton(
            actions,
            text="Stop  ·  F9",
            height=42,
            width=140,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#3a2226",
            hover_color="#4a2a30",
            text_color=DANGER,
            command=self._stop,
            state="disabled",
        )
        self.stop_btn.pack(side="left", padx=(10, 0))

        settings = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        settings.pack(side="bottom", fill="x", padx=pad, pady=(0, 12))

        row1 = ctk.CTkFrame(settings, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(row1, text="Speed", text_color=MUTED, width=90, anchor="w").pack(side="left")
        self.wpm = ctk.CTkSlider(
            row1, from_=30, to=140, number_of_steps=110, progress_color=ACCENT, button_color=ACCENT,
            command=lambda _v: self._refresh_meta(),
        )
        self.wpm.set(62)
        self.wpm.pack(side="left", fill="x", expand=True, padx=8)
        self.wpm_label = ctk.CTkLabel(row1, text="62 WPM", text_color=TEXT, width=80, anchor="e")
        self.wpm_label.pack(side="right")

        row2 = ctk.CTkFrame(settings, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(row2, text="Humanize", text_color=MUTED, width=90, anchor="w").pack(side="left")
        self.humanize = ctk.CTkSlider(
            row2, from_=0, to=100, number_of_steps=100, progress_color=ACCENT, button_color=ACCENT,
            command=lambda _v: self._refresh_meta(),
        )
        self.humanize.set(70)
        self.humanize.pack(side="left", fill="x", expand=True, padx=8)
        self.human_label = ctk.CTkLabel(row2, text="Natural", text_color=TEXT, width=80, anchor="e")
        self.human_label.pack(side="right")

        row3 = ctk.CTkFrame(settings, fg_color="transparent")
        row3.pack(fill="x", padx=16, pady=(6, 14))
        ctk.CTkLabel(row3, text="Countdown", text_color=MUTED, width=90, anchor="w").pack(side="left")
        self.delay = ctk.CTkSlider(
            row3, from_=1, to=8, number_of_steps=7, progress_color=ACCENT, button_color=ACCENT,
            command=lambda _v: self._refresh_meta(),
        )
        self.delay.set(3)
        self.delay.pack(side="left", fill="x", expand=True, padx=8)
        self.delay_label = ctk.CTkLabel(row3, text="3 s", text_color=TEXT, width=80, anchor="e")
        self.delay_label.pack(side="right")

        extras = ctk.CTkFrame(settings, fg_color="transparent")
        extras.pack(fill="x", padx=16, pady=(0, 14))
        self.typos = ctk.CTkCheckBox(
            extras,
            text="Occasional typos (then correct them)",
            font=ctk.CTkFont(size=13),
            text_color=MUTED,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
        )
        self.typos.select()
        self.typos.pack(side="left")

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(side="top", fill="x", padx=pad, pady=(22, 8))

        ctk.CTkLabel(
            header,
            text="HumanType",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Paste text here, click the field you want, then type like a person.",
            font=ctk.CTkFont(size=13),
            text_color=MUTED,
        ).pack(anchor="w", pady=(2, 0))

        box = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        box.pack(fill="both", expand=True, padx=pad, pady=(8, 12))

        tools = ctk.CTkFrame(box, fg_color="transparent")
        tools.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkButton(
            tools,
            text="Paste clipboard",
            width=130,
            height=30,
            fg_color="#2a2f3a",
            hover_color="#353b48",
            command=self._paste_clipboard,
        ).pack(side="left")
        ctk.CTkButton(
            tools,
            text="Clear",
            width=80,
            height=30,
            fg_color="#2a2f3a",
            hover_color="#353b48",
            command=lambda: self.text.delete("1.0", "end"),
        ).pack(side="left", padx=(8, 0))

        self.always_on_top = ctk.CTkCheckBox(
            tools,
            text="Always on top",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._toggle_topmost,
        )
        self.always_on_top.pack(side="right")

        self.text = ctk.CTkTextbox(
            box,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            fg_color="#12151b",
            text_color=TEXT,
            border_width=0,
            wrap="word",
        )
        self.text.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.text.bind("<KeyRelease>", lambda _e: self._refresh_meta())
        self.text.bind("<<Paste>>", lambda _e: self.after(50, self._refresh_meta))

    def _settings(self) -> TypeSettings:
        return TypeSettings(
            wpm=int(self.wpm.get()),
            humanize=self.humanize.get() / 100.0,
            typos=bool(self.typos.get()),
        )

    def _body(self) -> str:
        return self.text.get("1.0", "end-1c")

    def _human_word(self, value: float) -> str:
        if value < 20:
            return "Even"
        if value < 45:
            return "Light"
        if value < 75:
            return "Natural"
        return "Messy"

    def _refresh_meta(self) -> None:
        settings = self._settings()
        self.wpm_label.configure(text=f"{settings.wpm} WPM")
        self.human_label.configure(text=self._human_word(self.humanize.get()))
        self.delay_label.configure(text=f"{int(self.delay.get())} s")
        if self._busy:
            return
        text = self._body()
        n = len(text)
        if n == 0:
            self.status.configure(text="Ready  ·  paste some text to begin")
            return
        secs = estimate_seconds(text, settings)
        self.status.configure(text=f"Ready  ·  {n} characters  ·  ~{secs:.0f}s  ·  F8 types now, Start waits")

    def _toggle_topmost(self) -> None:
        self.attributes("-topmost", bool(self.always_on_top.get()))

    def _paste_clipboard(self) -> None:
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            self._set_status("Clipboard is empty")
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", clip)
        self._refresh_meta()

    def _bind_hotkeys(self) -> None:
        def on_f8() -> None:
            self.after(0, self._start_now)

        def on_f9() -> None:
            self.after(0, self._stop)

        self._hotkey_listener = pynput_keyboard.GlobalHotKeys({"<f8>": on_f8, "<f9>": on_f9})
        self._hotkey_listener.start()

    def _start_with_countdown(self) -> None:
        if self._busy:
            return
        text = self._body()
        if not text.strip():
            self._set_status("Paste some text first")
            return
        self._run_worker(text, countdown=int(self.delay.get()))

    def _start_now(self) -> None:
        if self._busy:
            return
        text = self._body()
        if not text.strip():
            self._set_status("Paste some text first")
            return
        # F8 while HumanType is focused would type into this window.
        if self.focus_get() is not None:
            self._start_with_countdown()
            return
        self._run_worker(text, countdown=0)

    def _run_worker(self, text: str, countdown: int) -> None:
        self._busy = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.set(0)
        self.text.configure(state="disabled")

        def work() -> None:
            try:
                for left in range(countdown, 0, -1):
                    if not self._busy:
                        self.after(0, lambda: self._set_status("Stopped"))
                        return
                    self.after(0, lambda n=left: self._set_status(f"Click the target field… starting in {n}"))
                    time.sleep(1)
                if not self._busy:
                    self.after(0, lambda: self._set_status("Stopped"))
                    return
                self.after(0, lambda: self._set_status("Typing…  F9 to stop"))
                settings = self._settings()
                self._typer.type_text(text, settings, on_progress=self._on_progress)
            finally:
                self.after(0, self._idle)

        threading.Thread(target=work, daemon=True).start()

    def _on_progress(self, progress: TypeProgress) -> None:
        self._latest_progress = progress
        now = time.monotonic()
        if not (progress.done or progress.stopped or now - self._last_ui > 0.05):
            return
        self._last_ui = now
        self.after(0, self._flush_progress)

    def _flush_progress(self) -> None:
        progress = self._latest_progress
        if progress is None:
            return
        if progress.total:
            self.progress.set(progress.index / progress.total)
        if progress.stopped:
            self._set_status(f"Stopped  ·  {progress.index}/{progress.total} characters")
        elif progress.done:
            self.progress.set(1)
            self._set_status(f"Done  ·  {progress.total} characters")
        else:
            self._set_status(f"Typing…  {progress.index}/{progress.total}  ·  F9 to stop")

    def _stop(self) -> None:
        if not self._busy:
            return
        self._busy = False
        self._typer.stop()
        self._set_status("Stopping…")

    def _idle(self) -> None:
        self._busy = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.text.configure(state="normal")

    def _set_status(self, message: str) -> None:
        self.status.configure(text=message)

    def _on_close(self) -> None:
        self._busy = False
        self._typer.stop()
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        self.destroy()
