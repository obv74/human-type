"""Human-like typing: variable delays, bursts, pauses, optional typos."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .keyboard import Keyboard, tiny_settle

NEIGHBORS = {
    "a": "sqwz",
    "b": "vghn",
    "c": "xdfv",
    "d": "sfcerx",
    "e": "wrsdf",
    "f": "dgcrtv",
    "g": "fhtbvy",
    "h": "gjnybu",
    "i": "ujko",
    "j": "hkmnui",
    "k": "jloim",
    "l": "kop",
    "m": "njk",
    "n": "bhjm",
    "o": "iklp",
    "p": "ol",
    "q": "wa",
    "r": "edft",
    "s": "awedxz",
    "t": "rfgy",
    "u": "yhji",
    "v": "cfgb",
    "w": "qase",
    "x": "zsdc",
    "y": "tghu",
    "z": "asx",
    "1": "2q",
    "2": "13qw",
    "3": "24we",
    "4": "35er",
    "5": "46rt",
    "6": "57ty",
    "7": "68yu",
    "8": "79ui",
    "9": "80io",
    "0": "9op",
}


@dataclass
class TypeSettings:
    wpm: int = 62
    humanize: float = 0.7  # 0 = even, 1 = very human
    typos: bool = True


@dataclass
class TypeProgress:
    index: int
    total: int
    done: bool = False
    stopped: bool = False


class HumanTyper:
    def __init__(self, keyboard: Keyboard) -> None:
        self.keyboard = keyboard
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def type_text(
        self,
        text: str,
        settings: TypeSettings,
        on_progress: Optional[Callable[[TypeProgress], None]] = None,
    ) -> TypeProgress:
        self._stop = False
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        total = len(text)
        human = max(0.0, min(1.0, settings.humanize))
        mean = 60.0 / (max(20, settings.wpm) * 5.0)
        sigma = mean * (0.12 + 0.55 * human)
        typo_rate = (0.022 * human) if settings.typos else 0.0
        burst_left = 0
        since_pause = 0
        prev = ""

        for i, char in enumerate(text):
            if self._stop:
                progress = TypeProgress(index=i, total=total, stopped=True)
                if on_progress:
                    on_progress(progress)
                return progress

            if burst_left <= 0 and human > 0.15 and random.random() < 0.12 * human:
                burst_left = random.randint(3, 8)

            delay = random.gauss(mean, sigma)
            if burst_left > 0:
                burst_left -= 1
                delay *= random.uniform(0.35, 0.7)
            else:
                delay *= random.uniform(0.75, 1.35)

            if prev in ".!?":
                delay += random.uniform(0.18, 0.7) * human
            elif prev in ",;:":
                delay += random.uniform(0.06, 0.28) * human
            elif prev in " ":
                delay += random.uniform(0.02, 0.14) * human
            if char.isupper() and char.isalpha():
                delay += random.uniform(0.015, 0.07) * (0.4 + human)
            if char in "()[]{}\"'":
                delay += random.uniform(0.02, 0.1) * human

            since_pause += 1
            if human > 0.25 and since_pause > random.randint(55, 140) and random.random() < 0.35 * human:
                delay += random.uniform(0.35, 1.6) * human
                since_pause = 0

            time.sleep(max(0.012, delay))

            if (
                typo_rate > 0
                and char.isalpha()
                and random.random() < typo_rate
            ):
                wrong = _nearby(char)
                if wrong:
                    self.keyboard.write(wrong)
                    tiny_settle()
                    time.sleep(random.uniform(0.08, 0.28) * (0.5 + human))
                    self.keyboard.backspace()
                    tiny_settle()
                    time.sleep(random.uniform(0.04, 0.14))

            self.keyboard.write(char)
            tiny_settle()
            prev = char

            if on_progress:
                on_progress(TypeProgress(index=i + 1, total=total))

        progress = TypeProgress(index=total, total=total, done=True)
        if on_progress:
            on_progress(progress)
        return progress


def estimate_seconds(text: str, settings: TypeSettings) -> float:
    chars = max(1, len(text))
    mean = 60.0 / (max(20, settings.wpm) * 5.0)
    extra = 0.08 * settings.humanize
    return chars * (mean + extra)


def _nearby(char: str) -> str:
    key = char.lower()
    options = NEIGHBORS.get(key, "")
    if not options:
        return ""
    pick = random.choice(options)
    return pick.upper() if char.isupper() else pick
